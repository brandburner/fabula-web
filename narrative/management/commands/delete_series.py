"""
Management command to delete one series tree safely.

`series.delete()` alone raises ProtectedError: EventPage.episode is a
PROTECT FK, so the episode pages inside the tree cannot go while their
events exist (ISS-002). The supported order is two-stage — delete the
series' EventPages first, then the page tree. Series-scoped snippets
(Theme, ConflictArc, Location) follow via their CASCADE series FK, and
connections/participations/profiles cascade from events and episodes.

Usage:
    python manage.py delete_series <slug-or-fabula_uuid> --dry-run
    python manage.py delete_series <slug-or-fabula_uuid> --yes
"""

import sys

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from narrative.models import (
    SeriesIndexPage, SeasonPage, EpisodePage, EventPage,
    CharacterPage, OrganizationPage, ObjectPage,
    Theme, ConflictArc, Location, NarrativeConnection,
)


class Command(BaseCommand):
    help = (
        'Delete a single series tree (two-stage: events first, then the '
        'tree) together with its series-scoped snippets. Other series are '
        'never touched.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            'identifier',
            type=str,
            help='Series slug or fabula_uuid',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without deleting anything',
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip the interactive confirmation (required non-interactively)',
        )

    def handle(self, *args, **options):
        identifier = options['identifier']
        dry_run = options['dry_run']
        assume_yes = options['yes']

        series = SeriesIndexPage.objects.filter(
            Q(slug=identifier) | Q(fabula_uuid=identifier)
        ).first()
        if series is None:
            available = ", ".join(
                SeriesIndexPage.objects.values_list('slug', flat=True)
            ) or "(none)"
            raise CommandError(
                f"No series matches '{identifier}'. Available slugs: {available}"
            )

        events = EventPage.objects.descendant_of(series)
        event_ids = list(events.values_list('pk', flat=True))
        counts = {
            'events': len(event_ids),
            'episodes': EpisodePage.objects.descendant_of(series).count(),
            'seasons': SeasonPage.objects.descendant_of(series).count(),
            'characters': CharacterPage.objects.descendant_of(series).count(),
            'organizations': OrganizationPage.objects.descendant_of(series).count(),
            'objects': ObjectPage.objects.descendant_of(series).count(),
            'themes (series FK)': Theme.objects.filter(series=series).count(),
            'arcs (series FK)': ConflictArc.objects.filter(series=series).count(),
            'locations (series FK)': Location.objects.filter(series=series).count(),
            'connections (via events)': NarrativeConnection.objects.filter(
                Q(from_event_id__in=event_ids) | Q(to_event_id__in=event_ids)
            ).count(),
        }

        self.stdout.write(f"Series: {series.title} (slug={series.slug}, "
                          f"fabula_uuid={series.fabula_uuid or 'none'})")
        self.stdout.write("Will delete:")
        for label, count in counts.items():
            self.stdout.write(f"  {label:<26} {count}")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                "[DRY RUN] Nothing was deleted. Re-run with --yes to apply."
            ))
            return

        if not assume_yes:
            if not sys.stdin.isatty():
                raise CommandError(
                    "Refusing to delete without confirmation in a "
                    "non-interactive run. Pass --yes to proceed."
                )
            answer = input(
                f"Type the series slug ('{series.slug}') to confirm deletion: "
            )
            if answer.strip() != series.slug:
                self.stdout.write(self.style.WARNING(
                    "Aborted: confirmation did not match. Nothing was deleted."
                ))
                return

        with transaction.atomic():
            # Stage 1: events go first — they hold the PROTECT FK onto
            # episodes. Per-instance delete keeps the page tree consistent
            # (the whole subtree dies in stage 2, but a stage-1 crash must
            # not leave corrupted treebeard counters behind on rollback).
            deleted_events = 0
            for event in EventPage.objects.filter(pk__in=event_ids).iterator():
                event.delete()
                deleted_events += 1

            # Stage 2: the tree (seasons, episodes, characters, orgs,
            # objects, index pages) plus CASCADE series-FK snippets.
            series.delete()

        self.stdout.write(self.style.SUCCESS(
            f"Deleted series '{series.title}': {deleted_events} events, "
            f"then the page tree and scoped snippets."
        ))
