"""
Backfill GER global_id for existing entities.

This command connects to the GER (Global Entity Registry) database and updates
existing Wagtail entities with their cross-season global_id. This is necessary
when entities were imported before GER support was added.

Usage:
    # Dry run to see what would be updated
    python manage.py backfill_global_ids --dry-run

    # Actually update entities
    python manage.py backfill_global_ids

    # Specify GER database
    python manage.py backfill_global_ids --ger-database fabulager

The command matches entities using their fabula_uuid against GER's SeasonMapping
nodes, which link local season UUIDs to global cross-season identities.
"""

import os
from typing import Dict, Optional
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Backfill GER global_id for existing entities'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes'
        )
        parser.add_argument(
            '--ger-uri',
            default=None,
            help='GER Neo4j URI (default: from NEO4J_URI env or bolt://localhost:7689)'
        )
        parser.add_argument(
            '--ger-user',
            default=None,
            help='GER Neo4j username (default: from NEO4J_USER env or neo4j)'
        )
        parser.add_argument(
            '--ger-password',
            default=None,
            help='GER Neo4j password (default: from NEO4J_PASSWORD env)'
        )
        parser.add_argument(
            '--ger-database',
            default=os.environ.get('GER_NEO4J_DATABASE', 'fabulager'),
            help='GER database name (default: fabulager)'
        )

    def handle(self, *args, **options):
        from django.conf import settings
        # Import models inside handle to avoid circular import issues
        from narrative.models import (
            Theme, ConflictArc, Location,
            CharacterPage, OrganizationPage, ObjectPage
        )
        self.Theme = Theme
        self.ConflictArc = ConflictArc
        self.Location = Location
        self.CharacterPage = CharacterPage
        self.OrganizationPage = OrganizationPage
        self.ObjectPage = ObjectPage

        self.dry_run = options['dry_run']
        self.verbosity = options['verbosity']

        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be made\n'))

        # Resolve credentials from options, settings, or environment
        uri = (options['ger_uri'] or
               getattr(settings, 'NEO4J_URI', None) or
               os.environ.get('NEO4J_URI', 'bolt://localhost:7689'))
        user = (options['ger_user'] or
                getattr(settings, 'NEO4J_USER', None) or
                os.environ.get('NEO4J_USER', 'neo4j'))
        password = (options['ger_password'] or
                    getattr(settings, 'NEO4J_PASSWORD', None) or
                    os.environ.get('NEO4J_PASSWORD', ''))

        self.stdout.write(f'Connecting to GER at {uri} (database: {options["ger_database"]})')

        # Connect to GER
        try:
            from neo4j import GraphDatabase
        except ImportError:
            self.stderr.write(self.style.ERROR(
                'neo4j driver not installed. Run: pip install neo4j'
            ))
            return

        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.ger_database = options['ger_database']

        try:
            # Load all GER mappings
            self.stdout.write('Loading GER mappings...')
            self.ger_mappings = self._load_ger_mappings()
            self.stdout.write(f'  Found {len(self.ger_mappings)} local_uuid -> global_id mappings')

            # Update each entity type
            stats = {
                'themes': self._backfill_themes(),
                'arcs': self._backfill_arcs(),
                'locations': self._backfill_locations(),
                'characters': self._backfill_characters(),
                'organizations': self._backfill_organizations(),
                'objects': self._backfill_objects(),
            }

            # Print summary
            self.stdout.write('\n' + '=' * 50)
            self.stdout.write(self.style.SUCCESS('Backfill Summary:'))
            total = 0
            for entity_type, count in stats.items():
                if count > 0:
                    self.stdout.write(f'  {entity_type}: {count} updated')
                    total += count
            self.stdout.write(f'\nTotal entities updated: {total}')

            if self.dry_run:
                self.stdout.write(self.style.WARNING('\nDRY RUN - No actual changes made'))
            else:
                self.stdout.write(self.style.SUCCESS('\nBackfill complete!'))

        finally:
            self.driver.close()

    def _load_ger_mappings(self) -> Dict[str, str]:
        """Load all local_uuid -> global_id mappings from GER."""
        query = """
        MATCH (g:GlobalEntityRef)-[:HAS_SEASON_MAPPING]->(m:SeasonMapping)
        RETURN m.local_uuid AS local_uuid, g.global_id AS global_id
        """

        mappings = {}
        with self.driver.session(database=self.ger_database) as session:
            result = session.run(query)
            for record in result:
                local_uuid = record.get('local_uuid')
                global_id = record.get('global_id')
                if local_uuid and global_id:
                    mappings[local_uuid] = global_id

        return mappings

    def _get_global_id(self, fabula_uuid: str) -> Optional[str]:
        """Look up global_id for a fabula_uuid."""
        return self.ger_mappings.get(fabula_uuid)

    def _backfill_themes(self) -> int:
        """Backfill global_id for Theme snippets."""
        self.stdout.write('\nProcessing Themes...')
        updated = 0

        for theme in self.Theme.objects.filter(global_id__isnull=True) | self.Theme.objects.filter(global_id=''):
            global_id = self._get_global_id(theme.fabula_uuid)
            if global_id:
                if self.verbosity >= 2:
                    self.stdout.write(f'  {theme.name}: {theme.fabula_uuid} -> {global_id}')
                if not self.dry_run:
                    theme.global_id = global_id
                    theme.save()
                updated += 1

        self.stdout.write(f'  Found {updated} themes to update')
        return updated

    def _backfill_arcs(self) -> int:
        """Backfill global_id for ConflictArc snippets."""
        self.stdout.write('\nProcessing Conflict Arcs...')
        updated = 0

        for arc in self.ConflictArc.objects.filter(global_id__isnull=True) | self.ConflictArc.objects.filter(global_id=''):
            global_id = self._get_global_id(arc.fabula_uuid)
            if global_id:
                if self.verbosity >= 2:
                    self.stdout.write(f'  {arc.title}: {arc.fabula_uuid} -> {global_id}')
                if not self.dry_run:
                    arc.global_id = global_id
                    arc.save()
                updated += 1

        self.stdout.write(f'  Found {updated} arcs to update')
        return updated

    def _backfill_locations(self) -> int:
        """Backfill global_id for Location snippets."""
        self.stdout.write('\nProcessing Locations...')
        updated = 0

        for location in self.Location.objects.filter(global_id__isnull=True) | self.Location.objects.filter(global_id=''):
            global_id = self._get_global_id(location.fabula_uuid)
            if global_id:
                if self.verbosity >= 2:
                    self.stdout.write(f'  {location.canonical_name}: {location.fabula_uuid} -> {global_id}')
                if not self.dry_run:
                    location.global_id = global_id
                    location.save()
                updated += 1

        self.stdout.write(f'  Found {updated} locations to update')
        return updated

    def _backfill_characters(self) -> int:
        """Backfill global_id for CharacterPage pages."""
        self.stdout.write('\nProcessing Characters...')
        updated = 0

        for char in self.CharacterPage.objects.filter(global_id__isnull=True) | self.CharacterPage.objects.filter(global_id=''):
            global_id = self._get_global_id(char.fabula_uuid)
            if global_id:
                if self.verbosity >= 2:
                    self.stdout.write(f'  {char.canonical_name}: {char.fabula_uuid} -> {global_id}')
                if not self.dry_run:
                    char.global_id = global_id
                    char.save_revision().publish()
                updated += 1

        self.stdout.write(f'  Found {updated} characters to update')
        return updated

    def _backfill_organizations(self) -> int:
        """Backfill global_id for OrganizationPage pages."""
        self.stdout.write('\nProcessing Organizations...')
        updated = 0

        for org in self.OrganizationPage.objects.filter(global_id__isnull=True) | self.OrganizationPage.objects.filter(global_id=''):
            global_id = self._get_global_id(org.fabula_uuid)
            if global_id:
                if self.verbosity >= 2:
                    self.stdout.write(f'  {org.canonical_name}: {org.fabula_uuid} -> {global_id}')
                if not self.dry_run:
                    org.global_id = global_id
                    org.save_revision().publish()
                updated += 1

        self.stdout.write(f'  Found {updated} organizations to update')
        return updated

    def _backfill_objects(self) -> int:
        """Backfill global_id for ObjectPage pages."""
        self.stdout.write('\nProcessing Objects...')
        updated = 0

        for obj in self.ObjectPage.objects.filter(global_id__isnull=True) | self.ObjectPage.objects.filter(global_id=''):
            global_id = self._get_global_id(obj.fabula_uuid)
            if global_id:
                if self.verbosity >= 2:
                    self.stdout.write(f'  {obj.canonical_name}: {obj.fabula_uuid} -> {global_id}')
                if not self.dry_run:
                    obj.global_id = global_id
                    obj.save_revision().publish()
                updated += 1

        self.stdout.write(f'  Found {updated} objects to update')
        return updated
