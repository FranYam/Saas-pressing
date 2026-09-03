"""Settings de production (Neon prod, sécurité renforcée, WhiteNoise)."""
from .base import *  # noqa: F401,F403
from .base import env  # noqa

DEBUG = False

# Échec rapide : pas de clé par défaut en production.
SECRET_KEY = env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS")

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ---------------------------------------------------------------------------
# Sécurité (derrière un proxy TLS type Render/Railway/Fly)
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Fichiers statiques servis par WhiteNoise (collectstatic au déploiement).
# WhiteNoise sert les fichiers statiques (collectstatic au déploiement).
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405

STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# Médias persistants (logos...) sur stockage objet S3-compatible — Cloudflare R2
# (10 Go gratuits). Inactif tant que S3_BUCKET_NAME n'est pas défini : sans
# disque persistant chez l'hébergeur, les uploads survivent aux redéploiements.
# ---------------------------------------------------------------------------
if env("S3_BUCKET_NAME", default=""):
    STORAGES = {
        **STORAGES,
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "endpoint_url": env("S3_ENDPOINT_URL"),
                "access_key": env("S3_ACCESS_KEY_ID"),
                "secret_key": env("S3_SECRET_ACCESS_KEY"),
                "bucket_name": env("S3_BUCKET_NAME"),
                # R2 : accès public via l'URL r2.dev du bucket (ou domaine propre).
                "custom_domain": env("S3_CUSTOM_DOMAIN", default="") or None,
                "region_name": env("S3_REGION_NAME", default="auto"),
                "location": "media",
                "url_protocol": "https:",
                "file_overwrite": False,
            },
        },
    }

# ---------------------------------------------------------------------------
# Sentry (optionnel — activé uniquement si SENTRY_DSN est défini)
# ---------------------------------------------------------------------------
SENTRY_DSN = env("SENTRY_DSN", default=None)
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        send_default_pii=False,
        traces_sample_rate=1.0,
    )
