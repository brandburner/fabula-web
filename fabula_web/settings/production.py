"""
Production settings for Fabula Web (Railway deployment).
"""

import os
import dj_database_url
from .base import *

DEBUG = False

ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',')

# Database from Railway
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True
    )
}

# Security settings for production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# WhiteNoise for static files — hashed immutable URLs + gzip/brotli.
# Django 5.x form: STATICFILES_STORAGE was removed in 5.1 (ISS-022).
STORAGES = {
    'default': {
        'BACKEND': 'django.core.files.storage.FileSystemStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Wagtail
WAGTAILADMIN_BASE_URL = os.environ.get('WAGTAILADMIN_BASE_URL', 'https://fabula.productions')

# Umami Analytics (set these env vars after deploying Umami on Railway)
UMAMI_SCRIPT_URL = os.environ.get('UMAMI_SCRIPT_URL', '')
UMAMI_WEBSITE_ID = os.environ.get('UMAMI_WEBSITE_ID', '')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Page cache shared across processes (lens review, Phase 3). cache_page
# entries must be reachable by BOTH gunicorn workers and by management
# commands (import_fabula clears the cache after every import) — the
# default LocMemCache is per-process, so a CLI clear never reached the
# serving workers and pages stayed stale for up to 24h. DatabaseCache
# rides the existing PostgreSQL instance; the table is created by
# `createcachetable` in the deploy startCommand (idempotent).
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    }
}
