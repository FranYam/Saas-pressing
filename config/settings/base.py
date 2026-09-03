"""
Settings communs à tous les environnements.

Toute la configuration sensible est lue depuis l'environnement (fichier
`.env` via django-environ) : rien n'est codé en dur ici. Les variantes
d'environnement vivent dans `dev.py` et `prod.py`.
"""
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ACCESS_TOKEN_LIFETIME_MINUTES=(int, 60),
    REFRESH_TOKEN_LIFETIME_DAYS=(int, 7),
)

# Lit le fichier `.env` s'il existe (développement local). En production,
# les variables viennent directement de l'environnement du processus.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-cle-de-dev-uniquement")

DEBUG = env("DEBUG")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
]

# Une app par domaine métier — voir docs/architecture (structure-projet-pressing-saas.md)
LOCAL_APPS = [
    "apps.core",
    "apps.tenants",
    "apps.accounts",
    "apps.clients",
    "apps.orders",
    "apps.payments",
    "apps.deliveries",
    "apps.payments_gateway",
    "apps.notifications",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise (fichiers statiques) est inséré ici par prod.py, juste après
    # SecurityMiddleware — inutile en dev où Django sert les statiques.
    "corsheaders.middleware.CorsMiddleware",
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

# ---------------------------------------------------------------------------
# Base de données — PostgreSQL via DATABASE_URL (Neon + pooler PgBouncer)
# ---------------------------------------------------------------------------
# En dev local, si DATABASE_URL est absente, on bascule sur SQLite pour
# pouvoir lancer migrate/tests sans infrastructure.
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{(BASE_DIR / 'db.sqlite3').as_posix()}",
    ),
}

if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    # Compatible pooler PgBouncer en mode transaction :
    # - connexions non persistantes côté Django ;
    # - curseurs côté serveur désactivés (incompatibles avec PgBouncer).
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# ---------------------------------------------------------------------------
# Authentification — JWT (méthode principale de l'API)
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Protégé par défaut : les vues publiques (login, inscription, webhooks)
    # déclarent explicitement AllowAny.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.StandardResultsSetPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env("ACCESS_TOKEN_LIFETIME_MINUTES")),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env("REFRESH_TOKEN_LIFETIME_DAYS")),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "UPDATE_LAST_LOGIN": True,
}

# ---------------------------------------------------------------------------
# Documentation OpenAPI (drf-spectacular)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    "TITLE": "SaaS Pressing API",
    "DESCRIPTION": (
        "API multi-tenant de gestion de pressings (commandes, paiements, "
        "notifications SMS, livraison) pour le marché du Burkina Faso."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SWAGGER_UI_SETTINGS": {"persistAuthorization": True},
    # NB : 2 avertissements de nommage d'enum (« status ») sont connus et
    # cosmétiques — le schéma généré est correct.
}

# ---------------------------------------------------------------------------
# CORS — la PWA consomme l'API depuis un navigateur
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# i18n / fuseau — le Burkina Faso est à UTC+0
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Fichiers statiques & médias (logos des pressings)
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Validation des mots de passe
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Passerelle Mobile Money (Issue #9) — Orange Money / Moov Money
# Valeurs vides par défaut : l'initiation échoue proprement (503/400) tant
# que l'opérateur n'est pas configuré. Jamais de secrets en dur ici.
# ---------------------------------------------------------------------------
MOBILE_MONEY = {
    "ORANGE": {
        "API_URL": env("ORANGE_MONEY_API_URL", default=""),
        "API_KEY": env("ORANGE_MONEY_API_KEY", default=""),
        "WEBHOOK_SECRET": env("ORANGE_WEBHOOK_SECRET", default=""),
    },
    "MOOV": {
        "API_URL": env("MOOV_MONEY_API_URL", default=""),
        "API_KEY": env("MOOV_MONEY_API_KEY", default=""),
        "WEBHOOK_SECRET": env("MOOV_WEBHOOK_SECRET", default=""),
    },
}

# ---------------------------------------------------------------------------
# Passerelle SMS (Issue #10) — agrégateur local/régional.
# URL vide = mode simulation : les SMS sont journalisés (SIMULATED) mais
# jamais envoyés — idéal en dev/pilote sans agrégateur.
# ---------------------------------------------------------------------------
SMS_GATEWAY = {
    "API_URL": env("SMS_API_URL", default=""),
    "API_KEY": env("SMS_API_KEY", default=""),
    "SENDER_ID": env("SMS_SENDER_ID", default=""),
}

# ---------------------------------------------------------------------------
# Logs
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
