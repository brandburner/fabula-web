"""Project middleware."""

from django.http import HttpResponsePermanentRedirect


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
