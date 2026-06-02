"""
Sitemaps for Fabula.

The site has ~165k indexable URLs. Almost all navigable content (events,
objects, characters, organizations, episodes, series) is **served by custom
Django views** (see narrative/urls.py) at canonical URLs returned by each
model's `get_absolute_url()` — NOT by Wagtail's page-tree routing. The series
subtrees are also siblings of the Wagtail site root, so Wagtail's built-in
tree sitemap only ever emitted ~14 marketing pages. This module therefore
builds explicit per-type sitemaps from `get_absolute_url()`.

Because the total is far over the 50k-URL / 50MB per-file spec limit,
`/sitemap.xml` is served as a **sitemap index** (see fabula_web/urls.py) and
each section is capped at `limit` URLs per file.

Two correctness invariants every Sitemap here upholds:

- An efficient `get_latest_lastmod()`. The index view calls it once per
  section; the default implementation iterates *every* item (catastrophic at
  36k events), so we override it with a single aggregate query.
- A stable `order_by()` on `items()`. Without it Postgres may return rows in a
  different order per request and the paginated sub-sitemaps would overlap /
  drop URLs.
"""

from django.contrib.sitemaps import Sitemap
from django.db.models import Max
from django.urls import reverse

from .models import (
    NarrativeConnection, Theme, ConflictArc, Location,
    SeriesIndexPage, EpisodePage, CharacterPage, OrganizationPage,
    ObjectPage, EventPage,
)


# ---------------------------------------------------------------------------
# Wagtail-page content (served via custom get_absolute_url views)
# ---------------------------------------------------------------------------

class _PageSitemap(Sitemap):
    """Base for live Wagtail pages whose canonical URL comes from
    `get_absolute_url()` (global_id-based), not the page tree."""

    protocol = "https"
    changefreq = "monthly"
    limit = 10000
    model = None  # set by subclass

    def items(self):
        return (
            self.model.objects.live()
            .only("global_id", "fabula_uuid",
                  "last_published_at", "latest_revision_created_at")
            .order_by("pk")
        )

    def lastmod(self, obj):
        return obj.last_published_at or obj.latest_revision_created_at

    def location(self, obj):
        return obj.get_absolute_url()

    def get_latest_lastmod(self):
        return self.model.objects.live().aggregate(m=Max("last_published_at"))["m"]


class CharacterSitemap(_PageSitemap):
    model = CharacterPage
    priority = 0.7


class OrganizationSitemap(_PageSitemap):
    model = OrganizationPage
    priority = 0.6


class ObjectSitemap(_PageSitemap):
    model = ObjectPage
    priority = 0.5


class EventSitemap(_PageSitemap):
    model = EventPage
    priority = 0.7


class SeriesSitemap(Sitemap):
    """Series landing pages — served at /explore/<slug>/ (no get_absolute_url
    on the model)."""

    protocol = "https"
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return SeriesIndexPage.objects.live().order_by("pk")

    def lastmod(self, obj):
        return obj.last_published_at or obj.latest_revision_created_at

    def location(self, obj):
        return f"/explore/{obj.slug}/"

    def get_latest_lastmod(self):
        return SeriesIndexPage.objects.live().aggregate(m=Max("last_published_at"))["m"]


class EpisodeSitemap(Sitemap):
    """Episode detail pages — served at /explore/<series-slug>/episodes/<id>/.
    EpisodePage has no get_absolute_url and no direct series link, so we resolve
    the owning series by Wagtail tree path prefix (built once per render)."""

    protocol = "https"
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        # Map series tree-path -> slug once; episode paths are prefixed by the
        # path of their ancestor series (series=depth2, episode=depth4).
        self._series_by_path = {
            s.path: s.slug
            for s in SeriesIndexPage.objects.live().only("path", "slug")
        }
        eps = (
            EpisodePage.objects.live()
            .only("path", "fabula_uuid",
                  "last_published_at", "latest_revision_created_at")
            .order_by("path")
        )
        # Skip any episode whose owning series isn't live/resolvable — emitting
        # /explore/None/episodes/... would be a broken URL.
        return [e for e in eps if self._series_slug(e) is not None]

    def _series_slug(self, obj):
        for path, slug in self._series_by_path.items():
            if obj.path.startswith(path):
                return slug
        return None

    def location(self, obj):
        slug = self._series_slug(obj)
        ident = obj.fabula_uuid or obj.pk
        return f"/explore/{slug}/episodes/{ident}/"

    def lastmod(self, obj):
        return obj.last_published_at or obj.latest_revision_created_at

    def get_latest_lastmod(self):
        return EpisodePage.objects.live().aggregate(m=Max("last_published_at"))["m"]


