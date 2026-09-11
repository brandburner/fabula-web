"""
Sitemap host pinning (ISS-030).

Every <loc> must be on the canonical apex host regardless of which host the
request arrived on, and regardless of Railway's RAILWAY_PUBLIC_DOMAIN (which
is the www. custom domain — a host the site 301s away from).
"""

from django.core.cache import cache
from django.test import TestCase, override_settings


@override_settings(
    ALLOWED_HOSTS=["*"],
    WAGTAILADMIN_BASE_URL="https://fabula.productions",
)
class SitemapHostTests(TestCase):

    def setUp(self):
        cache.clear()

    def _assert_apex_only(self, body):
        self.assertIn("https://fabula.productions/", body)
        self.assertNotIn("www.fabula.productions", body)
        self.assertNotIn("testserver", body)

    def test_www_host_is_redirected_before_the_sitemap_renders(self):
        # WwwRedirectMiddleware owns www.; the pin covers every *other* alias.
        resp = self.client.get("/sitemap.xml", HTTP_HOST="www.fabula.productions")
        self.assertEqual(resp.status_code, 301)
        self.assertEqual(resp["Location"], "https://fabula.productions/sitemap.xml")

    def test_index_uses_apex_even_when_fetched_via_alias_host(self):
        resp = self.client.get("/sitemap.xml", HTTP_HOST="testserver")
        self.assertEqual(resp.status_code, 200)
        self._assert_apex_only(resp.content.decode())

    def test_section_uses_apex_even_when_fetched_via_railway_host(self):
        resp = self.client.get(
            "/sitemap-pages.xml", HTTP_HOST="fabula-web-production.up.railway.app")
        self.assertEqual(resp.status_code, 200)
        self._assert_apex_only(resp.content.decode())

    def test_canonical_host_ignores_railway_public_domain(self):
        import os
        from unittest import mock
        from fabula_web.urls import canonical_host
        with mock.patch.dict(os.environ, {"RAILWAY_PUBLIC_DOMAIN": "www.fabula.productions"}):
            self.assertEqual(canonical_host(), "fabula.productions")
