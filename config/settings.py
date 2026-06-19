import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "0" if os.environ.get("VERCEL") else "1") == "1"

ALLOWED_HOSTS = ["127.0.0.1", "localhost", ".localhost", ".vercel.app"]
if os.environ.get("VERCEL_URL"):
    ALLOWED_HOSTS.append(os.environ["VERCEL_URL"])
ALLOWED_HOSTS += [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

CSRF_TRUSTED_ORIGINS = ["https://*.vercel.app"]
CSRF_TRUSTED_ORIGINS += [
    origin.strip()
    for origin in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "storages",
    "loja",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "loja.middleware.TenantMiddleware",
    "loja.middleware.MaintenanceModeMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default=0):
    value = os.environ.get(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def database_from_url(database_url):
    parsed = urlparse(database_url)
    if parsed.scheme in {"postgres", "postgresql"}:
        allowed_options = {
            "application_name",
            "channel_binding",
            "connect_timeout",
            "gssencmode",
            "keepalives",
            "keepalives_count",
            "keepalives_idle",
            "keepalives_interval",
            "options",
            "sslcert",
            "sslkey",
            "sslmode",
            "sslrootcert",
            "target_session_attrs",
            "tcp_user_timeout",
        }
        options = {
            key: value
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key in allowed_options
        }
        options.setdefault("sslmode", os.environ.get("DATABASE_SSLMODE", "require"))

        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname or "",
            "PORT": str(parsed.port or ""),
            "CONN_MAX_AGE": env_int("DATABASE_CONN_MAX_AGE", 0),
            "CONN_HEALTH_CHECKS": env_bool("DATABASE_CONN_HEALTH_CHECKS", True),
            "DISABLE_SERVER_SIDE_CURSORS": env_bool("DATABASE_DISABLE_SERVER_SIDE_CURSORS", True),
            "OPTIONS": options,
        }
    if parsed.scheme == "sqlite":
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": parsed.path or BASE_DIR / "db.sqlite3",
        }
    raise ValueError("DATABASE_URL precisa ser postgres://, postgresql:// ou sqlite:///")


DATABASE_URL = (
    os.environ.get("SUPABASE_DATABASE_URL")
    or os.environ.get("SUPABASE_POSTGRES_URL")
)
DATABASES = {
    "default": database_from_url(DATABASE_URL)
    if DATABASE_URL
    else {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "loja.validators.UppercasePasswordValidator"},
    {"NAME": "loja.validators.SpecialCharacterPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Fortaleza"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_STORAGE_BUCKET = os.environ.get("SUPABASE_STORAGE_BUCKET", "vestlink-media")
SUPABASE_STORAGE_KEY = (
    os.environ.get("SUPABASE_STORAGE_KEY")
    or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    or os.environ.get("SUPABASE_SECRET_KEY")
)
SUPABASE_STORAGE_TIMEOUT_SECONDS = env_int("SUPABASE_STORAGE_TIMEOUT_SECONDS", 20)
USE_SUPABASE_STORAGE = env_bool(
    "SUPABASE_STORAGE_ENABLED",
    bool(os.environ.get("VERCEL") and SUPABASE_URL and SUPABASE_STORAGE_KEY),
)

# Configuração de Armazenamento de Mídia em Nuvem (S3/Supabase/R2)
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY")
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME")
AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME")
AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL")
AWS_S3_CUSTOM_DOMAIN = os.environ.get("AWS_S3_CUSTOM_DOMAIN")

if USE_SUPABASE_STORAGE:
    STORAGES = {
        "default": {
            "BACKEND": "loja.storage.SupabaseStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
elif AWS_STORAGE_BUCKET_NAME:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "painel"
LOGOUT_REDIRECT_URL = "home"

SUPABASE_AUTH_KEY = (
    os.environ.get("SUPABASE_AUTH_KEY")
    or os.environ.get("SUPABASE_ANON_KEY")
    or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
)
SUPABASE_AUTH_EMAIL_CONFIRMATION = env_bool("SUPABASE_AUTH_EMAIL_CONFIRMATION", False)
SUPABASE_EMAIL_REDIRECT_URL = os.environ.get("SUPABASE_EMAIL_REDIRECT_URL", "")
SUPABASE_AUTH_TIMEOUT_SECONDS = env_int("SUPABASE_AUTH_TIMEOUT_SECONDS", 10)

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
RESEND_API_URL = os.environ.get("RESEND_API_URL", "https://api.resend.com/emails")
RESEND_TIMEOUT_SECONDS = env_int("RESEND_TIMEOUT_SECONDS", 10)
RESEND_FROM_EMAIL = os.environ.get("RESEND_FROM_EMAIL", "")

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "loja.email_backends.ResendEmailBackend" if RESEND_API_KEY else "django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
EMAIL_USE_SSL = env_bool("EMAIL_USE_SSL", False)
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL") or RESEND_FROM_EMAIL or "VestLink <contato@vestlink.local>"
VESTLINK_CHECKOUT_URL = os.environ.get("VESTLINK_CHECKOUT_URL", "")
MODALINK_CHECKOUT_URL = VESTLINK_CHECKOUT_URL or os.environ.get("MODALINK_CHECKOUT_URL", "")
VESTLINK_BASE_URL = os.environ.get("VESTLINK_BASE_URL", "")
MODALINK_BASE_URL = VESTLINK_BASE_URL or os.environ.get("MODALINK_BASE_URL", "")
MERCADO_PAGO_ACCESS_TOKEN = os.environ.get("MERCADO_PAGO_ACCESS_TOKEN", "")
MERCADO_PAGO_USE_SANDBOX = os.environ.get("MERCADO_PAGO_USE_SANDBOX", "1") == "1"
VESTLINK_MAINTENANCE = os.environ.get("VESTLINK_MAINTENANCE", "0") == "1"
CRON_SECRET = os.environ.get("CRON_SECRET", "")
LEAD_RETENTION_DAYS = env_int("LEAD_RETENTION_DAYS", 365)
SENTRY_SEND_DEFAULT_PII = env_bool("SENTRY_SEND_DEFAULT_PII", False)

# Diretivas de segurança adicionais para produção
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = "DENY"

# Configuração de Cache (Redis com fallback local)
REDIS_URL = os.environ.get("REDIS_URL")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            }
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "loja-unique-locmem-cache",
        }
    }

# Integração do Sentry
SENTRY_DSN = os.environ.get("SENTRY_DSN")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
        send_default_pii=SENTRY_SEND_DEFAULT_PII,
    )