# ---------------------------------------------------------------------------
# Snippet / Django-model content (updated_at timestamps)
# ---------------------------------------------------------------------------

class ConnectionSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6
    protocol = "https"
    limit = 10000

    def items(self):
        # location() needs only global_id/fabula_uuid/pk; lastmod needs
        # updated_at. No select_related — the join to from/to_event was wasted.
        return (
            NarrativeConnection.objects
            .only("global_id", "fabula_uuid", "updated_at")
            .order_by("pk")
        )

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()

    def get_latest_lastmod(self):
        return NarrativeConnection.objects.aggregate(m=Max("updated_at"))["m"]


class ThemeSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5
    protocol = "https"

    def items(self):
        return Theme.objects.order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()

    def get_latest_lastmod(self):
        return Theme.objects.aggregate(m=Max("updated_at"))["m"]


class ArcSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5
    protocol = "https"

    def items(self):
        return ConflictArc.objects.order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()

    def get_latest_lastmod(self):
        return ConflictArc.objects.aggregate(m=Max("updated_at"))["m"]


class LocationSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.4
    protocol = "https"
    limit = 10000

    def items(self):
        return Location.objects.order_by("pk")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        return obj.get_absolute_url()

    def get_latest_lastmod(self):
        return Location.objects.aggregate(m=Max("updated_at"))["m"]


# ---------------------------------------------------------------------------
# Marketing pages
# ---------------------------------------------------------------------------

# Served paths owned by the v2 marketing routes (marketing/urls.py), which
# shadow the legacy Wagtail pages of the same path. '/' and '/about/' are in
# StaticViewSitemap; '/platform/' 301-redirects to /engine/. Excluded here to
# avoid duplicate / redirecting <loc> entries.
_V2_OWNED_PATHS = {"/", "/about/", "/platform/"}


class MarketingTreeSitemap(Sitemap):
    """The legacy (v1) marketing pages still live under the default Wagtail site
    root (Product, Pricing, FAQ, Use Cases, Benchmarks, ...), served by
    Wagtail's catch-all.

    We deliberately do NOT use wagtail.contrib.sitemaps here: this deployment's
    Wagtail Site hostname is the Railway wildcard '*', so Wagtail's
    `get_full_url()` produces broken `http://*/...` URLs (the old sitemap shipped
    exactly that). Instead we emit relative paths and let Django apply
    protocol='https' + the request host, matching every other sitemap."""

    protocol = "https"
    changefreq = "monthly"
    priority = 0.6

    def _root(self):
        from wagtail.models import Site
        return Site.objects.get(is_default_site=True).root_page

    def _served_path(self, page, root_url_path):
        # Wagtail url_path is the tree path ('/fabula/product/'); the served URL
        # strips the site-root page's url_path prefix ('/fabula/').
        return "/" + page.url_path[len(root_url_path):]

    def items(self):
        from django.contrib.contenttypes.models import ContentType
        from marketing.models import UseCasePage

        root = self._root()
        self._root_url_path = root.url_path
        pages = (
            root.get_descendants(inclusive=True).live().public()
            # UseCasePage detail pages currently 500 on prod — never sitemap a
            # broken URL. The /use-cases/ index (UseCasesIndexPage) is fine.
            .exclude(content_type=ContentType.objects.get_for_model(UseCasePage))
            .only("url_path", "last_published_at", "latest_revision_created_at")
            .order_by("path")
        )
        return [
            p for p in pages
            if self._served_path(p, self._root_url_path) not in _V2_OWNED_PATHS
        ]

    def location(self, obj):
        return self._served_path(obj, self._root_url_path)

    def lastmod(self, obj):
        return obj.last_published_at or obj.latest_revision_created_at

    def get_latest_lastmod(self):
        return (
            self._root().get_descendants(inclusive=True)
            .live().public()
            .aggregate(m=Max("last_published_at"))["m"]
        )


# ---------------------------------------------------------------------------
# Static marketing pages (highest-value SEO surface, previously absent)
# ---------------------------------------------------------------------------

class StaticViewSitemap(Sitemap):
    """The v2 marketing landing pages. Static templates, so no per-page
    lastmod; priority/changefreq tuned by hand."""

    protocol = "https"
    changefreq = "weekly"

    _pages = {
        "v2_home": 1.0,
        "v2_engine": 0.9,
        "v2_production": 0.9,
        "v2_about": 0.7,
        "v2_investors": 0.7,
    }

    def items(self):
        return list(self._pages.keys())

    def priority(self, item):
        return self._pages[item]

    def location(self, item):
        return reverse(item)
