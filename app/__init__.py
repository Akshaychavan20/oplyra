import os

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_migrate import Migrate
from config import config_by_name

# Initialize Flask extensions (lazy loading pattern)
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
migrate = Migrate()

# Configure Flask-Login settings
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'


def run_schema_migrations(app):
    """Checks and adds missing columns dynamically to support self-healing DB schema updates."""
    with app.app_context():
        import sqlalchemy as sa
        from sqlalchemy import inspect
        
        try:
            inspector = inspect(db.engine)

            def table_columns(table_name):
                if not inspector.has_table(table_name):
                    app.logger.debug(
                        "Skipping schema migration for '%s': table does not exist yet.",
                        table_name,
                    )
                    return None
                return [c['name'] for c in inspector.get_columns(table_name)]
            
            # 1. Check and add columns to projects
            project_columns = table_columns('projects')
            if project_columns is not None:
                with db.engine.begin() as conn:
                    if 'folder_id' not in project_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE projects ADD COLUMN folder_id INT NULL REFERENCES project_folders(id) ON DELETE SET NULL"))
                            app.logger.info("Added folder_id column to projects table.")
                        except Exception as e:
                            app.logger.error(f"Error adding folder_id to projects: {e}")
                            
                    if 'is_favorite' not in project_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0"))
                            app.logger.info("Added is_favorite column to projects table.")
                        except Exception as e:
                            app.logger.error(f"Error adding is_favorite to projects: {e}")
                            
                    if 'is_pinned' not in project_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0"))
                            app.logger.info("Added is_pinned column to projects table.")
                        except Exception as e:
                            app.logger.error(f"Error adding is_pinned to projects: {e}")
                            
                    if 'is_archived' not in project_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE projects ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"))
                            app.logger.info("Added is_archived column to projects table.")
                        except Exception as e:
                            app.logger.error(f"Error adding is_archived to projects: {e}")
                            
                    if 'category' not in project_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE projects ADD COLUMN category VARCHAR(100) NULL"))
                            app.logger.info("Added category column to projects table.")
                        except Exception as e:
                            app.logger.error(f"Error adding category to projects: {e}")
                            
                    if 'tags' not in project_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE projects ADD COLUMN tags TEXT NULL"))
                            app.logger.info("Added tags column to projects table.")
                        except Exception as e:
                            app.logger.error(f"Error adding tags to projects: {e}")
                            
            # 2. Check and add columns to contents
            content_columns = table_columns('contents')
            if content_columns is not None:
                with db.engine.begin() as conn:
                    if 'is_favorite' not in content_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE contents ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0"))
                            app.logger.info("Added is_favorite column to contents table.")
                        except Exception as e:
                            app.logger.error(f"Error adding is_favorite to contents: {e}")
                            
            # 3. Check and add columns to seo_analyses
            seo_columns = table_columns('seo_analyses')
            if seo_columns is not None:
                with db.engine.begin() as conn:
                    if 'details' not in seo_columns:
                        try:
                            conn.execute(sa.text("ALTER TABLE seo_analyses ADD COLUMN details TEXT NULL"))
                            app.logger.info("Added details column to seo_analyses table.")
                        except Exception as e:
                            app.logger.error(f"Error adding details to seo_analyses: {e}")

            # 4. Campaign budget currency + timeline duration fields
            campaign_columns = table_columns('campaigns')
            if campaign_columns is not None:
                with db.engine.begin() as conn:
                    if 'currency' not in campaign_columns:
                        try:
                            conn.execute(sa.text(
                                "ALTER TABLE campaigns ADD COLUMN currency VARCHAR(3) NOT NULL DEFAULT 'INR'"
                            ))
                            app.logger.info("Added currency column to campaigns table.")
                        except Exception as e:
                            app.logger.error(f"Error adding currency to campaigns: {e}")
                    if 'duration_type' not in campaign_columns:
                        try:
                            conn.execute(sa.text(
                                "ALTER TABLE campaigns ADD COLUMN duration_type VARCHAR(20) NOT NULL DEFAULT 'fixed'"
                            ))
                            app.logger.info("Added duration_type column to campaigns table.")
                        except Exception as e:
                            app.logger.error(f"Error adding duration_type to campaigns: {e}")
                    if 'recurrence' not in campaign_columns:
                        try:
                            conn.execute(sa.text(
                                "ALTER TABLE campaigns ADD COLUMN recurrence VARCHAR(20) NULL"
                            ))
                            app.logger.info("Added recurrence column to campaigns table.")
                        except Exception as e:
                            app.logger.error(f"Error adding recurrence to campaigns: {e}")

            # 5. Password reset tokens — hashed tokens + audit columns
            prt_columns = table_columns('password_reset_tokens')
            if prt_columns is not None:
                with db.engine.begin() as conn:
                    if 'token_hash' not in prt_columns:
                        try:
                            # Invalidate legacy plaintext tokens; switch to hash-only storage
                            if 'token' in prt_columns:
                                conn.execute(sa.text('DELETE FROM password_reset_tokens'))
                            conn.execute(sa.text(
                                "ALTER TABLE password_reset_tokens "
                                "ADD COLUMN token_hash VARCHAR(64) NULL"
                            ))
                            # Backfill impossible for deleted rows; add unique index after populate
                            app.logger.info("Added token_hash column to password_reset_tokens.")
                        except Exception as e:
                            app.logger.error(f"Error adding token_hash to password_reset_tokens: {e}")
                    if 'used_at' not in prt_columns:
                        try:
                            conn.execute(sa.text(
                                "ALTER TABLE password_reset_tokens ADD COLUMN used_at DATETIME NULL"
                            ))
                            app.logger.info("Added used_at column to password_reset_tokens.")
                        except Exception as e:
                            app.logger.error(f"Error adding used_at to password_reset_tokens: {e}")
                    if 'ip_address' not in prt_columns:
                        try:
                            conn.execute(sa.text(
                                "ALTER TABLE password_reset_tokens ADD COLUMN ip_address VARCHAR(45) NULL"
                            ))
                        except Exception as e:
                            app.logger.error(f"Error adding ip_address to password_reset_tokens: {e}")
                    if 'user_agent' not in prt_columns:
                        try:
                            conn.execute(sa.text(
                                "ALTER TABLE password_reset_tokens ADD COLUMN user_agent VARCHAR(512) NULL"
                            ))
                        except Exception as e:
                            app.logger.error(f"Error adding user_agent to password_reset_tokens: {e}")
                    # Drop legacy plaintext token column when present
                    refreshed = [c['name'] for c in inspector.get_columns('password_reset_tokens')]
                    if 'token' in refreshed and 'token_hash' in refreshed:
                        try:
                            # Ensure no null token_hash rows remain
                            conn.execute(sa.text(
                                "DELETE FROM password_reset_tokens WHERE token_hash IS NULL"
                            ))
                            dialect = db.engine.dialect.name
                            if dialect == 'sqlite':
                                # SQLite cannot DROP COLUMN on older versions reliably — leave orphan
                                pass
                            else:
                                conn.execute(sa.text(
                                    "ALTER TABLE password_reset_tokens DROP COLUMN token"
                                ))
                                app.logger.info("Dropped plaintext token column from password_reset_tokens.")
                        except Exception as e:
                            app.logger.error(f"Error dropping legacy token column: {e}")

            # 6. Auth security audit table (create if missing — Alembic handles prod)
            if not inspector.has_table('auth_security_logs'):
                try:
                    with db.engine.begin() as conn:
                        conn.execute(sa.text("""
                            CREATE TABLE auth_security_logs (
                                id INTEGER PRIMARY KEY AUTO_INCREMENT,
                                event_type VARCHAR(80) NOT NULL,
                                user_id INTEGER NULL,
                                ip_address VARCHAR(45) NULL,
                                user_agent VARCHAR(512) NULL,
                                details TEXT NULL,
                                created_at DATETIME NULL,
                                INDEX ix_auth_security_logs_event_type (event_type),
                                INDEX ix_auth_security_logs_user_id (user_id),
                                INDEX ix_auth_security_logs_created_at (created_at),
                                CONSTRAINT fk_auth_security_user
                                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                            )
                        """ if db.engine.dialect.name != 'sqlite' else """
                            CREATE TABLE auth_security_logs (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                event_type VARCHAR(80) NOT NULL,
                                user_id INTEGER NULL REFERENCES users(id) ON DELETE SET NULL,
                                ip_address VARCHAR(45),
                                user_agent VARCHAR(512),
                                details TEXT,
                                created_at DATETIME
                            )
                        """))
                    app.logger.info("Created auth_security_logs table.")
                except Exception as e:
                    app.logger.error(f"Error creating auth_security_logs: {e}")
        except Exception as e:
            app.logger.error(f"Error running database schema migrations: {e}")


