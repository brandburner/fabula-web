"""
URL configuration for Fabula Web.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls


def health_check(request):
    """Simple health check endpoint for Railway."""
    return JsonResponse({'status': 'ok'})


urlpatterns = [
    path('health/', health_check, name='health_check'),
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
