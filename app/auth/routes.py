import re
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, AnalyticsLog, Organization, Membership

auth_bp = Blueprint('auth', __name__)

# Basic email validation regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# Password policy: length + character classes (aligned with password-create.js)
PASSWORD_SPECIAL_RE = re.compile(r'''[!@#$%^&*()_+\-=\[\]{}|;:'",.<>?/]''')


def validate_password_strength(password: str):
    """
    Returns (is_valid, error_message).
    Enforces min 8 chars, upper, lower, digit, and allowed special character.
    """
    if password is None:
        password = ''
    # Strip accidental leading/trailing whitespace server-side
    password = password.strip()

    if len(password) < 8:
        return False, 'Password must be at least 8 characters long.'
    if not re.search(r'[A-Z]', password):
        return False, 'Password must include at least one uppercase letter.'
    if not re.search(r'[a-z]', password):
        return False, 'Password must include at least one lowercase letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must include at least one number.'
    if not PASSWORD_SPECIAL_RE.search(password):
        return False, 'Password must include at least one special character.'
    return True, None


@auth_bp.route('/auth/register', methods=['GET', 'POST'])
def register_legacy_redirect():
    """Legacy URL support — registration lives at /register."""
    if request.method == 'POST':
        return register()
    return redirect(url_for('auth.register', **request.args))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Handles User Registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        password = password.strip() if password else ''
        confirm_password = confirm_password.strip() if confirm_password else ''
        
        # Validation checks
        is_valid = True
        
        if not username or len(username) < 3:
            flash('Username must be at least 3 characters long.', 'danger')
            is_valid = False
            
        if not email or not EMAIL_REGEX.match(email):
            flash('Please enter a valid email address.', 'danger')
            is_valid = False
            
        ok, pwd_error = validate_password_strength(password)
        if not ok:
            flash(pwd_error, 'danger')
            is_valid = False
            
        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            is_valid = False
            
        if not is_valid:
            return render_template('auth/register.html', username=username, email=email)
            
        # Check database for existing users
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            flash('Email address is already registered.', 'danger')
            return render_template('auth/register.html', username=username, email=email)
            
        existing_username = User.query.filter_by(username=username).first()
        if existing_username:
            flash('Username is already taken.', 'danger')
            return render_template('auth/register.html', username=username, email=email)
            
        # Create and save new user
        new_user = User(username=username, email=email)
        new_user.set_password(password)
        
        try:
            db.session.add(new_user)
            db.session.commit()

            # Provision the user's default Organization + Membership immediately
            # so every workflow (content, campaigns, integration imports) has a
            # tenant to attach to from the very first action.
            org = Organization(name=f"{new_user.username}'s Workspace", plan_tier='pro')
            db.session.add(org)
            db.session.commit()
            db.session.add(Membership(organization_id=org.id, user_id=new_user.id, role='admin'))
            db.session.commit()

            # Log the registration activity
            log = AnalyticsLog(user_id=new_user.id, activity_type='register')
            db.session.add(log)
            db.session.commit()
            
            login_user(new_user)
            flash(f'Welcome to Oplyra, {new_user.username}! Your account is ready.', 'success')
            return redirect(url_for('main.index'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating your account. Please try again.', 'danger')
            return render_template('auth/register.html', username=username, email=email)
            
    return render_template('auth/register.html')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Handles User Authentication (Login)."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
        
    if request.method == 'POST':
        from app.infra.rate_limit import RateLimitExceeded, enforce_rate_limit
        try:
            enforce_rate_limit(
                'auth',
                identity=f'ip:{request.remote_addr or "unknown"}',
            )
        except RateLimitExceeded:
            flash('Too many login attempts. Please wait a minute and try again.', 'danger')
            return render_template('auth/login.html'), 429

        email_or_username = request.form.get('email_or_username', '').strip()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False
        
        if not email_or_username or not password:
            flash('Please fill in all fields.', 'danger')
            return render_template('auth/login.html', email_or_username=email_or_username)
            
        # Find user by email or username
        user = User.query.filter(
            (User.email == email_or_username) | (User.username == email_or_username)
        ).first()
        
        if user and user.check_password(password):
            login_user(user, remember=remember)
            
            # Log the login activity
            log = AnalyticsLog(user_id=user.id, activity_type='login')
            db.session.add(log)
            db.session.commit()
            
            flash(f'Welcome back, {user.username}!', 'success')
            
            # Redirect to next parameter (same-origin relative paths only)
            from app.utils.security import safe_redirect_target
            next_page = safe_redirect_target(
                request.args.get('next'),
                fallback=url_for('main.index'),
            )
            return redirect(next_page)
        else:
            flash('Invalid email/username or password.', 'danger')
            return render_template('auth/login.html', email_or_username=email_or_username)
            
    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    """Handles User Logout."""
    # Log the logout activity before session invalidates
    log = AnalyticsLog(user_id=current_user.id, activity_type='logout')
    db.session.add(log)
    db.session.commit()
    
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('auth.login'))


def send_reset_email(email, reset_link, user_id=None):
    """Queue branded password-reset email. Never logs the reset URL/token."""
    from app.services.mail import queue_password_reset_email
    from app.services.password_reset import RESET_TOKEN_TTL_MINUTES, log_auth_security

    current_app.logger.info('Password reset email queued for user')
    queue_password_reset_email(
        to=email,
        reset_link=reset_link,
        expires_minutes=RESET_TOKEN_TTL_MINUTES,
    )
    log_auth_security(
        'password_reset_email_sent',
        user_id=user_id,
        details={'delivery': 'queued'},
    )


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Forgot Password — anti-enumeration, rate-limited, hashed tokens."""
    from app.infra.rate_limit import RateLimitExceeded, enforce_rate_limit
    from app.services.password_reset import (
        GENERIC_FORGOT_MESSAGE,
        issue_reset_token,
        log_auth_security,
    )

    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email or not EMAIL_REGEX.match(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('auth/forgot_password.html')

        ip = request.remote_addr or 'unknown'
        try:
            enforce_rate_limit('password_reset_ip', identity=f'ip:{ip}')
            enforce_rate_limit('password_reset_email', identity=f'email:{email}')
        except RateLimitExceeded:
            log_auth_security(
                'password_reset_rate_limit_exceeded',
                details={'scope': 'forgot_password'},
            )
            current_app.logger.warning(
                'Password reset rate limit exceeded ip=%s', ip,
            )
            flash('Too many password reset requests. Please try again later.', 'danger')
            return render_template('auth/forgot_password.html'), 429

        user = User.query.filter_by(email=email).first()
        log_auth_security(
            'password_reset_requested',
            user_id=user.id if user else None,
            details={'email_present': bool(user)},
        )

        # Never reveal whether the email exists.
        if user:
            try:
                raw_token, _row = issue_reset_token(user)
                reset_link = url_for('auth.reset_password', token=raw_token, _external=True)
                send_reset_email(user.email, reset_link, user_id=user.id)
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(
                    'Error initiating password reset: %s', type(e).__name__,
                )
                # Still show generic message — do not leak failures tied to existence
                flash(GENERIC_FORGOT_MESSAGE, 'success')
                return redirect(url_for('auth.login'))

        flash(GENERIC_FORGOT_MESSAGE, 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>/validate', methods=['GET'])
def validate_reset_token(token):
    """JSON token status for the reset page (valid | missing | used | expired)."""
    from app.services.password_reset import classify_token, log_auth_security

    status, row = classify_token(token)
    if status == 'missing':
        log_auth_security('password_reset_invalid_token')
    elif status == 'expired':
        log_auth_security(
            'password_reset_expired_token',
            user_id=row.user_id if row else None,
        )
    elif status == 'used':
        log_auth_security(
            'password_reset_used_token',
            user_id=row.user_id if row else None,
        )
    return jsonify({
        'valid': status == 'valid',
        'status': status,
        'expires_at': row.expires_at.isoformat() + 'Z' if row and status == 'valid' else None,
    })


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Set a new password via a one-time hashed recovery token."""
    from app.infra.rate_limit import RateLimitExceeded, enforce_rate_limit
    from app.services.password_reset import (
        SUCCESS_RESET_MESSAGE,
        classify_token,
        consume_reset_token,
        log_auth_security,
    )

    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    ip = request.remote_addr or 'unknown'
    try:
        enforce_rate_limit('password_reset_attempt', identity=f'ip:{ip}')
    except RateLimitExceeded:
        log_auth_security('password_reset_rate_limit_exceeded', details={'scope': 'reset'})
        flash('Too many attempts. Please try again later.', 'danger')
        return redirect(url_for('auth.login'))

    status, reset_token = classify_token(token)

    if status == 'missing':
        log_auth_security('password_reset_invalid_token')
        flash('The password reset link is invalid or has already been used.', 'danger')
        return redirect(url_for('auth.login'))

    if status == 'used':
        log_auth_security(
            'password_reset_used_token',
            user_id=reset_token.user_id if reset_token else None,
        )
        flash('The password reset link is invalid or has already been used.', 'danger')
        return redirect(url_for('auth.login'))

    if status == 'expired':
        log_auth_security(
            'password_reset_expired_token',
            user_id=reset_token.user_id if reset_token else None,
        )
        if reset_token and not reset_token.used:
            try:
                reset_token.mark_used()
                db.session.commit()
            except Exception:
                db.session.rollback()
        flash('The password reset link has expired.', 'danger')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        password = password.strip() if password else ''
        confirm_password = confirm_password.strip() if confirm_password else ''

        is_valid = True

        ok, pwd_error = validate_password_strength(password)
        if not ok:
            flash(pwd_error, 'danger')
            is_valid = False

        if password != confirm_password:
            flash('Passwords do not match.', 'danger')
            is_valid = False

        if not is_valid:
            return render_template('auth/reset_password.html', token=token)

        # Re-check token immediately before consume (replay defense)
        status2, reset_token = classify_token(token)
        if status2 != 'valid' or reset_token is None:
            log_auth_security('password_reset_invalid_token', details={'phase': 'submit'})
            flash('The password reset link is invalid or has already been used.', 'danger')
            return redirect(url_for('auth.login'))

        try:
            user = reset_token.user
            user.set_password(password)
            consume_reset_token(reset_token)

            log = AnalyticsLog(user_id=user.id, activity_type='password_reset')
            db.session.add(log)
            db.session.commit()

            log_auth_security(
                'password_reset_success',
                user_id=user.id,
            )
            flash(SUCCESS_RESET_MESSAGE, 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            current_app.logger.error('Error resetting password: %s', type(e).__name__)
            flash('An error occurred while resetting your password. Please try again.', 'danger')
            return render_template('auth/reset_password.html', token=token)

    return render_template('auth/reset_password.html', token=token)
