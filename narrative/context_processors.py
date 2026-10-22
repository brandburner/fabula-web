"""
Theme context processor for Fabula.

Switch themes by appending ?theme=writerly or ?theme=dark to any URL;
ThemeCookieMiddleware stores the choice in a cookie and redirects.
"""

from django.conf import settings

from .theme import get_theme


def theme_context(request):
    """
    Add theme context to all templates.

    Theme comes from the ``fabula_theme`` cookie (see narrative/theme.py),
    defaulting to 'writerly'. Deliberately never touches request.session:
    reading it marks every response ``Vary: Cookie`` and writing it created
    a DB row per crawler hit on a ?theme= link.
    """
    theme = get_theme(request)

    return {
        'fabula_theme': theme,
        'is_dark_theme': theme == 'dark',
        'is_writerly_theme': theme == 'writerly',
        'umami_url': getattr(settings, 'UMAMI_SCRIPT_URL', ''),
        'umami_website_id': getattr(settings, 'UMAMI_WEBSITE_ID', ''),
    }
