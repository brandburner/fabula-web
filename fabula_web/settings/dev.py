"""
Development settings for Fabula Web.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Use SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Optional: Use PostgreSQL in dev too
# import dj_database_url
# DATABASES = {
#     'default': dj_database_url.config(
#         default='postgres://localhost/fabula_web'
#     )
# }

# Debug toolbar (optional)
# INSTALLED_APPS += ['debug_toolbar']
# MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
# INTERNAL_IPS = ['127.0.0.1']

# Email backend for dev
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Simplified static files for dev
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.StaticFilesStorage'
