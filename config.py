import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base Configuration"""
    # Dev fallback only — ProductionConfig rejects weak/missing keys at boot.
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default-dev-secret-key')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Lightweight engine options (safe for SQLite + MySQL)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }

    # Session cookie hardening (applied in all non-test envs; Secure forced in prod)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False

    # Gemini API configurations
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash')

    # Multi-provider AI Gateway keys (server-side only — never expose to frontend)
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    OPENAI_COMPATIBLE_API_KEY = os.environ.get('OPENAI_COMPATIBLE_API_KEY')
    OPENAI_COMPATIBLE_BASE_URL = os.environ.get('OPENAI_COMPATIBLE_BASE_URL')
    AI_DEFAULT_PROVIDER = os.environ.get('AI_DEFAULT_PROVIDER', 'auto')

    # Provider feature flags (true/false)
    AI_ENABLE_GEMINI = os.environ.get('AI_ENABLE_GEMINI', 'true')
    AI_ENABLE_OPENAI = os.environ.get('AI_ENABLE_OPENAI', 'true')
    AI_ENABLE_ANTHROPIC = os.environ.get('AI_ENABLE_ANTHROPIC', 'true')
    AI_ENABLE_DEEPSEEK = os.environ.get('AI_ENABLE_DEEPSEEK', 'true')
    AI_ENABLE_OPENAI_COMPATIBLE = os.environ.get('AI_ENABLE_OPENAI_COMPATIBLE', 'false')

    # Marketing integrations (Sprint 5A — Google OAuth)
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
    GOOGLE_OAUTH_REDIRECT_URI = os.environ.get('GOOGLE_OAUTH_REDIRECT_URI', '')
    INTEGRATIONS_MOCK_MODE = os.environ.get('INTEGRATIONS_MOCK_MODE', '').lower() in ('1', 'true', 'yes')

    # Celery & Redis task queue settings
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL') or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND') or os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', '').lower() in ('1', 'true', 'yes')
    REDIS_FORCE_MEMORY = False

    # Object storage — local|s3|gcs|azure
    STORAGE_PROVIDER = os.environ.get('STORAGE_PROVIDER', 'local')
    OBJECT_STORAGE_ROOT = os.path.join(BASE_DIR, 'uploads', 'objects')
    S3_BUCKET = os.environ.get('S3_BUCKET', '')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    GCS_BUCKET = os.environ.get('GCS_BUCKET', '')
    AZURE_BLOB_CONTAINER = os.environ.get('AZURE_BLOB_CONTAINER', '')
    AZURE_STORAGE_ACCOUNT = os.environ.get('AZURE_STORAGE_ACCOUNT', '')

    # Upload and export settings
    EXPORT_FOLDER = os.path.join(BASE_DIR, 'exports')
    KNOWLEDGE_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'knowledge')

    # Knowledge Engine / RAG
    KNOWLEDGE_VECTOR_PROVIDER = os.environ.get('KNOWLEDGE_VECTOR_PROVIDER', 'local')
    KNOWLEDGE_EMBEDDING_PROVIDER = os.environ.get('KNOWLEDGE_EMBEDDING_PROVIDER', 'local')
    KNOWLEDGE_EMBEDDING_MODEL = os.environ.get('KNOWLEDGE_EMBEDDING_MODEL', 'local-hash-384')
    KNOWLEDGE_EMBEDDING_DIMS = int(os.environ.get('KNOWLEDGE_EMBEDDING_DIMS', '384'))
    KNOWLEDGE_CHUNK_SIZE = int(os.environ.get('KNOWLEDGE_CHUNK_SIZE', '800'))
    KNOWLEDGE_CHUNK_OVERLAP = int(os.environ.get('KNOWLEDGE_CHUNK_OVERLAP', '120'))
    KNOWLEDGE_TOP_K = int(os.environ.get('KNOWLEDGE_TOP_K', '6'))
    KNOWLEDGE_RAG_ENABLED = os.environ.get('KNOWLEDGE_RAG_ENABLED', 'true').lower() in ('1', 'true', 'yes')
    LOCAL_VECTOR_MAX_SCAN = int(os.environ.get('LOCAL_VECTOR_MAX_SCAN', '5000'))

    # Vector provider credentials (optional — required when provider selected in prod)
    QDRANT_URL = os.environ.get('QDRANT_URL', '')
    QDRANT_API_KEY = os.environ.get('QDRANT_API_KEY', '')
    QDRANT_COLLECTION = os.environ.get('QDRANT_COLLECTION', 'oplyra_chunks')
    PINECONE_API_KEY = os.environ.get('PINECONE_API_KEY', '')
    PINECONE_HOST = os.environ.get('PINECONE_HOST', '')
    WEAVIATE_URL = os.environ.get('WEAVIATE_URL', '')
    WEAVIATE_API_KEY = os.environ.get('WEAVIATE_API_KEY', '')
    WEAVIATE_CLASS = os.environ.get('WEAVIATE_CLASS', 'OplyraChunk')

    # Observability
    STRUCTURED_LOGGING = os.environ.get('STRUCTURED_LOGGING', '').lower() in ('1', 'true', 'yes')
    LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS', '90'))
    ALLOW_LOCAL_INFRA = os.environ.get('ALLOW_LOCAL_INFRA', '').lower() in ('1', 'true', 'yes')

    # SMTP / transactional email (password reset, etc.)
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or None
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes')
    MAIL_USE_SSL = os.environ.get('MAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or None
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or None
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'no-reply@oplyra.com')
    # When True, skip real SMTP (tests / local); Celery still runs eagerly
    MAIL_SUPPRESS_SEND = os.environ.get('MAIL_SUPPRESS_SEND', '').lower() in ('1', 'true', 'yes')

    # When True, schema is managed exclusively via Alembic (no create_all).
    USE_ALEMBIC_ONLY = False

    # Platform Admin — legacy allowlist used only for bootstrap email hint
    PLATFORM_ADMIN_EMAILS = [
        e.strip().lower()
        for e in os.environ.get('PLATFORM_ADMIN_EMAILS', '').split(',')
        if e.strip()
    ]
    # Internal Admin (RBAC) — separate identity from customer User
    INTERNAL_ADMIN_BOOTSTRAP_EMAIL = (
        os.environ.get('INTERNAL_ADMIN_BOOTSTRAP_EMAIL', '').strip().lower() or None
    )
    INTERNAL_ADMIN_BOOTSTRAP_PASSWORD = os.environ.get('INTERNAL_ADMIN_BOOTSTRAP_PASSWORD') or None
    # Comma-separated hosts allowed to serve /admin (empty = path mode, any host)
    ADMIN_HOSTS = [
        h.strip().lower()
        for h in os.environ.get('ADMIN_HOSTS', '').split(',')
        if h.strip()
    ]
    ADMIN_SESSION_HOURS = int(os.environ.get('ADMIN_SESSION_HOURS', '8'))
    ADMIN_REMEMBER_HOURS = int(os.environ.get('ADMIN_REMEMBER_HOURS', str(24 * 14)))
    ADMIN_MAX_FAILED_LOGINS = int(os.environ.get('ADMIN_MAX_FAILED_LOGINS', '5'))
    ADMIN_LOCKOUT_MINUTES = int(os.environ.get('ADMIN_LOCKOUT_MINUTES', '15'))
    # When true (or DEBUG), re-hash bootstrap admin from INTERNAL_ADMIN_BOOTSTRAP_PASSWORD
    INTERNAL_ADMIN_BOOTSTRAP_RESET_PASSWORD = os.environ.get(
        'INTERNAL_ADMIN_BOOTSTRAP_RESET_PASSWORD', ''
    ).lower() in ('1', 'true', 'yes')

    @staticmethod
    def init_app(app):
        os.makedirs(Config.EXPORT_FOLDER, exist_ok=True)
        os.makedirs(Config.KNOWLEDGE_UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.OBJECT_STORAGE_ROOT, exist_ok=True)


class DevelopmentConfig(Config):
    """Development Configuration"""
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://root:password@localhost:3306/oplyra'
    )
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '5')),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', '10')),
    }


class TestingConfig(Config):
    """Testing Configuration"""
    TESTING = True
    SECRET_KEY = 'test-secret-key-for-unittest-only-32b'
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'TEST_DATABASE_URL',
        'sqlite:///:memory:'
    )
    SQLALCHEMY_ENGINE_OPTIONS = {}
    WTF_CSRF_ENABLED = False
    CELERY_TASK_ALWAYS_EAGER = True
    REDIS_FORCE_MEMORY = True
    STORAGE_PROVIDER = 'local'
    KNOWLEDGE_VECTOR_PROVIDER = 'local'
    STRUCTURED_LOGGING = False
    MAIL_SERVER = None
    MAIL_SUPPRESS_SEND = True
    # Force AI Gateway mock mode so tests never hit the live Gemini API
    # (the "your_" prefix triggers deterministic mock responses).
    GEMINI_API_KEY = 'your_mock_key'
    OPENAI_API_KEY = 'your_mock_openai'
    ANTHROPIC_API_KEY = 'your_mock_anthropic'
    DEEPSEEK_API_KEY = 'your_mock_deepseek'
    INTERNAL_ADMIN_BOOTSTRAP_EMAIL = 'admin@oplyra.test'
    INTERNAL_ADMIN_BOOTSTRAP_PASSWORD = 'AdminBootstrap1!'
    PLATFORM_ADMIN_EMAILS = ['admin@oplyra.test']


class ProductionConfig(Config):
    """Production Configuration — fail-closed on secrets and DB."""
    DEBUG = False
    TESTING = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    USE_ALEMBIC_ONLY = True
    STRUCTURED_LOGGING = True
    # Prefer cloud defaults — override explicitly if needed
    STORAGE_PROVIDER = os.environ.get('STORAGE_PROVIDER', 's3')
    KNOWLEDGE_VECTOR_PROVIDER = os.environ.get('KNOWLEDGE_VECTOR_PROVIDER', 'qdrant')
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
        'pool_size': int(os.environ.get('DB_POOL_SIZE', '20')),
        'max_overflow': int(os.environ.get('DB_MAX_OVERFLOW', '40')),
    }

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        from app.utils.security import is_weak_secret_key

        secret = app.config.get('SECRET_KEY') or os.environ.get('SECRET_KEY')
        if is_weak_secret_key(secret):
            raise RuntimeError(
                'Production SECRET_KEY is missing or weak. '
                'Set a random SECRET_KEY of at least 32 characters.'
            )
        app.config['SECRET_KEY'] = secret

        if not app.config.get('SQLALCHEMY_DATABASE_URI'):
            raise RuntimeError(
                'Production DATABASE_URL is required. '
                'Set DATABASE_URL before starting the application.'
            )

        allow_local = app.config.get('ALLOW_LOCAL_INFRA')
        if not allow_local:
            if (app.config.get('KNOWLEDGE_VECTOR_PROVIDER') or 'local').lower() == 'local':
                raise RuntimeError(
                    'Production forbids local vector search. '
                    'Set KNOWLEDGE_VECTOR_PROVIDER to qdrant|pinecone|weaviate|pgvector '
                    'or ALLOW_LOCAL_INFRA=true for emergency override.'
                )
            if (app.config.get('STORAGE_PROVIDER') or 'local').lower() == 'local':
                raise RuntimeError(
                    'Production forbids local file storage. '
                    'Set STORAGE_PROVIDER to s3|gcs|azure '
                    'or ALLOW_LOCAL_INFRA=true for emergency override.'
                )


# Dictionary mapping configurations
config_by_name = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
