"""
Django management command to import Fabula YAML data into Wagtail.

This command reads YAML files exported from a Fabula narrative graph and creates
corresponding Wagtail pages and models. It handles dependencies correctly and is
idempotent using fabula_uuid as the lookup key.

Usage:
    python manage.py import_fabula ./fabula_export
    python manage.py import_fabula ./fabula_export --dry-run
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

import yaml
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from wagtail.models import Page, Site

from narrative.models import (
    # Snippets
    Theme,
    ConflictArc,
    Location,
    # Pages
    SeriesIndexPage,
    SeasonPage,
    EpisodePage,
    CharacterIndexPage,
    CharacterPage,
    OrganizationIndexPage,
    OrganizationPage,
    ObjectIndexPage,
    ObjectPage,
    EventIndexPage,
    EventPage,
    # Related models
    NarrativeConnection,
    EventParticipation,
    CharacterEpisodeProfile,
    ObjectInvolvement,
    LocationInvolvement,
    OrganizationInvolvement,
)


class ImportStats:
    """Track import statistics for reporting."""

    def __init__(self):
        self.created = {}
        self.updated = {}
        self.cross_season_matched = {}  # Track GER cross-season matches
        self.errors = []

    def record_created(self, model_name: str):
        self.created[model_name] = self.created.get(model_name, 0) + 1

    def record_updated(self, model_name: str):
        self.updated[model_name] = self.updated.get(model_name, 0) + 1

    def record_cross_season_match(self, model_name: str):
        """Record a cross-season entity match via GER global_id."""
        self.cross_season_matched[model_name] = self.cross_season_matched.get(model_name, 0) + 1

    def record_error(self, message: str):
        self.errors.append(message)

    def summary(self) -> str:
        """Generate a summary report."""
        lines = []
        lines.append("\n=== Import Summary ===")

        if self.created:
            lines.append("\nCreated:")
            for model, count in sorted(self.created.items()):
                lines.append(f"  {model}: {count}")

        if self.updated:
            lines.append("\nUpdated:")
            for model, count in sorted(self.updated.items()):
                lines.append(f"  {model}: {count}")

        if self.cross_season_matched:
            lines.append("\nCross-Season Matched (via GER global_id):")
            for model, count in sorted(self.cross_season_matched.items()):
                lines.append(f"  {model}: {count}")

        if self.errors:
            lines.append(f"\nErrors: {len(self.errors)}")
            for error in self.errors[:10]:  # Show first 10 errors
                lines.append(f"  - {error}")
            if len(self.errors) > 10:
                lines.append(f"  ... and {len(self.errors) - 10} more")

        return "\n".join(lines)


class Command(BaseCommand):
    help = 'Import Fabula YAML data into Wagtail'

    def __init__(self):
        super().__init__()
        self.stats = ImportStats()
        self.dry_run = False
        self.verbose = False

        # Caches for lookups by fabula_uuid
        self.themes_cache: Dict[str, Theme] = {}
        self.arcs_cache: Dict[str, ConflictArc] = {}
        self.locations_cache: Dict[str, Location] = {}
        self.characters_cache: Dict[str, CharacterPage] = {}
        self.organizations_cache: Dict[str, OrganizationPage] = {}
        self.objects_cache: Dict[str, ObjectPage] = {}
        self.episodes_cache: Dict[str, EpisodePage] = {}
        self.events_cache: Dict[str, EventPage] = {}

        # GER global_id caches for cross-season entity resolution
        # These enable finding existing entities when importing a new season
        self.themes_by_global_id: Dict[str, Theme] = {}
        self.arcs_by_global_id: Dict[str, ConflictArc] = {}
        self.locations_by_global_id: Dict[str, Location] = {}
        self.characters_by_global_id: Dict[str, CharacterPage] = {}
        self.organizations_by_global_id: Dict[str, OrganizationPage] = {}
        self.objects_by_global_id: Dict[str, ObjectPage] = {}

    def add_arguments(self, parser):
        parser.add_argument(
            'data_dir',
            type=str,
            help='Directory containing exported YAML files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Validate data without saving to database'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress information'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Delete entities not in the export (removes deprecated items)'
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.verbose = options['verbose']
        self.cleanup = options.get('cleanup', False)
        data_dir = Path(options['data_dir'])

        if not data_dir.exists():
            raise CommandError(f"Data directory does not exist: {data_dir}")

        self.stdout.write(self.style.SUCCESS(
            f"{'[DRY RUN] ' if self.dry_run else ''}Starting Fabula import from {data_dir}"
        ))

        # Disable Wagtail's automatic reference index updates during bulk import
        # This dramatically speeds up imports by preventing per-save indexing
        from django.conf import settings
        original_autoupdate = getattr(settings, 'WAGTAIL_REFERENCE_INDEX_AUTOUPDATE', True)
        settings.WAGTAIL_REFERENCE_INDEX_AUTOUPDATE = False
        self.stdout.write("Disabled automatic reference index updates for bulk import")

        try:
            # Load all YAML files
            manifest = self.load_yaml(data_dir / 'manifest.yaml')
            series_data = self.load_yaml(data_dir / 'series.yaml')
            themes_data = self.unwrap_data(self.load_yaml(data_dir / 'themes.yaml'), 'themes')
            arcs_data = self.unwrap_data(self.load_yaml(data_dir / 'arcs.yaml'), 'arcs')
            locations_data = self.unwrap_data(self.load_yaml(data_dir / 'locations.yaml'), 'locations')
            characters_data = self.unwrap_data(self.load_yaml(data_dir / 'characters.yaml'), 'characters')
            organizations_data_raw = self.load_yaml(data_dir / 'organizations.yaml', required=False)
            organizations_data = self.unwrap_data(organizations_data_raw, 'organizations') if organizations_data_raw else None
            objects_data_raw = self.load_yaml(data_dir / 'objects.yaml', required=False)
            objects_data = self.unwrap_data(objects_data_raw, 'objects') if objects_data_raw else []
            connections_data = self.unwrap_data(self.load_yaml(data_dir / 'connections.yaml'), 'connections')

            # Deduplicate entities that may have duplicate entries in YAML
            # (e.g., same character with different organization affiliations from JOIN queries)
            characters_data = self.dedupe_by_global_id(characters_data, 'characters')
            if organizations_data:
                organizations_data = self.dedupe_by_global_id(organizations_data, 'organizations')
            objects_data = self.dedupe_by_global_id(objects_data, 'objects')
            locations_data = self.dedupe_by_global_id(locations_data, 'locations')
            themes_data = self.dedupe_by_global_id(themes_data, 'themes')
            arcs_data = self.dedupe_by_global_id(arcs_data, 'arcs')

            # Load event files
            events_dir = data_dir / 'events'
            events_data = self.load_events(events_dir)

            self.log_info(f"Loaded {len(events_data)} event files")

            # Run import in transaction (unless dry run)
            if self.dry_run:
                self.run_import(
                    manifest, series_data, themes_data, arcs_data, locations_data,
                    characters_data, organizations_data, objects_data, events_data, connections_data
                )
            else:
                with transaction.atomic():
                    self.run_import(
                        manifest, series_data, themes_data, arcs_data, locations_data,
                        characters_data, organizations_data, objects_data, events_data, connections_data
                    )

            # Print summary
            self.stdout.write(self.style.SUCCESS(self.stats.summary()))

            if self.stats.errors:
                self.stdout.write(self.style.ERROR(
                    f"\nImport completed with {len(self.stats.errors)} errors"
                ))
            else:
                self.stdout.write(self.style.SUCCESS(
                    f"\n{'[DRY RUN] ' if self.dry_run else ''}Import completed successfully!"
                ))

            # Run cleanup if requested (delete entities not in export)
            if self.cleanup and not self.dry_run:
                self.run_cleanup(
                    series_data,
                    events_data,
                    characters_data,
                    organizations_data or [],
                    locations_data
                )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nImport failed: {str(e)}"))
            if self.verbose:
                import traceback
                traceback.print_exc()
            raise
        finally:
            # Restore original setting
            settings.WAGTAIL_REFERENCE_INDEX_AUTOUPDATE = original_autoupdate
            self.stdout.write("Restored automatic reference index updates")

    def load_global_id_caches(self):
        """
        Pre-load existing entities with global_id into caches for cross-season resolution.

        This enables GER-based cross-season matching: when importing S2 data,
        entities with matching global_id will UPDATE the existing S1 entity
        rather than creating duplicates.
        """
        self.log_progress("Loading GER global_id caches for cross-season resolution...")

        # Load themes with global_id
        for theme in Theme.objects.exclude(global_id__isnull=True).exclude(global_id=''):
            self.themes_by_global_id[theme.global_id] = theme
        self.log_detail(f"  Loaded {len(self.themes_by_global_id)} themes with global_id")

        # Load conflict arcs with global_id
        for arc in ConflictArc.objects.exclude(global_id__isnull=True).exclude(global_id=''):
            self.arcs_by_global_id[arc.global_id] = arc
        self.log_detail(f"  Loaded {len(self.arcs_by_global_id)} arcs with global_id")

        # Load locations with global_id
        for location in Location.objects.exclude(global_id__isnull=True).exclude(global_id=''):
            self.locations_by_global_id[location.global_id] = location
        self.log_detail(f"  Loaded {len(self.locations_by_global_id)} locations with global_id")

        # Load characters with global_id
        for char in CharacterPage.objects.exclude(global_id__isnull=True).exclude(global_id=''):
            self.characters_by_global_id[char.global_id] = char
        self.log_detail(f"  Loaded {len(self.characters_by_global_id)} characters with global_id")

        # Load organizations with global_id
        for org in OrganizationPage.objects.exclude(global_id__isnull=True).exclude(global_id=''):
            self.organizations_by_global_id[org.global_id] = org
        self.log_detail(f"  Loaded {len(self.organizations_by_global_id)} organizations with global_id")

        # Load objects with global_id
        for obj in ObjectPage.objects.exclude(global_id__isnull=True).exclude(global_id=''):
            self.objects_by_global_id[obj.global_id] = obj
        self.log_detail(f"  Loaded {len(self.objects_by_global_id)} objects with global_id")

        total = (
            len(self.themes_by_global_id) +
            len(self.arcs_by_global_id) +
            len(self.locations_by_global_id) +
            len(self.characters_by_global_id) +
            len(self.organizations_by_global_id) +
            len(self.objects_by_global_id)
        )
        self.log_info(f"  Total entities with GER global_id: {total}")

    def run_import(
        self,
        manifest: Dict,
        series_data,  # Can be Dict or List[Dict]
        themes_data: List[Dict],
        arcs_data: List[Dict],
        locations_data: List[Dict],
        characters_data: List[Dict],
        organizations_data: Optional[List[Dict]],
        objects_data: List[Dict],
        events_data: List[Dict],
        connections_data: List[Dict]
    ):
        """Execute the import in dependency order."""

        # Load existing entities with global_id for cross-season resolution
        self.load_global_id_caches()

        self.log_progress("Phase 1: Importing snippets (themes, arcs, locations)")
        self.import_themes(themes_data)
        self.import_arcs(arcs_data)
        self.import_locations(locations_data)

        self.log_progress("Phase 2: Creating page tree structure")
        # Handle series_data as either a list or a single dict
        series_list = series_data if isinstance(series_data, list) else [series_data]

        # Import all series, use "The West Wing" as primary (or first series if not found)
        main_series_page = None
        character_index = None
        org_index = None
        object_index = None
        event_index = None

        for single_series in series_list:
            series_page, char_idx, org_idx, obj_idx, event_idx = self.import_series_structure(single_series)
            # Use The West Wing as primary, otherwise use first series
            if single_series.get('title') == 'The West Wing' or main_series_page is None:
                main_series_page = series_page
                character_index = char_idx
                org_index = org_idx
                object_index = obj_idx
                event_index = event_idx

        self.log_progress("Phase 3: Importing organizations, objects, and characters")
        if organizations_data:
            self.import_organizations(organizations_data, org_index)
        if objects_data:
            self.import_objects(objects_data, object_index)
        self.import_characters(characters_data, character_index)

        self.log_progress("Phase 4: Importing events")
        self.import_events(events_data, event_index)

        self.log_progress("Phase 5: Creating event participations")
        self.import_event_participations(events_data)

        self.log_progress("Phase 6: Creating entity involvements")
        self.import_object_involvements(events_data)
        self.import_location_involvements(events_data)
        self.import_organization_involvements(events_data)

        self.log_progress("Phase 7: Creating narrative connections")
        self.import_connections(connections_data)

        self.log_progress("Phase 8: Configuring Wagtail Site")
        self.configure_site(main_series_page)

    def configure_site(self, root_page):
        """Configure the default Wagtail Site to use our content root."""
        if not root_page:
            self.log_info("  No root page available, skipping site configuration")
            return

        if self.dry_run:
            self.log_info(f"  Would update default site to use root: {root_page.title}")
            return

        try:
            # Get or create the default site
            site = Site.objects.filter(is_default_site=True).first()
            if site:
                site.root_page = root_page
                site.site_name = root_page.title
                site.save()
                self.log_info(f"  Updated default site to use root: {root_page.title}")
                self.stats.record_updated('Site')
            else:
                Site.objects.create(
                    hostname='*',
                    root_page=root_page,
                    is_default_site=True,
                    site_name=root_page.title
                )
                self.log_info(f"  Created default site with root: {root_page.title}")
                self.stats.record_created('Site')
        except Exception as e:
            self.stats.record_error(f"Site configuration failed: {e}")
            self.log_info(f"  Warning: Could not configure site: {e}")

    # =========================================================================
    # YAML Loading
    # =========================================================================

    def load_yaml(self, path: Path, required: bool = True) -> Any:
        """Load a YAML file."""
        if not path.exists():
            if required:
                raise CommandError(f"Required file not found: {path}")
            return None

        try:
            with open(path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            raise CommandError(f"Error loading {path}: {e}")

    def unwrap_data(self, data: Any, key: str) -> List[Dict]:
        """Unwrap data from a wrapper dict if present, otherwise return as-is.

        Handles both formats:
        - Wrapped: {'themes': [...]} -> returns [...]
        - Bare: [...] -> returns [...]
        """
        if isinstance(data, dict) and key in data:
            return data[key]
        if isinstance(data, list):
            return data
        return data or []

    def load_events(self, events_dir: Path) -> List[Dict]:
        """Load all event YAML files from the events directory."""
        if not events_dir.exists():
            raise CommandError(f"Events directory not found: {events_dir}")

        events = []
        for event_file in sorted(events_dir.glob('*.yaml')):
            event_data = self.load_yaml(event_file)
            if event_data:
                events.append(event_data)

        return events

    def make_unique_slug(self, base_slug: str, uuid: str) -> str:
        """Create a unique slug by appending full UUID for guaranteed uniqueness."""
        # Use full UUID to handle duplicate entries with same suffix
        uuid_slug = slugify(uuid) if uuid else ''
        return f"{base_slug}-{uuid_slug}" if uuid_slug else base_slug

    def normalize_character_type(self, char_type: str) -> str:
        """Normalize character type to model-compatible value."""
        type_map = {
            'main': 'main',
            'main character': 'main',
            'recurring': 'recurring',
            'recurring character': 'recurring',
            'guest': 'guest',
            'guest character': 'guest',
            'mentioned': 'mentioned',
            'mentioned only': 'mentioned',
        }
        return type_map.get(char_type.lower(), 'recurring') if char_type else 'recurring'

    def truncate_field(self, value: str, max_length: int) -> str:
        """Truncate a string to fit within a max length, adding ellipsis if needed."""
        if not value or len(value) <= max_length:
            return value
        return value[:max_length - 3] + '...'

    def dedupe_by_global_id(self, data_list: List[Dict], entity_type: str = 'entity') -> List[Dict]:
        """
        Deduplicate a list of entity data by global_id.

        Some exports (particularly from Neo4j with JOINs) can produce duplicate
        entries for the same entity with different relationships (e.g., same
        character with different organization affiliations). This dedupes by
        global_id, keeping the first occurrence.

        Args:
            data_list: List of entity dictionaries
            entity_type: Name of entity type for logging

        Returns:
            Deduplicated list
        """
        seen_global_ids = set()
        seen_fabula_uuids = set()
        deduped = []
        duplicates_skipped = 0

        for item in data_list:
            global_id = item.get('global_id', '')
            fabula_uuid = item.get('fabula_uuid', '')

            # Skip if we've seen this global_id before
            if global_id and global_id in seen_global_ids:
                duplicates_skipped += 1
                continue

            # Also skip if we've seen this fabula_uuid (backup dedup)
            if fabula_uuid and fabula_uuid in seen_fabula_uuids:
                duplicates_skipped += 1
                continue

            if global_id:
                seen_global_ids.add(global_id)
            if fabula_uuid:
                seen_fabula_uuids.add(fabula_uuid)
            deduped.append(item)

        if duplicates_skipped > 0:
            self.log_info(f"  Deduped {entity_type}: removed {duplicates_skipped} duplicate entries")

        return deduped

    # =========================================================================
    # Phase 1: Snippets
    # =========================================================================

    def import_themes(self, themes_data: List[Dict]):
        """Import Theme snippets with GER cross-season resolution."""
        self.log_progress(f"  Importing {len(themes_data)} themes...")

        for theme_data in themes_data:
            fabula_uuid = theme_data.get('fabula_uuid') or theme_data.get('theme_uuid', '')
            global_id = theme_data.get('global_id', '')

            # Cross-season resolution: first try to find by global_id
            theme = None
            cross_season_match = False
            if global_id and global_id in self.themes_by_global_id:
                theme = self.themes_by_global_id[global_id]
                cross_season_match = True
                self.log_detail(f"    Cross-season match for theme: {theme.name} (global_id: {global_id})")

            # Fall back to fabula_uuid lookup
            if not theme:
                theme = Theme.objects.filter(fabula_uuid=fabula_uuid).first()

            created = False
            if theme:
                # Update existing (either from cross-season match or fabula_uuid)
                theme.name = self.truncate_field(theme_data['name'], 255)
                theme.description = theme_data.get('description', '')
                if global_id:
                    theme.global_id = global_id
                if not self.dry_run:
                    theme.save()
                if cross_season_match:
                    self.stats.record_cross_season_match('Theme')
                self.stats.record_updated('Theme')
            else:
                # Create new
                theme = Theme(
                    fabula_uuid=fabula_uuid,
                    name=self.truncate_field(theme_data['name'], 255),
                    description=theme_data.get('description', ''),
                    global_id=global_id or None,
                )
                if not self.dry_run:
                    theme.save()
                self.stats.record_created('Theme')
                created = True

            # Update caches
            self.themes_cache[fabula_uuid] = theme
            if global_id:
                self.themes_by_global_id[global_id] = theme

            self.log_detail(f"    {'Created' if created else 'Updated'} theme: {theme.name}")

    def import_arcs(self, arcs_data: List[Dict]):
        """Import ConflictArc snippets with GER cross-season resolution."""
        self.log_progress(f"  Importing {len(arcs_data)} conflict arcs...")

        for arc_data in arcs_data:
            fabula_uuid = arc_data.get('fabula_uuid') or arc_data.get('arc_uuid', '')
            global_id = arc_data.get('global_id', '')
            title = self.truncate_field(arc_data['title'], 255)

            # Cross-season resolution: first try to find by global_id
            arc = None
            cross_season_match = False
            if global_id and global_id in self.arcs_by_global_id:
                arc = self.arcs_by_global_id[global_id]
                cross_season_match = True
                self.log_detail(f"    Cross-season match for arc: {arc.title} (global_id: {global_id})")

            # Fall back to fabula_uuid lookup
            if not arc:
                arc = ConflictArc.objects.filter(fabula_uuid=fabula_uuid).first()

            created = False
            if arc:
                # Update existing
                arc.title = title
                arc.description = arc_data.get('description', '')
                arc.arc_type = arc_data.get('arc_type', 'INTERPERSONAL')
                if global_id:
                    arc.global_id = global_id
                if not self.dry_run:
                    arc.save()
                if cross_season_match:
                    self.stats.record_cross_season_match('ConflictArc')
                self.stats.record_updated('ConflictArc')
            else:
                # Create new
                arc = ConflictArc(
                    fabula_uuid=fabula_uuid,
                    title=title,
                    description=arc_data.get('description', ''),
                    arc_type=arc_data.get('arc_type', 'INTERPERSONAL'),
                    global_id=global_id or None,
                )
                if not self.dry_run:
                    arc.save()
                self.stats.record_created('ConflictArc')
                created = True

            # Update caches
            self.arcs_cache[fabula_uuid] = arc
            if global_id:
                self.arcs_by_global_id[global_id] = arc

            self.log_detail(f"    {'Created' if created else 'Updated'} arc: {arc.title}")

    def import_locations(self, locations_data: List[Dict]):
        """Import Location snippets with GER cross-season resolution."""
        self.log_progress(f"  Importing {len(locations_data)} locations...")

        # First pass: create all locations without parent relationships
        for loc_data in locations_data:
            fabula_uuid = loc_data.get('fabula_uuid') or loc_data.get('location_uuid', '')
            global_id = loc_data.get('global_id', '')

            # Cross-season resolution: first try to find by global_id
            location = None
            cross_season_match = False
            if global_id and global_id in self.locations_by_global_id:
                location = self.locations_by_global_id[global_id]
                cross_season_match = True
                self.log_detail(f"    Cross-season match for location: {location.canonical_name} (global_id: {global_id})")

            # Fall back to fabula_uuid lookup
            if not location:
                location = Location.objects.filter(fabula_uuid=fabula_uuid).first()

            created = False
            if location:
                # Update existing
                location.canonical_name = self.truncate_field(loc_data['canonical_name'], 255)
                location.description = loc_data.get('description', '')
                location.location_type = self.truncate_field(loc_data.get('location_type', ''), 100)
                if global_id:
                    location.global_id = global_id
                if not self.dry_run:
                    location.save()
                if cross_season_match:
                    self.stats.record_cross_season_match('Location')
                self.stats.record_updated('Location')
            else:
                # Create new
                location = Location(
                    fabula_uuid=fabula_uuid,
                    canonical_name=self.truncate_field(loc_data['canonical_name'], 255),
                    description=loc_data.get('description', ''),
                    location_type=self.truncate_field(loc_data.get('location_type', ''), 100),
                    global_id=global_id or None,
                )
                if not self.dry_run:
                    location.save()
                self.stats.record_created('Location')
                created = True

            # Update caches
            self.locations_cache[fabula_uuid] = location
            if global_id:
                self.locations_by_global_id[global_id] = location

            self.log_detail(f"    {'Created' if created else 'Updated'} location: {location.canonical_name}")

        # Second pass: set parent relationships
        for loc_data in locations_data:
            if parent_uuid := loc_data.get('parent_location_uuid'):
                loc_uuid = loc_data.get('fabula_uuid') or loc_data.get('location_uuid', '')
                location = self.locations_cache[loc_uuid]
                parent = self.locations_cache.get(parent_uuid)
                if parent:
                    location.parent_location = parent
                    if not self.dry_run:
                        location.save()

    # =========================================================================
    # Phase 2: Page Tree Structure
    # =========================================================================

    def import_series_structure(self, series_data: Dict) -> Tuple[SeriesIndexPage, CharacterIndexPage, OrganizationIndexPage, ObjectIndexPage, EventIndexPage]:
        """Create the series page tree structure."""

        # Get or create series root page
        series_uuid = series_data.get('fabula_uuid') or series_data.get('series_uuid', '')
        series_title = series_data['title']

        root_page = Page.objects.get(depth=1)  # Wagtail root page

        # Check if series already exists
        series_page = SeriesIndexPage.objects.filter(fabula_uuid=series_uuid).first()

        if series_page:
            self.log_detail(f"  Using existing series: {series_page.title}")
            series_page.description = series_data.get('description', '')
            if not self.dry_run:
                series_page.save_revision().publish()
            self.stats.record_updated('SeriesIndexPage')
        else:
            series_page = SeriesIndexPage(
                title=series_title,
                slug=slugify(series_title),
                fabula_uuid=series_uuid,
                description=series_data.get('description', ''),
            )
            if not self.dry_run:
                root_page.add_child(instance=series_page)
                series_page.save_revision().publish()
            self.stats.record_created('SeriesIndexPage')
            self.log_detail(f"  Created series page: {series_title}")

        # Create seasons
        for season_data in series_data.get('seasons', []):
            self.import_season(season_data, series_page)

        # Create index pages
        character_index = self.get_or_create_index_page(
            CharacterIndexPage,
            'Characters',
            series_page,
            'characters'
        )

        org_index = self.get_or_create_index_page(
            OrganizationIndexPage,
            'Organizations',
            series_page,
            'organizations'
        )

        object_index = self.get_or_create_index_page(
            ObjectIndexPage,
            'Objects',
            series_page,
            'objects'
        )

        event_index = self.get_or_create_index_page(
            EventIndexPage,
            'Events',
            series_page,
            'events'
        )

        return series_page, character_index, org_index, object_index, event_index

    def import_season(self, season_data: Dict, series_page: SeriesIndexPage):
        """Import a season and its episodes."""
        season_uuid = season_data.get('fabula_uuid') or season_data.get('season_uuid', '')
        season_number = season_data['season_number']

        season_page = SeasonPage.objects.filter(fabula_uuid=season_uuid).first()

        if season_page:
            season_page.season_number = season_number
            season_page.description = season_data.get('description', '')
            if not self.dry_run:
                season_page.save_revision().publish()
            self.stats.record_updated('SeasonPage')
        else:
            season_page = SeasonPage(
                title=f"Season {season_number}",
                slug=f"season-{season_number}",
                fabula_uuid=season_uuid,
                season_number=season_number,
                description=season_data.get('description', ''),
            )
            if not self.dry_run:
                series_page.add_child(instance=season_page)
                season_page.save_revision().publish()
            self.stats.record_created('SeasonPage')

        self.log_detail(f"    Season {season_number}")

        # Create episodes
        for episode_data in season_data.get('episodes', []):
            self.import_episode(episode_data, season_page)

    def import_episode(self, episode_data: Dict, season_page: SeasonPage):
        """Import an episode."""
        episode_uuid = episode_data.get('fabula_uuid') or episode_data.get('episode_uuid', '')
        episode_number = episode_data['episode_number']
        title = episode_data['title']

        episode_page = EpisodePage.objects.filter(fabula_uuid=episode_uuid).first()

        if episode_page:
            episode_page.title = title
            episode_page.episode_number = episode_number
            episode_page.logline = episode_data.get('logline', '')
            episode_page.high_level_summary = episode_data.get('high_level_summary', '')
            episode_page.dominant_tone = episode_data.get('dominant_tone', '')
            if not self.dry_run:
                episode_page.save_revision().publish()
            self.stats.record_updated('EpisodePage')
        else:
            episode_page = EpisodePage(
                title=title,
                slug=slugify(f"s{season_page.season_number}e{episode_number}-{title}"),
                fabula_uuid=episode_uuid,
                episode_number=episode_number,
                logline=episode_data.get('logline', ''),
                high_level_summary=episode_data.get('high_level_summary', ''),
                dominant_tone=episode_data.get('dominant_tone', ''),
            )
            if not self.dry_run:
                season_page.add_child(instance=episode_page)
                episode_page.save_revision().publish()
            self.stats.record_created('EpisodePage')

        self.episodes_cache[episode_uuid] = episode_page
        self.log_detail(f"      Episode {episode_number}: {title}")

    def get_or_create_index_page(
        self,
        page_class,
        title: str,
        parent: Page,
        slug: str
    ):
        """Get or create an index page."""
        existing = page_class.objects.child_of(parent).first()

        if existing:
            self.log_detail(f"  Using existing {page_class.__name__}: {existing.title}")
            self.stats.record_updated(page_class.__name__)
            return existing

        page = page_class(
            title=title,
            slug=slug,
            introduction='',
        )

        if not self.dry_run:
            parent.add_child(instance=page)
            page.save_revision().publish()

        self.stats.record_created(page_class.__name__)
        self.log_detail(f"  Created {page_class.__name__}: {title}")
        return page

    # =========================================================================
    # Phase 3: Characters and Organizations
    # =========================================================================

    def import_organizations(self, orgs_data: List[Dict], org_index: OrganizationIndexPage):
        """Import organizations with GER cross-season resolution."""
        self.log_progress(f"  Importing {len(orgs_data)} organizations...")

        for org_data in orgs_data:
            org_uuid = org_data.get('fabula_uuid') or org_data.get('org_uuid', '')
            global_id = org_data.get('global_id', '')

            # Cross-season resolution: first try to find by global_id
            org_page = None
            cross_season_match = False
            if global_id and global_id in self.organizations_by_global_id:
                org_page = self.organizations_by_global_id[global_id]
                cross_season_match = True
                self.log_detail(f"    Cross-season match for organization: {org_page.canonical_name} (global_id: {global_id})")

            # Fall back to fabula_uuid lookup
            if not org_page:
                org_page = OrganizationPage.objects.filter(fabula_uuid=org_uuid).first()

            created = False
            if org_page:
                # Update existing - sync title with canonical_name for graph display consistency
                org_page.title = self.truncate_field(org_data['canonical_name'], 255)
                org_page.canonical_name = self.truncate_field(org_data['canonical_name'], 255)
                org_page.description = org_data.get('description', '')
                org_page.sphere_of_influence = self.truncate_field(org_data.get('sphere_of_influence', ''), 255)
                if global_id:
                    org_page.global_id = global_id
                if not self.dry_run:
                    org_page.save_revision().publish()
                if cross_season_match:
                    self.stats.record_cross_season_match('OrganizationPage')
                self.stats.record_updated('OrganizationPage')
            else:
                # Create new
                base_slug = slugify(org_data['canonical_name'])
                unique_slug = self.make_unique_slug(base_slug, org_uuid)
                org_page = OrganizationPage(
                    title=org_data['canonical_name'],
                    slug=unique_slug,
                    fabula_uuid=org_uuid,
                    canonical_name=self.truncate_field(org_data['canonical_name'], 255),
                    description=org_data.get('description', ''),
                    sphere_of_influence=self.truncate_field(org_data.get('sphere_of_influence', ''), 255),
                    global_id=global_id or None,
                )
                if not self.dry_run:
                    org_index.add_child(instance=org_page)
                    org_page.save_revision().publish()
                self.stats.record_created('OrganizationPage')
                created = True

            # Update caches
            self.organizations_cache[org_uuid] = org_page
            if global_id:
                self.organizations_by_global_id[global_id] = org_page

            self.log_detail(f"    {'Created' if created else 'Updated'} organization: {org_page.canonical_name}")

    def import_characters(self, characters_data: List[Dict], char_index: CharacterIndexPage):
        """Import characters with GER cross-season resolution."""
        self.log_progress(f"  Importing {len(characters_data)} characters...")

        for char_data in characters_data:
            char_uuid = char_data.get('fabula_uuid') or char_data.get('agent_uuid', '')
            global_id = char_data.get('global_id', '')

            # Cross-season resolution: first try to find by global_id
            char_page = None
            cross_season_match = False
            if global_id and global_id in self.characters_by_global_id:
                char_page = self.characters_by_global_id[global_id]
                cross_season_match = True
                self.log_detail(f"    Cross-season match for character: {char_page.canonical_name} (global_id: {global_id})")

            # Fall back to fabula_uuid lookup
            if not char_page:
                char_page = CharacterPage.objects.filter(fabula_uuid=char_uuid).first()

            # Get organization if specified
            org = None
            if org_uuid := char_data.get('affiliated_organization_uuid'):
                org = self.organizations_cache.get(org_uuid)

            created = False
            if char_page:
                # Update existing - sync title with canonical_name for graph display consistency
                char_page.title = self.truncate_field(char_data['canonical_name'], 255)
                char_page.canonical_name = self.truncate_field(char_data['canonical_name'], 255)
                char_page.title_role = self.truncate_field(char_data.get('title_role') or '', 255)
                char_page.description = char_data.get('description') or ''
                char_page.traits = char_data.get('traits') or []
                char_page.nicknames = char_data.get('aliases') or char_data.get('nicknames') or []
                char_page.character_type = self.normalize_character_type(char_data.get('character_type', 'recurring'))
                char_page.sphere_of_influence = self.truncate_field(char_data.get('sphere_of_influence') or '', 255)
                char_page.appearance_count = char_data.get('appearance_count', 0)
                char_page.affiliated_organization = org
                if global_id:
                    char_page.global_id = global_id
                if not self.dry_run:
                    char_page.save_revision().publish()
                if cross_season_match:
                    self.stats.record_cross_season_match('CharacterPage')
                self.stats.record_updated('CharacterPage')
            else:
                # Create new
                base_slug = slugify(char_data['canonical_name'])
                unique_slug = self.make_unique_slug(base_slug, char_uuid)
                char_page = CharacterPage(
                    title=self.truncate_field(char_data['canonical_name'], 255),
                    slug=unique_slug,
                    fabula_uuid=char_uuid,
                    canonical_name=self.truncate_field(char_data['canonical_name'], 255),
                    title_role=self.truncate_field(char_data.get('title_role') or '', 255),
                    description=char_data.get('description') or '',
                    traits=char_data.get('traits') or [],
                    nicknames=char_data.get('aliases') or char_data.get('nicknames') or [],
                    character_type=self.normalize_character_type(char_data.get('character_type', 'recurring')),
                    sphere_of_influence=self.truncate_field(char_data.get('sphere_of_influence') or '', 255),
                    appearance_count=char_data.get('appearance_count', 0),
                    affiliated_organization=org,
                    global_id=global_id or None,
                )
                if not self.dry_run:
                    char_index.add_child(instance=char_page)
                    char_page.save_revision().publish()
                self.stats.record_created('CharacterPage')
                created = True

            # Update caches
            self.characters_cache[char_uuid] = char_page
            if global_id:
                self.characters_by_global_id[global_id] = char_page

            self.log_detail(f"    {'Created' if created else 'Updated'} character: {char_page.canonical_name}")

    def import_objects(self, objects_data: List[Dict], object_index: ObjectIndexPage):
        """Import objects with GER cross-season resolution."""
        self.log_progress(f"  Importing {len(objects_data)} objects...")

        for obj_data in objects_data:
            obj_uuid = obj_data.get('fabula_uuid') or obj_data.get('object_uuid', '')
            global_id = obj_data.get('global_id', '')

            # Cross-season resolution: first try to find by global_id
            obj_page = None
            cross_season_match = False
            if global_id and global_id in self.objects_by_global_id:
                obj_page = self.objects_by_global_id[global_id]
                cross_season_match = True
                self.log_detail(f"    Cross-season match for object: {obj_page.canonical_name} (global_id: {global_id})")

            # Fall back to fabula_uuid lookup
            if not obj_page:
                obj_page = ObjectPage.objects.filter(fabula_uuid=obj_uuid).first()

            # Get potential owner if specified
            owner = None
            if owner_uuid := obj_data.get('potential_owner_uuid'):
                owner = self.characters_cache.get(owner_uuid)

            created = False
            if obj_page:
                # Update existing - sync title with canonical_name for graph display consistency
                obj_page.title = self.truncate_field(obj_data['canonical_name'], 255)
                obj_page.canonical_name = self.truncate_field(obj_data['canonical_name'], 255)
                obj_page.description = obj_data.get('description', '')
                obj_page.purpose = obj_data.get('purpose', '')
                obj_page.significance = obj_data.get('significance', '')
                obj_page.potential_owner = owner
                if global_id:
                    obj_page.global_id = global_id
                if not self.dry_run:
                    obj_page.save_revision().publish()
                if cross_season_match:
                    self.stats.record_cross_season_match('ObjectPage')
                self.stats.record_updated('ObjectPage')
            else:
                # Create new
                base_slug = slugify(obj_data['canonical_name'])
                unique_slug = self.make_unique_slug(base_slug, obj_uuid)
                obj_page = ObjectPage(
                    title=obj_data['canonical_name'],
                    slug=unique_slug,
                    fabula_uuid=obj_uuid,
                    canonical_name=self.truncate_field(obj_data['canonical_name'], 255),
                    description=obj_data.get('description', ''),
                    purpose=obj_data.get('purpose', ''),
                    significance=obj_data.get('significance', ''),
                    potential_owner=owner,
                    global_id=global_id or None,
                )
                if not self.dry_run:
                    object_index.add_child(instance=obj_page)
                    obj_page.save_revision().publish()
                self.stats.record_created('ObjectPage')
                created = True

            # Update caches
            self.objects_cache[obj_uuid] = obj_page
            if global_id:
                self.objects_by_global_id[global_id] = obj_page

            self.log_detail(f"    {'Created' if created else 'Updated'} object: {obj_page.canonical_name}")

    # =========================================================================
    # Phase 4: Events
    # =========================================================================

    def import_events(self, events_data: List[Dict], event_index: EventIndexPage):
        """Import events from episode files (each file contains an events list)."""
        # Count total events
        total_events = sum(len(ep_data.get('events', [])) for ep_data in events_data)
        self.log_progress(f"  Importing {total_events} events from {len(events_data)} episode files...")

        for episode_file_data in events_data:
            # Get default episode UUID from file header
            default_episode_uuid = episode_file_data.get('episode_uuid', '')

            # Iterate over events in this episode file
            for event_data in episode_file_data.get('events', []):
                event_uuid = event_data.get('fabula_uuid') or event_data.get('event_uuid', '')

                # Get episode (use event's episode_uuid or fall back to file's default)
                episode_uuid = event_data.get('episode_uuid', '') or default_episode_uuid
                episode = self.episodes_cache.get(episode_uuid)
                if not episode:
                    self.stats.record_error(f"Episode not found for event {event_uuid}")
                    continue

                # Get location
                location = None
                if loc_uuid := event_data.get('location_uuid'):
                    location = self.locations_cache.get(loc_uuid)

                event_page = EventPage.objects.filter(fabula_uuid=event_uuid).first()

                # Generate title from description or use a default
                title = event_data.get('title') or f"Event {event_data.get('scene_sequence', 0)}.{event_data.get('sequence_in_scene', 0)}"

                if event_page:
                    event_page.title = title
                    event_page.episode = episode
                    event_page.scene_sequence = event_data.get('scene_sequence', 0)
                    event_page.sequence_in_scene = event_data.get('sequence_in_scene', 0)
                    event_page.description = event_data.get('description') or ''
                    event_page.key_dialogue = event_data.get('key_dialogue') or []
                    event_page.is_flashback = event_data.get('is_flashback', False)
                    event_page.location = location

                    if not self.dry_run:
                        # Set themes and arcs BEFORE save (ParentalManyToManyField requires this)
                        theme_uuids = event_data.get('theme_uuids') or []
                        themes = [self.themes_cache[uuid] for uuid in theme_uuids if uuid in self.themes_cache]
                        event_page.themes.set(themes)

                        arc_uuids = event_data.get('arc_uuids') or []
                        arcs = [self.arcs_cache[uuid] for uuid in arc_uuids if uuid in self.arcs_cache]
                        event_page.arcs.set(arcs)

                        event_page.save_revision().publish()

                    self.stats.record_updated('EventPage')
                else:
                    base_slug = slugify(f"{episode.slug}-{event_data.get('scene_sequence', 0)}-{event_data.get('sequence_in_scene', 0)}")
                    unique_slug = self.make_unique_slug(base_slug, event_uuid)
                    event_page = EventPage(
                        title=title,
                        slug=unique_slug,
                        fabula_uuid=event_uuid,
                        episode=episode,
                        scene_sequence=event_data.get('scene_sequence', 0),
                        sequence_in_scene=event_data.get('sequence_in_scene', 0),
                        description=event_data.get('description') or '',
                        key_dialogue=event_data.get('key_dialogue') or [],
                        is_flashback=event_data.get('is_flashback', False),
                        location=location,
                    )

                    if not self.dry_run:
                        event_index.add_child(instance=event_page)

                        # Set themes and arcs BEFORE final save (ParentalManyToManyField requires this)
                        theme_uuids = event_data.get('theme_uuids') or []
                        themes = [self.themes_cache[uuid] for uuid in theme_uuids if uuid in self.themes_cache]
                        event_page.themes.set(themes)

                        arc_uuids = event_data.get('arc_uuids') or []
                        arcs = [self.arcs_cache[uuid] for uuid in arc_uuids if uuid in self.arcs_cache]
                        event_page.arcs.set(arcs)

                        event_page.save_revision().publish()

                    self.stats.record_created('EventPage')

                self.events_cache[event_uuid] = event_page
                self.log_detail(f"    {'Updated' if event_page.pk else 'Created'} event: {title}")

    # =========================================================================
    # Phase 5: Event Participations
    # =========================================================================

    def import_event_participations(self, events_data: List[Dict]):
        """Import event participations from episode files (each file contains an events list)."""
        self.log_progress(f"  Importing event participations...")

        total = 0
        for episode_file_data in events_data:
            for event_data in episode_file_data.get('events', []):
                event_uuid = event_data.get('fabula_uuid') or event_data.get('event_uuid', '')
                event = self.events_cache.get(event_uuid)

                if not event:
                    continue

                participations = event_data.get('participations') or []

                for part_data in participations:
                    char_uuid = part_data.get('character_uuid') or part_data.get('agent_uuid', '')
                    character = self.characters_cache.get(char_uuid)

                    if not character:
                        self.stats.record_error(f"Character {char_uuid} not found for participation")
                        continue

                    # Check if participation already exists
                    participation = EventParticipation.objects.filter(
                        event=event,
                        character=character
                    ).first()

                    if participation:
                        # Update existing
                        participation.emotional_state = part_data.get('emotional_state') or ''
                        participation.goals = part_data.get('goals') or []
                        participation.what_happened = part_data.get('what_happened') or ''
                        participation.observed_status = part_data.get('observed_status') or ''
                        participation.beliefs = part_data.get('beliefs') or []
                        participation.observed_traits = part_data.get('observed_traits') or []
                        participation.importance = part_data.get('importance') or ''

                        if not self.dry_run:
                            participation.save()
                        self.stats.record_updated('EventParticipation')
                    else:
                        # Create new
                        participation = EventParticipation(
                            event=event,
                            character=character,
                            emotional_state=part_data.get('emotional_state') or '',
                            goals=part_data.get('goals') or [],
                            what_happened=part_data.get('what_happened') or '',
                            observed_status=part_data.get('observed_status') or '',
                            beliefs=part_data.get('beliefs') or [],
                            observed_traits=part_data.get('observed_traits') or [],
                            importance=part_data.get('importance') or '',
                        )

                        if not self.dry_run:
                            participation.save()
                        self.stats.record_created('EventParticipation')

                    total += 1

        self.log_detail(f"    Processed {total} participations")

    # =========================================================================
    # Phase 6: Entity Involvements
    # =========================================================================

    def import_object_involvements(self, events_data: List[Dict]):
        """Import object involvements from event files."""
        self.log_progress(f"  Importing object involvements...")

        total = 0
        for episode_file_data in events_data:
            for event_data in episode_file_data.get('events', []):
                event_uuid = event_data.get('fabula_uuid') or event_data.get('event_uuid', '')
                event = self.events_cache.get(event_uuid)

                if not event:
                    continue

                involvements = event_data.get('object_involvements') or []

                for inv_data in involvements:
                    obj_uuid = inv_data.get('object_uuid', '')
                    obj = self.objects_cache.get(obj_uuid)

                    if not obj:
                        self.stats.record_error(f"Object {obj_uuid} not found for involvement")
                        continue

                    # Check if involvement already exists
                    involvement = ObjectInvolvement.objects.filter(
                        event=event,
                        object=obj
                    ).first()

                    if involvement:
                        involvement.description_of_involvement = inv_data.get('description_of_involvement') or ''
                        involvement.status_before_event = inv_data.get('status_before_event') or ''
                        involvement.status_after_event = inv_data.get('status_after_event') or ''

                        if not self.dry_run:
                            involvement.save()
                        self.stats.record_updated('ObjectInvolvement')
                    else:
                        involvement = ObjectInvolvement(
                            event=event,
                            object=obj,
                            description_of_involvement=inv_data.get('description_of_involvement') or '',
                            status_before_event=inv_data.get('status_before_event') or '',
                            status_after_event=inv_data.get('status_after_event') or '',
                        )

                        if not self.dry_run:
                            involvement.save()
                        self.stats.record_created('ObjectInvolvement')

                    total += 1

        self.log_detail(f"    Processed {total} object involvements")

    def import_location_involvements(self, events_data: List[Dict]):
        """Import location involvements from event files."""
        self.log_progress(f"  Importing location involvements...")

        total = 0
        for episode_file_data in events_data:
            for event_data in episode_file_data.get('events', []):
                event_uuid = event_data.get('fabula_uuid') or event_data.get('event_uuid', '')
                event = self.events_cache.get(event_uuid)

                if not event:
                    continue

                involvements = event_data.get('location_involvements') or []

                for inv_data in involvements:
                    loc_uuid = inv_data.get('location_uuid', '')
                    location = self.locations_cache.get(loc_uuid)

                    if not location:
                        self.stats.record_error(f"Location {loc_uuid} not found for involvement")
                        continue

                    # Check if involvement already exists
                    involvement = LocationInvolvement.objects.filter(
                        event=event,
                        location=location
                    ).first()

                    if involvement:
                        involvement.description_of_involvement = inv_data.get('description_of_involvement') or ''
                        involvement.observed_atmosphere = inv_data.get('observed_atmosphere') or ''
                        involvement.functional_role = inv_data.get('functional_role') or ''
                        involvement.symbolic_significance = inv_data.get('symbolic_significance') or ''
                        involvement.access_restrictions = inv_data.get('access_restrictions') or ''
                        involvement.key_environmental_details = inv_data.get('key_environmental_details') or []

                        if not self.dry_run:
                            involvement.save()
                        self.stats.record_updated('LocationInvolvement')
                    else:
                        involvement = LocationInvolvement(
                            event=event,
                            location=location,
                            description_of_involvement=inv_data.get('description_of_involvement') or '',
                            observed_atmosphere=inv_data.get('observed_atmosphere') or '',
                            functional_role=inv_data.get('functional_role') or '',
                            symbolic_significance=inv_data.get('symbolic_significance') or '',
                            access_restrictions=inv_data.get('access_restrictions') or '',
                            key_environmental_details=inv_data.get('key_environmental_details') or [],
                        )

                        if not self.dry_run:
                            involvement.save()
                        self.stats.record_created('LocationInvolvement')

                    total += 1

        self.log_detail(f"    Processed {total} location involvements")

    def import_organization_involvements(self, events_data: List[Dict]):
        """Import organization involvements from event files."""
        self.log_progress(f"  Importing organization involvements...")

        total = 0
        for episode_file_data in events_data:
            for event_data in episode_file_data.get('events', []):
                event_uuid = event_data.get('fabula_uuid') or event_data.get('event_uuid', '')
                event = self.events_cache.get(event_uuid)

                if not event:
                    continue

                involvements = event_data.get('organization_involvements') or []

                for inv_data in involvements:
                    org_uuid = inv_data.get('organization_uuid', '')
                    organization = self.organizations_cache.get(org_uuid)

                    if not organization:
                        self.stats.record_error(f"Organization {org_uuid} not found for involvement")
                        continue

                    # Check if involvement already exists
                    involvement = OrganizationInvolvement.objects.filter(
                        event=event,
                        organization=organization
                    ).first()

                    if involvement:
                        involvement.description_of_involvement = inv_data.get('description_of_involvement') or ''
                        involvement.active_representation = inv_data.get('active_representation') or ''
                        involvement.power_dynamics = inv_data.get('power_dynamics') or ''
                        involvement.organizational_goals = inv_data.get('organizational_goals') or []
                        involvement.influence_mechanisms = inv_data.get('influence_mechanisms') or []
                        involvement.institutional_impact = inv_data.get('institutional_impact') or ''
                        involvement.internal_dynamics = inv_data.get('internal_dynamics') or ''

                        if not self.dry_run:
                            involvement.save()
                        self.stats.record_updated('OrganizationInvolvement')
                    else:
                        involvement = OrganizationInvolvement(
                            event=event,
                            organization=organization,
                            description_of_involvement=inv_data.get('description_of_involvement') or '',
                            active_representation=inv_data.get('active_representation') or '',
                            power_dynamics=inv_data.get('power_dynamics') or '',
                            organizational_goals=inv_data.get('organizational_goals') or [],
                            influence_mechanisms=inv_data.get('influence_mechanisms') or [],
                            institutional_impact=inv_data.get('institutional_impact') or '',
                            internal_dynamics=inv_data.get('internal_dynamics') or '',
                        )

                        if not self.dry_run:
                            involvement.save()
                        self.stats.record_created('OrganizationInvolvement')

                    total += 1

        self.log_detail(f"    Processed {total} organization involvements")

    # =========================================================================
    # Phase 7: Narrative Connections
    # =========================================================================

    def import_connections(self, connections_data: List[Dict]):
        """Import narrative connections with GER cross-season resolution."""
        self.log_progress(f"  Importing {len(connections_data)} narrative connections...")

        # Build cache of existing connections by global_id for cross-season matching
        connections_by_global_id = {
            c.global_id: c for c in NarrativeConnection.objects.exclude(global_id__isnull=True).exclude(global_id='')
        }

        for conn_data in connections_data:
            from_uuid = conn_data['from_event_uuid']
            to_uuid = conn_data['to_event_uuid']

            from_event = self.events_cache.get(from_uuid)
            to_event = self.events_cache.get(to_uuid)

            if not from_event or not to_event:
                self.stats.record_error(
                    f"Events not found for connection: {from_uuid} -> {to_uuid}"
                )
                continue

            conn_type = conn_data['connection_type']
            global_id = conn_data.get('global_id', '')
            fabula_uuid = conn_data.get('fabula_uuid') or conn_data.get('connection_uuid', '')

            # Cross-season resolution: first try to find by global_id
            connection = None
            cross_season_match = False
            if global_id and global_id in connections_by_global_id:
                connection = connections_by_global_id[global_id]
                cross_season_match = True
                self.log_detail(f"    Cross-season match for connection: {global_id}")

            # Fall back to event pair + type lookup
            if not connection:
                connection = NarrativeConnection.objects.filter(
                    from_event=from_event,
                    to_event=to_event,
                    connection_type=conn_type
                ).first()

            if connection:
                # Update existing
                connection.strength = conn_data.get('strength', 'medium')
                connection.description = conn_data.get('description', '')
                if fabula_uuid:
                    connection.fabula_uuid = fabula_uuid
                if global_id:
                    connection.global_id = global_id

                if not self.dry_run:
                    connection.save()
                self.stats.record_updated('NarrativeConnection')
            else:
                # Create new
                connection = NarrativeConnection(
                    fabula_uuid=fabula_uuid,
                    global_id=global_id,
                    from_event=from_event,
                    to_event=to_event,
                    connection_type=conn_type,
                    strength=conn_data.get('strength', 'medium'),
                    description=conn_data.get('description', ''),
                )

                if not self.dry_run:
                    connection.save()
                self.stats.record_created('NarrativeConnection')

            self.log_detail(f"    {'Updated' if connection.pk else 'Created'} {conn_type} connection")

    # =========================================================================
    # Utilities
    # =========================================================================

    def log_progress(self, message: str):
        """Log a progress message with emoji."""
        icon = "🔍" if self.dry_run else "⚙️"
        self.stdout.write(f"{icon} {message}")

    def log_info(self, message: str):
        """Log an informational message."""
        self.stdout.write(f"ℹ️  {message}")

    def log_detail(self, message: str):
        """Log a detailed message (only in verbose mode)."""
        if self.verbose:
            self.stdout.write(f"  {message}")

    # =========================================================================
    # Cleanup (remove deprecated entities not in export)
    # =========================================================================

    def run_cleanup(
        self,
        series_data,  # Can be Dict or List[Dict]
        events_data: List[Dict],
        characters_data: List[Dict],
        organizations_data: List[Dict],
        locations_data: List[Dict]
    ):
        """
        Delete entities from the database that are not in the export.

        This removes deprecated entities that were previously imported
        but are no longer in the canonical export.
        """
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Cleanup Phase: Removing deprecated entities")
        self.stdout.write("=" * 60)

        total_deleted = 0

        # Extract UUIDs from series hierarchy
        series_list = series_data if isinstance(series_data, list) else [series_data]
        series_uuids = set()
        season_uuids = set()
        episode_uuids = set()

        for series in series_list:
            if series.get('fabula_uuid'):
                series_uuids.add(series['fabula_uuid'])
            for season in series.get('seasons', []):
                if season.get('fabula_uuid'):
                    season_uuids.add(season['fabula_uuid'])
                for episode in season.get('episodes', []):
                    if episode.get('fabula_uuid'):
                        episode_uuids.add(episode['fabula_uuid'])

        # Extract event UUIDs from events data (list of episode event files)
        event_uuids = set()
        for episode_events in events_data:
            for event in episode_events.get('events', []):
                if event.get('fabula_uuid'):
                    event_uuids.add(event['fabula_uuid'])

        # Cleanup Events first (they reference Episodes)
        deleted = self._cleanup_model(EventPage, 'fabula_uuid', event_uuids, 'events')
        total_deleted += deleted

        # Cleanup Episodes (they reference Seasons)
        deleted = self._cleanup_model(EpisodePage, 'fabula_uuid', episode_uuids, 'episodes')
        total_deleted += deleted

        # Cleanup Seasons (they reference Series)
        deleted = self._cleanup_model(SeasonPage, 'fabula_uuid', season_uuids, 'seasons')
        total_deleted += deleted

        # Cleanup Series
        deleted = self._cleanup_model(SeriesIndexPage, 'fabula_uuid', series_uuids, 'series')
        total_deleted += deleted

        # Cleanup Characters
        char_uuids = {c.get('fabula_uuid') for c in characters_data if c.get('fabula_uuid')}
        deleted = self._cleanup_model(CharacterPage, 'fabula_uuid', char_uuids, 'characters')
        total_deleted += deleted

        # Cleanup Organizations
        org_uuids = {o.get('fabula_uuid') for o in organizations_data if o.get('fabula_uuid')}
        deleted = self._cleanup_model(OrganizationPage, 'fabula_uuid', org_uuids, 'organizations')
        total_deleted += deleted

        # Cleanup Locations
        loc_uuids = {l.get('fabula_uuid') for l in locations_data if l.get('fabula_uuid')}
        deleted = self._cleanup_model(Location, 'fabula_uuid', loc_uuids, 'locations')
        total_deleted += deleted

        self.stdout.write("=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Cleanup complete: deleted {total_deleted} deprecated entities"))

    def _cleanup_model(self, model_class, uuid_field: str, canonical_uuids: set, label: str) -> int:
        """Delete objects whose UUID is not in the canonical set."""
        model_name = model_class.__name__

        all_objects = model_class.objects.all()
        total_count = all_objects.count()

        deprecated = []
        for obj in all_objects:
            obj_uuid = getattr(obj, uuid_field, None)
            if obj_uuid and obj_uuid not in canonical_uuids:
                deprecated.append(obj)

        self.stdout.write(f"\n{model_name}:")
        self.stdout.write(f"  Canonical in export: {len(canonical_uuids)}")
        self.stdout.write(f"  Total in database: {total_count}")
        self.stdout.write(f"  Deprecated (deleting): {len(deprecated)}")

        if deprecated:
            # Show first few
            for obj in deprecated[:3]:
                name = getattr(obj, 'canonical_name', None) or getattr(obj, 'name', None) or getattr(obj, 'title', str(obj))
                self.stdout.write(f"    - {name}")
            if len(deprecated) > 3:
                self.stdout.write(f"    ... and {len(deprecated) - 3} more")

            # Delete them
            for obj in deprecated:
                obj.delete()

            self.stdout.write(self.style.SUCCESS(f"  Deleted {len(deprecated)} {label}"))

        return len(deprecated)
