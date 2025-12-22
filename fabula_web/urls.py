"""
URL configuration for Fabula Web.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
import os
from pathlib import Path

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.models import Page, Site


def health_check(request):
    """Simple health check endpoint for Railway."""
    return JsonResponse({'status': 'ok'})


def diagnostics(request):
    """Diagnostic endpoint to check data import status."""
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


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('diagnostics/', diagnostics, name='diagnostics'),
    path('django-admin/', admin.site.urls),
    path('admin/', include(wagtailadmin_urls)),
    path('documents/', include(wagtaildocs_urls)),

    # Narrative custom views (connections, themes, arcs, graph)
    path('', include('narrative.urls')),

    # Wagtail page serving (catch-all, must be last)
    path('', include(wagtail_urls)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
