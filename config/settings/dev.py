"""Settings de développement local (SQLite par défaut ou branche Neon de dev)."""
from .base import *  # noqa: F401,F403
from .base import env  # noqa

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# En dev local, la PWA tourne sur un serveur Vite/Next : on autorise tout.
CORS_ALLOW_ALL_ORIGINS = True

# django-debug-toolbar (installé via requirements/dev.txt)
INTERNAL_IPS = ["127.0.0.1"]
INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405
MIDDLEWARE = ["debug_toolbar.middleware.DebugToolbarMiddleware"] + MIDDLEWARE  # noqa: F405
