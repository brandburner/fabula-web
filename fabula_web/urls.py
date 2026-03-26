"""
URL configuration for Fabula Web.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
import logging
import os
import re
from pathlib import Path

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.contrib.sitemaps import Sitemap as WagtailSitemap
from wagtail.documents import urls as wagtaildocs_urls

from narrative.sitemaps import (
    ConnectionSitemap, ThemeSitemap, ArcSitemap, LocationSitemap,
)

sitemaps = {
    'wagtail': WagtailSitemap,
    'connections': ConnectionSitemap,
    'themes': ThemeSitemap,
    'arcs': ArcSitemap,
    'locations': LocationSitemap,
}


def robots_txt(request):
    """Serve robots.txt with sitemap reference."""
    lines = [
        "User-agent: *",
        "Allow: /",
        "",
        "Disallow: /admin/",
        "Disallow: /django-admin/",
        "",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def health_check(request):
    """Simple health check endpoint for Railway."""
    return JsonResponse({'status': 'ok'})


def diagnostics(request):
    """Diagnostic endpoint to check data import status."""
    from wagtail.models import Page, Site

    data_dir = Path('fabula_export')

    # Check data directory
    data_exists = data_dir.exists()
    data_files = list(data_dir.glob('*.yaml')) if data_exists else []
    events_dir = data_dir / 'events'
    event_files = list(events_dir.glob('*.yaml')) if events_dir.exists() else []

    # Check database content
    page_count = Page.objects.count()
    pages = list(Page.objects.values_list('title', 'depth', 'path')[:20])

    # Check site configuration
    sites = list(Site.objects.values('hostname', 'root_page_id', 'is_default_site', 'site_name'))

    return JsonResponse({
        'cwd': os.getcwd(),
        'data_dir_exists': data_exists,
        'data_files': [str(f) for f in data_files],
        'event_files_count': len(event_files),
        'page_count': page_count,
        'pages': pages,
        'sites': sites,
    })


def trigger_import(request):
    """Trigger data import (one-time use endpoint)."""
    from django.core.management import call_command
    from wagtail.models import Page
    from io import StringIO

    # Check if already imported
    if Page.objects.count() > 10:
        return JsonResponse({
            'status': 'skipped',
            'message': 'Data already imported',
            'page_count': Page.objects.count()
        })

    try:
        out = StringIO()
        call_command('import_fabula', 'fabula_export/', stdout=out, stderr=out)
        output = out.getvalue()

        return JsonResponse({
            'status': 'success',
            'output': output,
            'page_count': Page.objects.count()
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'traceback': traceback.format_exc()
        }, status=500)


def google_verification(request):
    """Google Search Console verification file."""
    return HttpResponse(
        "google-site-verification: googlea62b51e71cd21b69.html",
        content_type="text/html",
    )


# =============================================================================
# AGENT-FRIENDLY 404
# =============================================================================

logger = logging.getLogger(__name__)

# Patterns that identify AI agents and programmatic fetchers.
# Browsers send things like "Mozilla/5.0 ... Chrome/..." — these won't match.
AGENT_UA_PATTERNS = re.compile(
    r'(ChatGPT|GPTBot|Claude|Anthropic|Perplexity|Cohere|'
    r'Google-Extended|CCBot|Bytespider|'
    r'python-requests|httpx|axios|node-fetch|Go-http-client|'
    r'curl/|wget/|libwww-perl|Java/|'
    r'Scrapy|Apify|PetalBot)',
    re.IGNORECASE,
)


def _is_agent(request):
    """Return True if the request looks like an AI agent or bot."""
    ua = request.META.get('HTTP_USER_AGENT', '')
    if AGENT_UA_PATTERNS.search(ua):
        return True
    # Also treat explicit Accept: text/markdown or application/json as agent-like
    accept = request.META.get('HTTP_ACCEPT', '')
    if 'text/markdown' in accept or 'application/json' in accept:
        return True
    return False


def agent_friendly_404(request, exception=None):
    """
    Custom 404 handler that returns helpful markdown to AI agents
    and a normal HTML 404 to browsers.

    Logs every agent miss to the AgentMiss model for later analysis.
    """
    from narrative.models import AgentMiss

    if _is_agent(request):
        # Log the miss
        ua = request.META.get('HTTP_USER_AGENT', '')[:2000]
        referer = request.META.get('HTTP_REFERER', '')[:2000]
        AgentMiss.objects.create(
            path=request.path[:2000],
            user_agent=ua,
            referer=referer,
        )
        logger.info("Agent 404: %s (UA: %s)", request.path, ua[:100])

        host = request.build_absolute_uri('/')[:-1]  # strip trailing /
        body = (
            f"# 404 — Page Not Found\n\n"
            f"The path `{request.path}` does not exist on this site.\n\n"
            f"## Where to look instead\n\n"
            f"- **Site map (markdown)**: [{host}/sitemap.md]({host}/sitemap.md)\n"
            f"- **XML sitemap**: [{host}/sitemap.xml]({host}/sitemap.xml)\n"
            f"- **Explore all series**: [{host}/explore/]({host}/explore/)\n\n"
            f"## URL patterns on this site\n\n"
            f"| Pattern | Example |\n"
            f"|---|---|\n"
            f"| `/explore/` | Catalog of all narrative graphs |\n"
            f"| `/explore/<series-slug>/` | Series landing page |\n"
            f"| `/explore/<series-slug>/characters/` | Characters in a series |\n"
            f"| `/explore/<series-slug>/graph/` | Force-directed graph view |\n"
            f"| `/explore/<series-slug>/events/` | Events in a series |\n"
            f"| `/explore/<series-slug>/connections/` | Narrative connections |\n"
            f"| `/explore/<series-slug>/themes/` | Themes |\n"
            f"| `/connections/<id>/` | Single connection detail |\n"
            f"| `/characters/<id>/` | Single character detail |\n"
        )
        return HttpResponse(body, content_type='text/markdown; charset=utf-8', status=404)

    # Normal browser 404
    from django.shortcuts import render
    return render(request, '404.html', status=404)


def sitemap_md(request):
    """
    Machine-readable sitemap in markdown for AI agents.

    Dynamically lists all series and their available sub-sections.
    """
    from narrative.models import SeriesIndexPage
    from wagtail.models import Page

    host = request.build_absolute_uri('/')[:-1]

    lines = [
        "# Fabula — Site Map\n",
        "Fabula publishes narrative graph analysis. Connections between "
        "story events are first-class content with their own URLs.\n",
        "## API & Machine-Readable Endpoints\n",
        f"- [XML Sitemap]({host}/sitemap.xml)",
        f"- [Markdown Sitemap]({host}/sitemap.md) (this page)",
        f"- [robots.txt]({host}/robots.txt)\n",
        "## Explore Narrative Graphs\n",
        f"- [All Series Catalog]({host}/explore/)\n",
    ]

    # Dynamically list each series
    series_pages = (
        SeriesIndexPage.objects.live()
        .specific()
        .order_by('title')
    )
    if series_pages.exists():
        lines.append("### Available Series\n")
        for series in series_pages:
            slug = series.slug
            lines.append(f"#### {series.title}\n")
            lines.append(f"- [Landing]({host}/explore/{slug}/)")
            lines.append(f"- [Characters]({host}/explore/{slug}/characters/)")
            lines.append(f"- [Events]({host}/explore/{slug}/events/)")
            lines.append(f"- [Connections]({host}/explore/{slug}/connections/)")
            lines.append(f"- [Themes]({host}/explore/{slug}/themes/)")
            lines.append(f"- [Conflict Arcs]({host}/explore/{slug}/arcs/)")
            lines.append(f"- [Locations]({host}/explore/{slug}/locations/)")
            lines.append(f"- [Graph View]({host}/explore/{slug}/graph/)")
            lines.append("")

    lines += [
        "## URL Pattern Reference\n",
        "| Pattern | Description |",
        "|---|---|",
        "| `/explore/` | Catalog of all narrative graphs |",
        "| `/explore/<series-slug>/` | Series landing page |",
        "| `/explore/<series-slug>/characters/` | Characters index |",
        "| `/explore/<series-slug>/characters/<id>/` | Character detail |",
        "| `/explore/<series-slug>/events/` | Events index |",
        "| `/explore/<series-slug>/events/<id>/` | Event detail |",
        "| `/explore/<series-slug>/connections/` | Connections index |",
        "| `/explore/<series-slug>/connections/<id>/` | Connection detail |",
        "| `/explore/<series-slug>/themes/` | Themes index |",
        "| `/explore/<series-slug>/themes/<id>/` | Theme detail |",
        "| `/explore/<series-slug>/arcs/` | Conflict arcs index |",
        "| `/explore/<series-slug>/locations/` | Locations index |",
        "| `/explore/<series-slug>/graph/` | Full graph visualization |",
        "| `/connections/<id>/` | Global connection detail |",
        "| `/characters/<id>/` | Global character detail |",
        "| `/events/<id>/` | Global event detail |",
        "",
        "*Identifiers (`<id>`) can be a global_id, fabula_uuid, or numeric pk.*\n",
        "## About Fabula\n",
        "Fabula is a narrative analysis platform that maps the hidden "
        "architecture of TV storytelling. We model causal chains, "
        "foreshadowing, thematic parallels, and character continuity "
        "as a navigable graph.",
    ]

    return HttpResponse(
        "\n".join(lines),
        content_type='text/markdown; charset=utf-8',
    )


urlpatterns = [
    path('googlea62b51e71cd21b69.html', google_verification),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.md', sitemap_md, name='sitemap_md'),
    path('sitemap.xml', cache_page(3600)(sitemap), {'sitemaps': sitemaps}, name='sitemap'),
    path('health/', health_check, name='health_check'),
    path('diagnostics/', diagnostics, name='diagnostics'),
    path('trigger-import/', trigger_import, name='trigger_import'),
    path('django-admin/', admin.site.urls),
    path('admin/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),

    # Narrative custom views (connections, themes, arcs, graph)
    path('', include('narrative.urls')),

    # Wagtail page serving (catch-all, must be last)
    path('', include(wagtail_urls)),
]

handler404 = 'fabula_web.urls.agent_friendly_404'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
