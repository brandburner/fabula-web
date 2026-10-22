"""
Theme selection for Fabula (writerly / dark).

The theme lives in a plain ``fabula_theme`` cookie, set by
``fabula_web.middleware.ThemeCookieMiddleware`` when a ``?theme=`` link is
followed. It used to live in the DB session, which meant every crawler that
followed the per-page ``?theme=`` toggle links (they never return cookies)
minted a new ``django_session`` row — 9M rows / 2.8 GB by Oct 2026, every
one of them ``{"fabula_theme": ...}``.
"""

THEMES = ('writerly', 'dark')
DEFAULT_THEME = 'writerly'
THEME_COOKIE = 'fabula_theme'
THEME_COOKIE_MAX_AGE = 60 * 60 * 24 * 365


def get_theme(request):
    """Return the request's theme from its cookie, falling back to writerly."""
    theme = request.COOKIES.get(THEME_COOKIE)
    return theme if theme in THEMES else DEFAULT_THEME
