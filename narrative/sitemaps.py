"""
Custom sitemaps for non-Wagtail-Page entities.

These cover Django-view-served content: connections, themes, arcs, locations.
Wagtail pages (series, episodes, characters, events) are handled by
wagtail.contrib.sitemaps automatically.
"""

from django.contrib.sitemaps import Sitemap

from .models import NarrativeConnection, Theme, ConflictArc, Location


class ConnectionSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.6

    def items(self):
        return NarrativeConnection.objects.select_related(
            'from_event', 'to_event'
        ).all()

    def location(self, obj):
        return obj.get_absolute_url()


class ThemeSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return Theme.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()


class ArcSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return ConflictArc.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()


class LocationSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.4

    def items(self):
        return Location.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()
