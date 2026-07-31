"""Dedicated Internal Admin authentication routes — separate from customer /login."""
from __future__ import annotations

from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import logout_user

from app.platform_admin.routes import platform_admin_bp
from app.platform_admin.session import (
    attempt_admin_login,
    revoke_current_admin_session,
    get_current_admin,
)
from app.platform_admin.access import admin_host_allowed, write_admin_audit
from app.infra.rate_limit import enforce_rate_limit, RateLimitExceeded


@platform_admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if not admin_host_allowed():
        from flask import abort
        abort(403)

    if get_current_admin():
        return redirect(url_for('platform_admin.overview'))

    error = None
    if request.method == 'POST':
        try:
            enforce_rate_limit(
                'admin_auth',
                identity=f"admin-login:{(request.remote_addr or 'unknown')}",
            )
        except RateLimitExceeded:
            error = 'Too many login attempts. Please wait and try again.'
            return render_template(
                'platform_admin/login.html',
                error=error,
                next=request.args.get('next') or '',
            )

        email = (request.form.get('email') or '').strip()
        password = request.form.get('password') or ''
        remember = request.form.get('remember') == '1'
        ok, msg = attempt_admin_login(email, password, remember=remember)
        if ok:
            write_admin_audit('admin.login', resource_type='admin_session', payload={'email': email.lower()})
            nxt = request.args.get('next') or request.form.get('next') or ''
            if nxt.startswith('/admin') and not nxt.startswith('//'):
                return redirect(nxt)
            return redirect(url_for('platform_admin.overview'))
        if msg == 'MFA_REQUIRED':
            flash('Multi-factor authentication is required for this account.', 'warning')
            error = 'MFA is enabled but the second-factor step is not yet available in this build.'
        else:
            error = msg

    return render_template(
        'platform_admin/login.html',
        error=error,
        next=request.args.get('next') or '',
    )


@platform_admin_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    admin = get_current_admin()
    if admin:
        write_admin_audit('admin.logout', resource_type='admin_session', resource_id=admin.id)
    revoke_current_admin_session()
    # Also clear any customer session if present — staff should not carry customer cookies into ops
    try:
        logout_user()
    except Exception:
        pass
    flash('Signed out of Internal Admin.', 'info')
    return redirect(url_for('platform_admin.login'))
