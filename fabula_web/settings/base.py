"""
Base settings for Fabula Web project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-change-me')

INSTALLED_APPS = [
    # Wagtail apps
    'wagtail.contrib.forms',
    'wagtail.contrib.redirects',
    'wagtail.embeds',
    'wagtail.sites',
    'wagtail.users',
    'wagtail.snippets',
    'wagtail.documents',
    'wagtail.images',
    'wagtail.search',
    'wagtail.admin',
    'wagtail',

    'modelcluster',
    'taggit',

    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',

    # Third party
    'django_extensions',

    # Project apps
    'narrative',
    'marketing',
    'chat',
    'adventure',
]

MIDDLEWARE = [
    'fabula_web.middleware.WwwRedirectMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'wagtail.contrib.redirects.middleware.RedirectMiddleware',
]

ROOT_URLCONF = 'fabula_web.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'marketing.context_processors.series_context',
                'narrative.context_processors.theme_context',
                'chat.context_processors.chat_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'fabula_web.wsgi.application'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
# Dev/tests use Django's default static storage; production.py opts into
# WhiteNoise manifest storage via STORAGES (STATICFILES_STORAGE was removed
# in Django 5.1 and is silently ignored — ISS-022).

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Wagtail settings
WAGTAIL_SITE_NAME = 'Fabula'
WAGTAILADMIN_BASE_URL = os.environ.get('WAGTAILADMIN_BASE_URL', 'http://localhost:8000')

# Search backend
WAGTAILSEARCH_BACKENDS = {
    'default': {
        'BACKEND': 'wagtail.search.backends.database',
    }
}

# =============================================================================
# CHARACTER IMPORTANCE TIER THRESHOLDS (Graph Gravity)
# =============================================================================
# These thresholds determine how characters are classified into importance tiers.
# A character qualifies for a tier if they meet EITHER the episode OR relationship threshold.

# Anchor tier (main cast): High narrative importance
TIER_ANCHOR_MIN_EPISODES = int(os.environ.get('TIER_ANCHOR_MIN_EPISODES', 5))
TIER_ANCHOR_MIN_RELATIONSHIPS = int(os.environ.get('TIER_ANCHOR_MIN_RELATIONSHIPS', 20))

# Planet tier (recurring): Moderate narrative importance
TIER_PLANET_MIN_EPISODES = int(os.environ.get('TIER_PLANET_MIN_EPISODES', 2))
TIER_PLANET_MIN_RELATIONSHIPS = int(os.environ.get('TIER_PLANET_MIN_RELATIONSHIPS', 5))

# Asteroid tier: Everything below Planet thresholds (default tier)

# =============================================================================
# ASK THE ARCHIVE — conversational layer over the narrative graph
# =============================================================================
# docs/CHAT_INTERACTIVITY_ARCHITECTURE_BRIEF.md. The endpoint is disabled
# unless a key is configured (or the fake backend is selected for local
# widget development / tests). Spend cap lives on the OpenRouter key itself
# — set it BEFORE exposing the endpoint publicly (brief §4.6).
CHAT_OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
CHAT_LLM_BACKEND = os.environ.get('CHAT_LLM_BACKEND', 'openrouter')
CHAT_ENABLED = bool(CHAT_OPENROUTER_API_KEY) or CHAT_LLM_BACKEND == 'fake'
CHAT_MODEL = os.environ.get('CHAT_MODEL', 'google/gemini-2.5-flash')
CHAT_MAX_TOKENS = int(os.environ.get('CHAT_MAX_TOKENS', 2048))
# Narrative prose breathes a little more than compliance answers (~0.5 vs
# the prior art's 0.3); facts stay grounded by tool discipline, not temp.
CHAT_TEMPERATURE = float(os.environ.get('CHAT_TEMPERATURE', 0.5))
CHAT_RATE_LIMIT_PER_MINUTE = int(os.environ.get('CHAT_RATE_LIMIT_PER_MINUTE', 10))
CHAT_RATE_LIMIT_PER_HOUR = int(os.environ.get('CHAT_RATE_LIMIT_PER_HOUR', 60))

# Local story-terminal prototype. Production requires explicit enablement.
ADVENTURE_ENABLED = os.environ.get('ADVENTURE_ENABLED', '0') == '1'
ADVENTURE_AUTHOR_BACKEND = os.environ.get('ADVENTURE_AUTHOR_BACKEND', 'local')
ADVENTURE_MODEL = os.environ.get('ADVENTURE_MODEL', CHAT_MODEL)
# Projected worlds: episodes read straight from the narrative graph into a
# walkable terminal world (adventure/projection.py). Slug -> published episode.
ADVENTURE_WORLDS = [
    {'slug': 'wolf-hall-e1', 'series': 'wolf-hall', 'season': 1, 'episode': 1, 'number': '002'},
]
