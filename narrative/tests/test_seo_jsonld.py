"""
JSON-LD @id resolvability (ISS-026).

Every @id / url the seo_tags emit must be an absolute, resolvable URL that
matches the page's <link rel=canonical>. Two historical failure modes are
pinned here: "bound method" (get_host not called) and "None" (Page.url is None
for custom-routed narrative pages).
"""

import json
import re

from django.template import Context, Template
from django.test import RequestFactory, TestCase, override_settings

from narrative.url_utils import canonical_path_for
from .test_views import ViewTestMixin

ABSOLUTE = re.compile(r"^https://[^/]+/")
SCRIPT = re.compile(r"<script[^>]*>(.*?)</script>", re.S)


@override_settings(WAGTAILADMIN_BASE_URL="https://fabula.productions")
class JsonLdIdTests(ViewTestMixin, TestCase):

    def _render(self, tag, obj, extra=None):
        request = RequestFactory().get("/", HTTP_HOST="testserver")
        ctx = {"request": request, "page": obj}
        ctx.update(extra or {})
        tpl = Template("{% load seo_tags %}{% " + tag + " page %}")
        html = tpl.render(Context(ctx))
        body = SCRIPT.search(html).group(1)
        return json.loads(body)

    def _walk_ids(self, node, out):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("@id", "url", "item") and isinstance(v, str):
                    out.append(v)
                self._walk_ids(v, out)
        elif isinstance(node, list):
            for i in node:
                self._walk_ids(i, out)
        return out

    def _walk_types(self, node, out):
        if isinstance(node, dict):
            if "@type" in node:
                out.append(node["@type"])
            for v in node.values():
                self._walk_types(v, out)
        elif isinstance(node, list):
            for i in node:
                self._walk_types(i, out)
        return out

    def _assert_schema_org_character_typing(self, data):
        """schema.org has no FictionalCharacter type; character nodes must be
        Person (schema.org meaning) + fabula:FictionalCharacter (ISS-031)."""
        types = self._walk_types(data, [])
        self.assertNotIn("FictionalCharacter", types)
        self.assertIn(["Person", "fabula:FictionalCharacter"], types)

    def _assert_resolvable(self, data, page):
        ids = self._walk_ids(data, [])
        self.assertTrue(ids)
        for value in ids:
            self.assertNotIn("None", value, value)
            self.assertNotIn("bound method", value, value)
            self.assertNotIn("testserver", value, value)
            self.assertRegex(value, ABSOLUTE)
        self.assertEqual(
            data["@graph"][0]["@id"],
            "https://fabula.productions" + canonical_path_for(page),
        )
        return ids

    def test_series(self):
        data = self._render("series_jsonld", self.series,
                            {"seasons": [self.season]})
        ids = self._assert_resolvable(data, self.series)
        self.assertIn("https://fabula.productions/explore/test-series/#season-1", ids)

    def test_episode(self):
        data = self._render("episode_jsonld", self.episode)
        ids = self._assert_resolvable(data, self.episode)
        self.assertIn("https://fabula.productions/explore/test-series/", ids)

    def test_character(self):
        data = self._render("character_jsonld", self.character)
        self._assert_resolvable(data, self.character)
        self._assert_schema_org_character_typing(data)

    def test_event(self):
        data = self._render("event_jsonld", self.event1)
        ids = self._assert_resolvable(data, self.event1)
        self._assert_schema_org_character_typing(data)
        # Connection endpoint and participant ids are series-scoped too.
        self.assertIn(
            "https://fabula.productions" + canonical_path_for(self.event2), ids)
        self.assertIn(
            "https://fabula.productions" + canonical_path_for(self.character), ids)

    def test_connection(self):
        request = RequestFactory().get("/")
        tpl = Template("{% load seo_tags %}{% connection_jsonld connection %}")
        html = tpl.render(Context({"request": request, "connection": self.connection}))
        data = json.loads(SCRIPT.search(html).group(1))
        ids = self._walk_ids(data, [])
        for value in ids:
            self.assertNotIn("None", value, value)
            self.assertRegex(value, ABSOLUTE)
        self.assertEqual(
            data["@graph"][0]["fabula:fromEvent"]["@id"],
            "https://fabula.productions" + canonical_path_for(self.event1),
        )

    def test_series_slug_from_context_skips_ancestry_query(self):
        with self.assertNumQueries(0):
            from narrative.templatetags.seo_tags import _series_slug
            self.assertEqual(
                _series_slug({"series_slug": "x"}, self.event1), "x")
