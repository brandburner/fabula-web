"""
Theme selection for Fabula (writerly / dark).

The theme lives in a plain ``fabula_theme`` cookie, set by
``fabula_web.middleware.ThemeCookieMiddleware`` when a ``?theme=`` link is
followed. It used to live in the DB session, which meant every crawler that
followed the per-page ``?theme=`` toggle links (they never return cookies)
minted a new ``django_session`` row — 9M rows / 2.8 GB by Oct 2026, every
one of them ``{"fabula_theme": ...}``.
"""

from functools import wraps

from django.views.decorators.cache import cache_page

THEMES = ('writerly', 'dark')
DEFAULT_THEME = 'writerly'
THEME_COOKIE = 'fabula_theme'
THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def get_theme(request):
    """Return the request's theme from its cookie, falling back to writerly."""
    theme = request.COOKIES.get(THEME_COOKIE)
    return theme if theme in THEMES else DEFAULT_THEME


def theme_cache_page(timeout):
    """
    ``cache_page`` with a separate cache namespace per theme.

    Templates branch on the theme server-side, so a cached page has to be
    keyed on it. Plain ``cache_page`` can't see the theme: it learns its key
    from the view's own ``Vary`` headers, before any middleware patches
    ``Vary: Cookie`` — so a dark render could be served to writerly readers
    for 24h. ``vary_on_cookie`` would key on the raw Cookie header instead,
    giving every visitor with a csrftoken/sessionid a private cache row.
    One ``key_prefix`` per theme keeps exactly two variants per URL.
    ``cache.clear()`` (import_fabula) still wipes both.
    """
    def decorator(view_func):
        variants = {
            theme: cache_page(timeout, key_prefix=f'theme-{theme}')(view_func)
            for theme in THEMES
        }

        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            return variants[get_theme(request)](request, *args, **kwargs)
        return _wrapped
    return decorator
