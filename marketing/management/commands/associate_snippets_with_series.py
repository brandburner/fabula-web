"""
Management command to associate existing snippets with their series.

This command associates Theme, ConflictArc, and Location snippets
with the appropriate SeriesIndexPage based on the events they're connected to.

Usage:
    python manage.py associate_snippets_with_series
    python manage.py associate_snippets_with_series --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from narrative.models import (
    Theme, ConflictArc, Location, EventPage, SeriesIndexPage
)


class Command(BaseCommand):
    help = 'Associate existing snippets with their series'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made'))

        # Get the default series (first one, typically West Wing)
        default_series = SeriesIndexPage.objects.live().first()
        if not default_series:
            self.stdout.write(self.style.ERROR('No SeriesIndexPage found!'))
            return

        self.stdout.write(f'Default series: {default_series.title}')

        with transaction.atomic():
            # Associate Themes
            themes_updated = 0
            for theme in Theme.objects.filter(series__isnull=True):
                # Find series from connected events
                series = self._find_series_for_theme(theme) or default_series
                if not dry_run:
                    theme.series = series
                    theme.save()
                themes_updated += 1
                self.stdout.write(f'  Theme "{theme.name}" -> {series.title}')

            self.stdout.write(self.style.SUCCESS(
                f'Updated {themes_updated} themes'
            ))

            # Associate ConflictArcs
            arcs_updated = 0
            for arc in ConflictArc.objects.filter(series__isnull=True):
                series = self._find_series_for_arc(arc) or default_series
                if not dry_run:
                    arc.series = series
                    arc.save()
                arcs_updated += 1
                self.stdout.write(f'  Arc "{arc.title}" -> {series.title}')

            self.stdout.write(self.style.SUCCESS(
                f'Updated {arcs_updated} conflict arcs'
            ))

            # Associate Locations
            locations_updated = 0
            for location in Location.objects.filter(series__isnull=True):
                series = self._find_series_for_location(location) or default_series
                if not dry_run:
                    location.series = series
                    location.save()
                locations_updated += 1
                self.stdout.write(f'  Location "{location.canonical_name}" -> {series.title}')

            self.stdout.write(self.style.SUCCESS(
                f'Updated {locations_updated} locations'
            ))

            if dry_run:
                raise DryRunComplete()

        self.stdout.write(self.style.SUCCESS('\nSnippet association complete!'))

    def _find_series_for_theme(self, theme):
        """Find the series a theme belongs to via its events."""
        event = theme.events.first()
        if event:
            return self._get_series_for_event(event)
        return None

    def _find_series_for_arc(self, arc):
        """Find the series an arc belongs to via its events."""
        event = arc.events.first()
        if event:
            return self._get_series_for_event(event)
        return None

    def _find_series_for_location(self, location):
        """Find the series a location belongs to via its events."""
        event = location.events.first()
        if event:
            return self._get_series_for_event(event)
        return None

    def _get_series_for_event(self, event):
        """Walk up the page tree to find the SeriesIndexPage."""
        try:
            # Event -> Episode -> Season -> Series
            episode = event.episode
            if episode:
                season = episode.get_parent()
                if season:
                    series = season.get_parent()
                    if isinstance(series.specific, SeriesIndexPage):
                        return series.specific
        except Exception:
            pass
        return None


class DryRunComplete(Exception):
    """Exception to trigger rollback in dry-run mode."""
    pass
