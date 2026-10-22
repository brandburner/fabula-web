"""Project middleware."""

from django.http import HttpResponsePermanentRedirect, HttpResponseRedirect
from django.utils.cache import patch_vary_headers

from narrative.theme import THEME_COOKIE, THEME_COOKIE_MAX_AGE, THEMES


class WwwRedirectMiddleware:
    """301-redirect the ``www.`` subdomain to the bare apex host.

    The site is served from both ``fabula.productions`` and
    ``www.fabula.productions`` (both in ALLOWED_HOSTS), which means the same
    content lives at two origins — duplicate content that splits SEO signals.
    This sends ``www`` permanently to the apex, giving a single canonical
    origin. Path, query string, and https are preserved; non-www hosts pass
    through untouched (so localhost/dev is unaffected).

    Placed first in MIDDLEWARE so a www request redirects in a single hop
    (https + apex together) rather than chaining through the SSL redirect.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0]
        if host.startswith('www.'):
            apex = host[4:]
            return HttpResponsePermanentRedirect(
                f'https://{apex}{request.get_full_path()}'
            )
        return self.get_response(request)


class ThemeCookieMiddleware:
    """Store a ``?theme=`` choice in a cookie and redirect to the clean URL.

    Every page links to ``?theme=dark`` / ``?theme=writerly``. Rendering those
    URLs used to save the theme to the DB session, so each crawler hit (no
    cookies returned) cost a full uncached page render plus a new
    ``django_session`` row. Now a toggle is a tiny 302 that sets the cookie
    and lands on the canonical, cacheable URL. 302 rather than 301: browsers
    cache a 301, so the second toggle would never reach the server.

    Also marks HTML responses ``Vary: Cookie``: templates are rendered per
    theme from that cookie, so a shared cache must not serve one theme's
    page to the other. (SessionMiddleware used to add this as a side effect
    of the session read.) Non-HTML responses — sitemaps, robots.txt, JSON —
    stay cookie-independent.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        theme = request.GET.get('theme')
        if request.method in ('GET', 'HEAD') and theme in THEMES:
            params = request.GET.copy()
            params.pop('theme')
            url = request.path
            if params:
                url = f'{url}?{params.urlencode()}'
            response = HttpResponseRedirect(url)
            response.set_cookie(
                THEME_COOKIE, theme,
                max_age=THEME_COOKIE_MAX_AGE,
                samesite='Lax',
                secure=request.is_secure(),
                httponly=True,
            )
            return response

        response = self.get_response(request)
        if response.get('Content-Type', '').startswith('text/html'):
            patch_vary_headers(response, ('Cookie',))
        return response