def init_database(app):
    """Ensures database exists (for MySQL) and creates all SQLAlchemy tables.

    Production uses Alembic exclusively (USE_ALEMBIC_ONLY) — create_all is skipped.
    """
    db_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    if not db_uri:
        return

    # Register all ORM models with SQLAlchemy metadata before create_all().
    from app import models  # noqa: F401

    if app.config.get('USE_ALEMBIC_ONLY'):
        app.logger.info(
            'USE_ALEMBIC_ONLY enabled — skipping create_all. '
            'Apply schema with: flask db upgrade'
        )
        return

    if db_uri.startswith('sqlite:///'):
        with app.app_context():
            db.create_all()
            run_schema_migrations(app)
        return

    if db_uri.startswith('mysql'):
        import sqlalchemy as sa
        import re
        # Parse URI: mysql+pymysql://user:pass@host:port/dbname?options
        match = re.match(r'(mysql\+pymysql://[^/]+)/([^?]+)', db_uri)
        if match:
            base_uri, db_name = match.groups()
            db_name_clean = db_name.split('?')[0]
            # Identifier safety: alphanumeric + underscore only
            if not re.fullmatch(r'[A-Za-z0-9_]+', db_name_clean):
                app.logger.error(
                    "Refusing to create MySQL database with unsafe name: %r",
                    db_name_clean,
                )
                return
            try:
                # Connect to MySQL server without selecting database
                temp_engine = sa.create_engine(base_uri)
                with temp_engine.connect() as conn:
                    conn.execution_options(isolation_level="AUTOCOMMIT").execute(
                        sa.text(f"CREATE DATABASE IF NOT EXISTS `{db_name_clean}`")
                    )
                temp_engine.dispose()
                app.logger.info(f"MySQL database '{db_name_clean}' verified or created.")
            except Exception as e:
                app.logger.warning(f"Could not verify/create MySQL database '{db_name_clean}' dynamically: {e}")
                
        with app.app_context():
            try:
                db.create_all()
                app.logger.info("SQLAlchemy tables verified or created.")
                run_schema_migrations(app)
            except Exception as e:
                app.logger.error(f"Error creating database tables: {e}")


