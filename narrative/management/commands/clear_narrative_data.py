"""
Management command to clear all narrative data for a fresh reimport.

Usage:
    python manage.py clear_narrative_data --dry-run    # Preview what would be deleted
    python manage.py clear_narrative_data --confirm    # Actually delete everything
"""

from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = 'Clear all narrative data for a fresh reimport'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Required flag to confirm deletion (safety measure)'
        )
        parser.add_argument(
            '--keep-structure',
            action='store_true',
            help='Keep series/season/episode structure and index pages'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        confirm = options['confirm']
        keep_structure = options['keep_structure']

        if not dry_run and not confirm:
            self.stdout.write(self.style.ERROR(
                'You must specify either --dry-run or --confirm to proceed.\n'
                'This is a destructive operation that will delete all narrative data.'
            ))
            return

        # Import models here to avoid circular imports
        from narrative.models import (
            # Relationship models (delete first due to FK constraints)
            EventParticipation,
            ObjectInvolvement,
            LocationInvolvement,
            OrganizationInvolvement,
            NarrativeConnection,
            CharacterEpisodeProfile,
            # Page models
            EventPage,
            CharacterPage,
            OrganizationPage,
            ObjectPage,
            # Snippet models
            Theme,
            ConflictArc,
            Location,
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - no changes will be made\n'))
        else:
            self.stdout.write(self.style.WARNING('DELETING ALL NARRATIVE DATA...\n'))

        # Count everything first
        counts = {
            'EventParticipation': EventParticipation.objects.count(),
            'ObjectInvolvement': ObjectInvolvement.objects.count(),
            'LocationInvolvement': LocationInvolvement.objects.count(),
            'OrganizationInvolvement': OrganizationInvolvement.objects.count(),
            'NarrativeConnection': NarrativeConnection.objects.count(),
            'CharacterEpisodeProfile': CharacterEpisodeProfile.objects.count(),
            'EventPage': EventPage.objects.count(),
            'CharacterPage': CharacterPage.objects.count(),
            'OrganizationPage': OrganizationPage.objects.count(),
            'ObjectPage': ObjectPage.objects.count(),
            'Theme': Theme.objects.count(),
            'ConflictArc': ConflictArc.objects.count(),
            'Location': Location.objects.count(),
        }

        # Add structure counts if not keeping
        if not keep_structure:
            from narrative.models import (
                SeriesIndexPage,
                SeasonPage,
                EpisodePage,
                CharacterIndexPage,
                OrganizationIndexPage,
                ObjectIndexPage,
                EventIndexPage,
            )
            counts.update({
                'EpisodePage': EpisodePage.objects.count(),
                'SeasonPage': SeasonPage.objects.count(),
                'SeriesIndexPage': SeriesIndexPage.objects.count(),
                'CharacterIndexPage': CharacterIndexPage.objects.count(),
                'OrganizationIndexPage': OrganizationIndexPage.objects.count(),
                'ObjectIndexPage': ObjectIndexPage.objects.count(),
                'EventIndexPage': EventIndexPage.objects.count(),
            })

        # Display counts
        self.stdout.write(self.style.MIGRATE_HEADING('=== Data to be deleted ===\n'))

        self.stdout.write('Relationship records:')
        for model in ['EventParticipation', 'ObjectInvolvement', 'LocationInvolvement',
                      'OrganizationInvolvement', 'NarrativeConnection', 'CharacterEpisodeProfile']:
            self.stdout.write(f'  {model}: {counts[model]:,}')

        self.stdout.write('\nEntity pages:')
        for model in ['EventPage', 'CharacterPage', 'OrganizationPage', 'ObjectPage']:
            self.stdout.write(f'  {model}: {counts[model]:,}')

        self.stdout.write('\nSnippets:')
        for model in ['Theme', 'ConflictArc', 'Location']:
            self.stdout.write(f'  {model}: {counts[model]:,}')

        if not keep_structure:
            self.stdout.write('\nStructure pages:')
            for model in ['EpisodePage', 'SeasonPage', 'SeriesIndexPage',
                         'CharacterIndexPage', 'OrganizationIndexPage',
                         'ObjectIndexPage', 'EventIndexPage']:
                if model in counts:
                    self.stdout.write(f'  {model}: {counts[model]:,}')

        total = sum(counts.values())
        self.stdout.write(f'\nTotal records: {total:,}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDry run complete. Use --confirm to delete.'))
            return

        # Actually delete everything
        self.stdout.write(self.style.MIGRATE_HEADING('\n=== Deleting... ===\n'))

        with transaction.atomic():
            # Phase 1: Delete relationship records (no FK dependencies)
            self.stdout.write('Deleting relationship records...')

            deleted = EventParticipation.objects.all().delete()[0]
            self.stdout.write(f'  EventParticipation: {deleted:,} deleted')

            deleted = ObjectInvolvement.objects.all().delete()[0]
            self.stdout.write(f'  ObjectInvolvement: {deleted:,} deleted')

            deleted = LocationInvolvement.objects.all().delete()[0]
            self.stdout.write(f'  LocationInvolvement: {deleted:,} deleted')

            deleted = OrganizationInvolvement.objects.all().delete()[0]
            self.stdout.write(f'  OrganizationInvolvement: {deleted:,} deleted')

            deleted = NarrativeConnection.objects.all().delete()[0]
            self.stdout.write(f'  NarrativeConnection: {deleted:,} deleted')

            deleted = CharacterEpisodeProfile.objects.all().delete()[0]
            self.stdout.write(f'  CharacterEpisodeProfile: {deleted:,} deleted')

            # Phase 2: Delete entity pages
            self.stdout.write('\nDeleting entity pages...')

            # Events first (they reference episodes, locations, themes, arcs)
            deleted = EventPage.objects.all().delete()[0]
            self.stdout.write(f'  EventPage: {deleted:,} deleted')

            # Characters (may reference organizations)
            deleted = CharacterPage.objects.all().delete()[0]
            self.stdout.write(f'  CharacterPage: {deleted:,} deleted')

            deleted = OrganizationPage.objects.all().delete()[0]
            self.stdout.write(f'  OrganizationPage: {deleted:,} deleted')

            deleted = ObjectPage.objects.all().delete()[0]
            self.stdout.write(f'  ObjectPage: {deleted:,} deleted')

            # Phase 3: Delete snippets
            self.stdout.write('\nDeleting snippets...')

            deleted = Theme.objects.all().delete()[0]
            self.stdout.write(f'  Theme: {deleted:,} deleted')

            deleted = ConflictArc.objects.all().delete()[0]
            self.stdout.write(f'  ConflictArc: {deleted:,} deleted')

            deleted = Location.objects.all().delete()[0]
            self.stdout.write(f'  Location: {deleted:,} deleted')

            # Phase 4: Delete structure if requested
            if not keep_structure:
                from narrative.models import (
                    SeriesIndexPage,
                    SeasonPage,
                    EpisodePage,
                    CharacterIndexPage,
                    OrganizationIndexPage,
                    ObjectIndexPage,
                    EventIndexPage,
                )

                self.stdout.write('\nDeleting structure pages...')

                # Delete in reverse hierarchy order
                deleted = EpisodePage.objects.all().delete()[0]
                self.stdout.write(f'  EpisodePage: {deleted:,} deleted')

                deleted = SeasonPage.objects.all().delete()[0]
                self.stdout.write(f'  SeasonPage: {deleted:,} deleted')

                deleted = SeriesIndexPage.objects.all().delete()[0]
                self.stdout.write(f'  SeriesIndexPage: {deleted:,} deleted')

                deleted = CharacterIndexPage.objects.all().delete()[0]
                self.stdout.write(f'  CharacterIndexPage: {deleted:,} deleted')

                deleted = OrganizationIndexPage.objects.all().delete()[0]
                self.stdout.write(f'  OrganizationIndexPage: {deleted:,} deleted')

                deleted = ObjectIndexPage.objects.all().delete()[0]
                self.stdout.write(f'  ObjectIndexPage: {deleted:,} deleted')

                deleted = EventIndexPage.objects.all().delete()[0]
                self.stdout.write(f'  EventIndexPage: {deleted:,} deleted')

        self.stdout.write(self.style.SUCCESS(f'\nSuccessfully deleted {total:,} records.'))
        self.stdout.write(self.style.SUCCESS('Database is ready for fresh import.'))