def create_app(config_name='default'):
    """Application Factory to initialize the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object(config_by_name[config_name])
    config_by_name[config_name].init_app(app)
    
    # Initialize extensions with the application instance
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    
    # Verify/create database and tables (skipped in production — use Alembic)
    # Set OPLYRA_SKIP_DB_INIT=1 when running `flask db migrate` against an empty DB.
    if not os.environ.get('OPLYRA_SKIP_DB_INIT'):
        init_database(app)
    
    # Register blueprints (routing modules)
    # Note: These imports are done inside the factory to prevent circular dependency issues
    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.projects.routes import projects_bp
    from app.content.routes import content_bp
    from app.content.enterprise_api import enterprise_bp
    from app.integrations.routes import integrations_bp
    from app.ai.routes import ai_bp
    from app.agents.routes import agents_bp
    from app.knowledge.routes import knowledge_bp
    from app.tools.routes import tools_bp
    from app.health.routes import health_bp
    from app.platform_admin import platform_admin_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='')
    app.register_blueprint(projects_bp, url_prefix='/clients')
    app.register_blueprint(content_bp, url_prefix='/content')
    app.register_blueprint(enterprise_bp, url_prefix='/api/v1')
    app.register_blueprint(integrations_bp, url_prefix='/integrations')
    app.register_blueprint(ai_bp, url_prefix='/api/ai')
    app.register_blueprint(agents_bp, url_prefix='/api/agents')
    app.register_blueprint(knowledge_bp, url_prefix='/api/knowledge')
    app.register_blueprint(tools_bp, url_prefix='/api/tools')
    app.register_blueprint(health_bp)
    app.register_blueprint(platform_admin_bp)

    # Seed Internal Admin RBAC (roles/permissions + bootstrap super_admin)
    with app.app_context():
        try:
            from app.platform_admin.seed import ensure_internal_admin_ready
            ensure_internal_admin_ready()
        except Exception as exc:
            app.logger.debug('Admin RBAC seed deferred: %s', exc)

    # Infrastructure: structured logging, request IDs, Celery
    from app.infra.logging_setup import configure_structured_logging, init_request_logging
    from app.infra.celery_app import init_celery
    from app.infra.redis_client import reset_redis_client
    reset_redis_client()
    configure_structured_logging(app)
    init_request_logging(app)
    init_celery(app)

    # Legacy API URL redirects (bookmarks / old links)
    from flask import redirect

    @app.route('/api/projects/')
    @app.route('/api/projects/<path:subpath>')
    def legacy_projects_redirect(subpath=''):
        target = f'/clients/{subpath}'.rstrip('/')
        return redirect(target or '/clients/', code=301)

    @app.route('/api/content/')
    @app.route('/api/content/<path:subpath>')
    def legacy_content_redirect(subpath=''):
        target = f'/content/{subpath}'.rstrip('/')
        return redirect(target or '/content/', code=301)
    
    # Custom Manual CSRF Protection (Zero External Dependencies)
    import secrets
    from flask import session, request, abort
    
    @app.context_processor
    def inject_csrf_token():
        if 'csrf_token' not in session:
            session['csrf_token'] = secrets.token_hex(16)
        return dict(csrf_token=lambda: session['csrf_token'])

    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        from app.platform_admin.access import is_platform_admin
        if current_user.is_authenticated:
            from app.models import Reminder
            unread = Reminder.query.filter_by(
                user_id=current_user.id, is_read=False
            ).order_by(Reminder.created_at.desc()).limit(8).all()
            unread_count = Reminder.query.filter_by(
                user_id=current_user.id, is_read=False
            ).count()
            return dict(
                notification_items=unread,
                notification_unread_count=unread_count,
                is_platform_admin=is_platform_admin(),
            )
        return dict(
            notification_items=[],
            notification_unread_count=0,
            is_platform_admin=False,
        )

    # Multi-currency budget formatting (INR / USD / extensible)
    from app.utils.currency import (
        format_money,
        format_money_totals,
        selectable_currencies,
        currency_registry_public,
        DEFAULT_CURRENCY,
    )

    @app.template_filter('money')
    def money_filter(amount, currency=None):
        return format_money(amount, currency or DEFAULT_CURRENCY)

    @app.context_processor
    def inject_currency_helpers():
        return dict(
            format_money=format_money,
            format_money_totals=format_money_totals,
            selectable_currencies=selectable_currencies,
            currency_registry=currency_registry_public,
            default_currency=DEFAULT_CURRENCY,
        )
        
    @app.before_request
    def verify_csrf():
        if app.testing:
            return
        # Protect all unsafe methods (not only POST)
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token')
            if not token or token != session.get('csrf_token'):
                app.logger.warning(f"CSRF validation failed for {request.path}")
                if (
                    request.path.startswith('/content/')
                    or request.path.startswith('/integrations/')
                    or request.path.startswith('/api/')
                ):
                    from flask import jsonify
                    return jsonify({
                        "success": False,
                        "error": "CSRF token missing or invalid. Please refresh the page and try again."
                    }), 400
                abort(400, "CSRF token missing or invalid.")

    @app.after_request
    def set_security_headers(response):
        """Baseline browser security headers (enterprise hardening)."""
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault(
            'Permissions-Policy',
            'geolocation=(), microphone=(), camera=()',
        )
        # CSP: allow self + existing Bootstrap/Icons CDNs used by templates
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "font-src 'self' https://cdn.jsdelivr.net data:; "
            "img-src 'self' data: https:; "
            "connect-src 'self'; "
            "frame-ancestors 'self'; "
            "base-uri 'self'; "
            "form-action 'self'",
        )
        if not app.debug and not app.testing:
            response.headers.setdefault(
                'Strict-Transport-Security',
                'max-age=31536000; includeSubDomains',
            )
        return response

    # Configure rotating file logging for production error tracing
    import logging
    from logging.handlers import RotatingFileHandler
    
    if not app.debug and not app.testing:
        file_handler = RotatingFileHandler('app_errors.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.ERROR)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.ERROR)
        
    # User loader callback for Flask-Login
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
        
    # Register HTTP error handlers
    from flask import render_template
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
        
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
        
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
        
    return app

