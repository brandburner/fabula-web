"""
Fabula YAML → Wagtail Import Command

Django management command to import narrative data from YAML files
into Wagtail pages and models.

Usage:
    python manage.py import_fabula ./fabula_export

The import is idempotent - running it multiple times with the same
data will update existing records rather than creating duplicates.
This is achieved by using fabula_uuid as the lookup key.

Import Order (respecting dependencies):
1. Themes (snippets, no dependencies)
2. Conflict Arcs (snippets, no dependencies)
3. Locations (snippets, self-referential for parent)
4. Organizations (pages, no dependencies)
5. Objects (pages, depend on organizations for ownership)
6. Series → Seasons → Episodes (page hierarchy)
7. Characters (pages, depend on organizations)
8. Events (pages, depend on episodes, locations, themes, arcs)
9. Event Participations (inline, depend on events and characters)
10. Object Involvements (inline, depend on events and objects)
11. Location Involvements (inline, depend on events and locations)
12. Organization Involvements (inline, depend on events and organizations)
13. Narrative Connections (model, depend on events)
"""

import os
import yaml
from typing import Dict, Any, Optional, List
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from wagtail.models import Page

# Import your models - adjust path as needed
from narrative.models import (
    Theme, ConflictArc, Location,
    SeriesIndexPage, SeasonPage, EpisodePage,
    CharacterPage, CharacterIndexPage,
    OrganizationPage, OrganizationIndexPage,
    ObjectPage, ObjectIndexPage,
    EventPage, EventIndexPage,
    EventParticipation, NarrativeConnection,
    ObjectInvolvement, LocationInvolvement, OrganizationInvolvement,
    CharacterEpisodeProfile,
    ConnectionType, ConnectionStrength, CharacterType, ArcType
)


class Command(BaseCommand):
    help = 'Import Fabula narrative data from YAML files into Wagtail'

    def add_arguments(self, parser):
        parser.add_argument(
            'source_dir',
            type=str,
            help='Directory containing YAML export files'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Parse and validate without saving to database'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing data before import (DANGEROUS)'
        )

    def handle(self, *args, **options):
        source_dir = options['source_dir']
        dry_run = options['dry_run']
        clear = options['clear']

        if not os.path.isdir(source_dir):
            raise CommandError(f"Directory not found: {source_dir}")

        self.stdout.write(f"\n🚀 Fabula YAML → Wagtail Import")
        self.stdout.write(f"   Source: {source_dir}")
        self.stdout.write(f"   Dry run: {dry_run}")
        self.stdout.write("")

        # Load manifest
        manifest = self._load_yaml(os.path.join(source_dir, 'manifest.yaml'))
        self.stdout.write(f"📋 Manifest: {manifest.get('series_title', 'Unknown')}")
        self.stdout.write(f"   Exported: {manifest.get('export_date', 'Unknown')}")
        self.stdout.write("")

        # UUID lookup caches (fabula_uuid → Wagtail object)
        self.theme_cache: Dict[str, Theme] = {}
        self.arc_cache: Dict[str, ConflictArc] = {}
        self.location_cache: Dict[str, Location] = {}
        self.org_cache: Dict[str, OrganizationPage] = {}
        self.object_cache: Dict[str, ObjectPage] = {}
        self.character_cache: Dict[str, CharacterPage] = {}
        self.episode_cache: Dict[str, EpisodePage] = {}
        self.event_cache: Dict[str, EventPage] = {}

        # Stats
        self.stats = {
            'themes': 0,
            'arcs': 0,
            'locations': 0,
            'objects': 0,
            'organizations': 0,
            'characters': 0,
            'episodes': 0,
            'events': 0,
            'participations': 0,
            'object_involvements': 0,
            'location_involvements': 0,
            'organization_involvements': 0,
            'connections': 0,
        }

        try:
            with transaction.atomic():
                if clear:
                    self._clear_existing_data()

                # Import in dependency order
                self._import_themes(source_dir)
                self._import_arcs(source_dir)
                self._import_locations(source_dir)
                self._import_organizations(source_dir)
                self._import_objects(source_dir)
                self._import_series_structure(source_dir)
                self._import_characters(source_dir)
                self._import_events(source_dir)
                self._import_connections(source_dir)

                if dry_run:
                    self.stdout.write("\n⚠️  DRY RUN - Rolling back transaction")
                    raise DryRunRollback()

        except DryRunRollback:
            pass

        self._print_stats()

    # =========================================================================
    # YAML Loading
    # =========================================================================

    def _load_yaml(self, filepath: str) -> Dict[str, Any]:
        """Load and parse a YAML file."""
        if not os.path.exists(filepath):
            self.stdout.write(self.style.WARNING(f"  ⚠ File not found: {filepath}"))
            return {}
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}

    # =========================================================================
    # Import Methods
    # =========================================================================

    def _import_themes(self, source_dir: str):
        """Import themes as snippets."""
        self.stdout.write("💡 Importing themes...")
        data = self._load_yaml(os.path.join(source_dir, 'themes.yaml'))
        
        for theme_data in data.get('themes', []):
            theme, created = Theme.objects.update_or_create(
                fabula_uuid=theme_data['fabula_uuid'],
                defaults={
                    'name': theme_data['name'],
                    'description': theme_data.get('description', ''),
                }
            )
            self.theme_cache[theme_data['fabula_uuid']] = theme
            self.stats['themes'] += 1
            
            action = "Created" if created else "Updated"
            self.stdout.write(f"  ✓ {action}: {theme.name}")

    def _import_arcs(self, source_dir: str):
        """Import conflict arcs as snippets."""
        self.stdout.write("📈 Importing conflict arcs...")
        data = self._load_yaml(os.path.join(source_dir, 'arcs.yaml'))
        
        for arc_data in data.get('arcs', []):
            arc, created = ConflictArc.objects.update_or_create(
                fabula_uuid=arc_data['fabula_uuid'],
                defaults={
                    'title': arc_data['title'],
                    'description': arc_data.get('description', ''),
                    'arc_type': arc_data.get('arc_type', ArcType.INTERPERSONAL),
                }
            )
            self.arc_cache[arc_data['fabula_uuid']] = arc
            self.stats['arcs'] += 1

    def _import_locations(self, source_dir: str):
        """Import locations as snippets (two-pass for parent refs)."""
        self.stdout.write("📍 Importing locations...")
        data = self._load_yaml(os.path.join(source_dir, 'locations.yaml'))
        locations_data = data.get('locations', [])
        
        # First pass: create all locations without parents
        for loc_data in locations_data:
            location, created = Location.objects.update_or_create(
                fabula_uuid=loc_data['fabula_uuid'],
                defaults={
                    'canonical_name': loc_data['canonical_name'],
                    'description': loc_data.get('description', ''),
                    'location_type': loc_data.get('location_type', ''),
                }
            )
            self.location_cache[loc_data['fabula_uuid']] = location
            self.stats['locations'] += 1
        
        # Second pass: set parent relationships
        for loc_data in locations_data:
            parent_uuid = loc_data.get('parent_location_uuid')
            if parent_uuid and parent_uuid in self.location_cache:
                location = self.location_cache[loc_data['fabula_uuid']]
                location.parent_location = self.location_cache[parent_uuid]
                location.save()

    def _import_organizations(self, source_dir: str):
        """Import organizations as pages."""
        self.stdout.write("🏛️  Importing organizations...")
        data = self._load_yaml(os.path.join(source_dir, 'organizations.yaml'))

        # Find or create organization index page
        org_index = OrganizationIndexPage.objects.first()
        if not org_index:
            # Will be created later when series structure is imported
            self.stdout.write("  ⚠ OrganizationIndexPage not yet created, deferring...")
            # Store for later
            self._deferred_orgs = data.get('organizations', [])
            return

        for org_data in data.get('organizations', []):
            self._import_single_organization(org_index, org_data)

    def _import_single_organization(self, org_index: OrganizationIndexPage, org_data: dict):
        """Import a single organization."""
        try:
            org = OrganizationPage.objects.get(fabula_uuid=org_data['fabula_uuid'])
            org.canonical_name = org_data['canonical_name']
            org.title = org_data['canonical_name']
            org.description = org_data.get('description', '')
            org.sphere_of_influence = org_data.get('sphere_of_influence', '')
            org.save()
        except OrganizationPage.DoesNotExist:
            org = OrganizationPage(
                title=org_data['canonical_name'],
                slug=slugify(org_data['canonical_name'])[:50],
                fabula_uuid=org_data['fabula_uuid'],
                canonical_name=org_data['canonical_name'],
                description=org_data.get('description', ''),
                sphere_of_influence=org_data.get('sphere_of_influence', ''),
            )
            org_index.add_child(instance=org)

        self.org_cache[org_data['fabula_uuid']] = org
        self.stats['organizations'] += 1

    def _import_objects(self, source_dir: str):
        """Import objects as pages."""
        self.stdout.write("📦 Importing objects...")
        data = self._load_yaml(os.path.join(source_dir, 'objects.yaml'))

        if not data:
            self.stdout.write("  ⚠ No objects.yaml found")
            return

        # Find or create object index page
        obj_index = ObjectIndexPage.objects.first()
        if not obj_index:
            # Will be created later when series structure is imported
            self.stdout.write("  ⚠ ObjectIndexPage not yet created, deferring...")
            self._deferred_objects = data.get('objects', [])
            return

        for obj_data in data.get('objects', []):
            self._import_single_object(obj_index, obj_data)

    def _import_single_object(self, obj_index: ObjectIndexPage, obj_data: dict):
        """Import a single object."""
        try:
            obj = ObjectPage.objects.get(fabula_uuid=obj_data['fabula_uuid'])
            obj.canonical_name = obj_data['canonical_name']
            obj.title = obj_data['canonical_name']
            obj.description = obj_data.get('description', '')
            obj.purpose = obj_data.get('purpose', '')
            obj.significance = obj_data.get('significance', '')
            obj.save()
        except ObjectPage.DoesNotExist:
            obj = ObjectPage(
                title=obj_data['canonical_name'],
                slug=slugify(obj_data['canonical_name'])[:50],
                fabula_uuid=obj_data['fabula_uuid'],
                canonical_name=obj_data['canonical_name'],
                description=obj_data.get('description', ''),
                purpose=obj_data.get('purpose', ''),
                significance=obj_data.get('significance', ''),
            )
            obj_index.add_child(instance=obj)

        # Set owner relationships if present
        owner_agent_uuid = obj_data.get('owner_agent_uuid')
        owner_org_uuid = obj_data.get('owner_org_uuid')

        if owner_agent_uuid and owner_agent_uuid in self.character_cache:
            obj.potential_owner = self.character_cache[owner_agent_uuid]
            obj.save()
        elif owner_org_uuid and owner_org_uuid in self.org_cache:
            obj.owner_organization = self.org_cache[owner_org_uuid]
            obj.save()

        self.object_cache[obj_data['fabula_uuid']] = obj
        self.stats['objects'] += 1

    def _import_series_structure(self, source_dir: str):
        """Import series → seasons → episodes hierarchy."""
        self.stdout.write("📺 Importing series structure...")
        data = self._load_yaml(os.path.join(source_dir, 'series.yaml'))
        
        if not data:
            self.stdout.write(self.style.WARNING("  ⚠ No series data found"))
            return

        # Get or create root page
        root_page = Page.objects.get(depth=1)
        
        # Create or update series page
        series_slug = slugify(data['title'])
        try:
            series_page = SeriesIndexPage.objects.get(fabula_uuid=data['fabula_uuid'])
            series_page.title = data['title']
            series_page.description = data.get('description', '')
            series_page.save()
            self.stdout.write(f"  ✓ Updated series: {data['title']}")
        except SeriesIndexPage.DoesNotExist:
            series_page = SeriesIndexPage(
                title=data['title'],
                slug=series_slug,
                fabula_uuid=data['fabula_uuid'],
                description=data.get('description', ''),
            )
            root_page.add_child(instance=series_page)
            self.stdout.write(f"  ✓ Created series: {data['title']}")

        # Create index pages under series if they don't exist
        self._ensure_index_pages(series_page)

        # Import seasons and episodes
        for season_data in data.get('seasons', []):
            season_page = self._import_season(series_page, season_data)
            
            for episode_data in season_data.get('episodes', []):
                self._import_episode(season_page, episode_data)

    def _ensure_index_pages(self, series_page: SeriesIndexPage):
        """Ensure character, event, org, object index pages exist."""
        index_types = [
            (CharacterIndexPage, 'characters', 'Characters'),
            (EventIndexPage, 'events', 'Events'),
            (OrganizationIndexPage, 'organizations', 'Organizations'),
            (ObjectIndexPage, 'objects', 'Objects'),
        ]

        for page_class, slug, title in index_types:
            if not page_class.objects.child_of(series_page).exists():
                index_page = page_class(title=title, slug=slug)
                series_page.add_child(instance=index_page)

    def _import_season(self, series_page: SeriesIndexPage, data: dict) -> SeasonPage:
        """Import a season under the series."""
        try:
            season = SeasonPage.objects.get(fabula_uuid=data['fabula_uuid'])
            season.title = f"Season {data['season_number']}"
            season.season_number = data['season_number']
            season.save()
        except SeasonPage.DoesNotExist:
            season = SeasonPage(
                title=f"Season {data['season_number']}",
                slug=f"season-{data['season_number']}",
                fabula_uuid=data['fabula_uuid'],
                season_number=data['season_number'],
                description=data.get('description', ''),
            )
            series_page.add_child(instance=season)
        
        return season

    def _import_episode(self, season_page: SeasonPage, data: dict) -> EpisodePage:
        """Import an episode under the season."""
        try:
            episode = EpisodePage.objects.get(fabula_uuid=data['fabula_uuid'])
            episode.title = data['title']
            episode.episode_number = data['episode_number']
            episode.logline = data.get('logline', '')
            episode.high_level_summary = data.get('high_level_summary', '')
            episode.dominant_tone = data.get('dominant_tone', '')
            episode.save()
        except EpisodePage.DoesNotExist:
            episode = EpisodePage(
                title=data['title'],
                slug=slugify(data['title'])[:50],
                fabula_uuid=data['fabula_uuid'],
                episode_number=data['episode_number'],
                logline=data.get('logline', ''),
                high_level_summary=data.get('high_level_summary', ''),
                dominant_tone=data.get('dominant_tone', ''),
            )
            season_page.add_child(instance=episode)
        
        self.episode_cache[data['fabula_uuid']] = episode
        self.stats['episodes'] += 1
        return episode

    def _import_characters(self, source_dir: str):
        """Import characters as pages."""
        self.stdout.write("👥 Importing characters...")
        data = self._load_yaml(os.path.join(source_dir, 'characters.yaml'))
        
        # Find character index page
        char_index = CharacterIndexPage.objects.first()
        if not char_index:
            self.stdout.write(self.style.ERROR("  ✗ No CharacterIndexPage found"))
            return
        
        for char_data in data.get('characters', []):
            try:
                character = CharacterPage.objects.get(fabula_uuid=char_data['fabula_uuid'])
                # Update existing
                character.canonical_name = char_data['canonical_name']
                character.title = char_data['canonical_name']
                character.title_role = char_data.get('title_role', '')
                character.description = char_data.get('description', '')
                character.traits = char_data.get('traits', [])
                character.aliases = char_data.get('aliases', [])
                character.character_type = char_data.get('character_type', CharacterType.RECURRING)
                character.sphere_of_influence = char_data.get('sphere_of_influence', '')
                character.appearance_count = char_data.get('appearance_count', 0)
                character.save()
            except CharacterPage.DoesNotExist:
                character = CharacterPage(
                    title=char_data['canonical_name'],
                    slug=slugify(char_data['canonical_name'])[:50],
                    fabula_uuid=char_data['fabula_uuid'],
                    canonical_name=char_data['canonical_name'],
                    title_role=char_data.get('title_role', ''),
                    description=char_data.get('description', ''),
                    traits=char_data.get('traits', []),
                    aliases=char_data.get('aliases', []),
                    character_type=char_data.get('character_type', CharacterType.RECURRING),
                    sphere_of_influence=char_data.get('sphere_of_influence', ''),
                    appearance_count=char_data.get('appearance_count', 0),
                )
                char_index.add_child(instance=character)
            
            self.character_cache[char_data['fabula_uuid']] = character
            self.stats['characters'] += 1

    def _import_events(self, source_dir: str):
        """Import events from per-episode YAML files."""
        self.stdout.write("⚡ Importing events...")
        events_dir = os.path.join(source_dir, 'events')
        
        if not os.path.isdir(events_dir):
            self.stdout.write(self.style.WARNING("  ⚠ No events directory found"))
            return
        
        # Find event index page
        event_index = EventIndexPage.objects.first()
        if not event_index:
            self.stdout.write(self.style.ERROR("  ✗ No EventIndexPage found"))
            return
        
        # Process each episode file
        for filename in sorted(os.listdir(events_dir)):
            if not filename.endswith('.yaml'):
                continue
            
            filepath = os.path.join(events_dir, filename)
            data = self._load_yaml(filepath)
            
            episode_uuid = data.get('episode_uuid')
            episode = self.episode_cache.get(episode_uuid)
            
            if not episode:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠ Episode not found for {filename}"
                ))
                continue
            
            for event_data in data.get('events', []):
                self._import_event(event_index, episode, event_data)

    def _import_event(self, event_index: EventIndexPage, episode: EpisodePage, data: dict):
        """Import a single event with its participations."""
        try:
            event = EventPage.objects.get(fabula_uuid=data['fabula_uuid'])
            # Update existing
            event.title = data['title']
            event.description = data.get('description', '')
            event.episode = episode
            event.scene_sequence = data.get('scene_sequence', 0)
            event.sequence_in_scene = data.get('sequence_in_scene', 0)
            event.key_dialogue = data.get('key_dialogue', [])
            event.is_flashback = data.get('is_flashback', False)
            event.save()
            created = False
        except EventPage.DoesNotExist:
            event = EventPage(
                title=data['title'],
                slug=slugify(data['title'])[:50],
                fabula_uuid=data['fabula_uuid'],
                description=data.get('description', ''),
                episode=episode,
                scene_sequence=data.get('scene_sequence', 0),
                sequence_in_scene=data.get('sequence_in_scene', 0),
                key_dialogue=data.get('key_dialogue', []),
                is_flashback=data.get('is_flashback', False),
            )
            event_index.add_child(instance=event)
            created = True
        
        # Set location
        location_uuid = data.get('location_uuid')
        if location_uuid and location_uuid in self.location_cache:
            event.location = self.location_cache[location_uuid]
            event.save()
        
        # Set themes (M2M)
        theme_uuids = data.get('theme_uuids', [])
        themes = [self.theme_cache[uuid] for uuid in theme_uuids if uuid in self.theme_cache]
        event.themes.set(themes)
        
        # Set arcs (M2M)
        arc_uuids = data.get('arc_uuids', [])
        arcs = [self.arc_cache[uuid] for uuid in arc_uuids if uuid in self.arc_cache]
        event.arcs.set(arcs)
        
        # Import participations
        self._import_participations(event, data.get('participations', []))

        # Import involvements
        self._import_object_involvements(event, data.get('object_involvements', []))
        self._import_location_involvements(event, data.get('location_involvements', []))
        self._import_organization_involvements(event, data.get('organization_involvements', []))

        self.event_cache[data['fabula_uuid']] = event
        self.stats['events'] += 1

    def _import_participations(self, event: EventPage, participations_data: List[dict]):
        """Import character participations for an event."""
        # Clear existing participations for this event
        EventParticipation.objects.filter(event=event).delete()
        
        for i, p_data in enumerate(participations_data):
            char_uuid = p_data.get('character_uuid')
            character = self.character_cache.get(char_uuid)
            
            if not character:
                continue
            
            EventParticipation.objects.create(
                event=event,
                character=character,
                sort_order=i,
                emotional_state=p_data.get('emotional_state', ''),
                goals=p_data.get('goals', []),
                what_happened=p_data.get('what_happened', ''),
                observed_status=p_data.get('observed_status', ''),
                beliefs=p_data.get('beliefs', []),
                observed_traits=p_data.get('observed_traits', []),
                importance=p_data.get('importance', 'secondary'),
            )
            self.stats['participations'] += 1

    def _import_object_involvements(self, event: EventPage, involvements_data: List[dict]):
        """Import object involvements for an event."""
        # Clear existing involvements for this event
        ObjectInvolvement.objects.filter(event=event).delete()

        for i, inv_data in enumerate(involvements_data):
            obj_uuid = inv_data.get('object_uuid')
            obj = self.object_cache.get(obj_uuid)

            if not obj:
                continue

            ObjectInvolvement.objects.create(
                event=event,
                object=obj,
                sort_order=i,
                description_of_involvement=inv_data.get('description_of_involvement', ''),
                status_before_event=inv_data.get('status_before_event', ''),
                status_after_event=inv_data.get('status_after_event', ''),
            )
            self.stats['object_involvements'] += 1

    def _import_location_involvements(self, event: EventPage, involvements_data: List[dict]):
        """Import location involvements for an event."""
        # Clear existing involvements for this event
        LocationInvolvement.objects.filter(event=event).delete()

        for i, inv_data in enumerate(involvements_data):
            loc_uuid = inv_data.get('location_uuid')
            loc = self.location_cache.get(loc_uuid)

            if not loc:
                continue

            LocationInvolvement.objects.create(
                event=event,
                location=loc,
                sort_order=i,
                description_of_involvement=inv_data.get('description_of_involvement', ''),
                observed_atmosphere=inv_data.get('observed_atmosphere', ''),
                functional_role=inv_data.get('functional_role', ''),
                symbolic_significance=inv_data.get('symbolic_significance', ''),
                access_restrictions=inv_data.get('access_restrictions', ''),
                key_environmental_details=inv_data.get('key_environmental_details', []),
            )
            self.stats['location_involvements'] += 1

    def _import_organization_involvements(self, event: EventPage, involvements_data: List[dict]):
        """Import organization involvements for an event."""
        # Clear existing involvements for this event
        OrganizationInvolvement.objects.filter(event=event).delete()

        for i, inv_data in enumerate(involvements_data):
            org_uuid = inv_data.get('organization_uuid')
            org = self.org_cache.get(org_uuid)

            if not org:
                continue

            OrganizationInvolvement.objects.create(
                event=event,
                organization=org,
                sort_order=i,
                description_of_involvement=inv_data.get('description_of_involvement', ''),
                active_representation=inv_data.get('active_representation', ''),
                power_dynamics=inv_data.get('power_dynamics', ''),
                organizational_goals=inv_data.get('organizational_goals', []),
                influence_mechanisms=inv_data.get('influence_mechanisms', []),
                institutional_impact=inv_data.get('institutional_impact', ''),
                internal_dynamics=inv_data.get('internal_dynamics', ''),
            )
            self.stats['organization_involvements'] += 1

    def _import_connections(self, source_dir: str):
        """Import narrative connections between events."""
        self.stdout.write("🔗 Importing narrative connections...")
        data = self._load_yaml(os.path.join(source_dir, 'connections.yaml'))
        
        for conn_data in data.get('connections', []):
            from_uuid = conn_data.get('from_event_uuid')
            to_uuid = conn_data.get('to_event_uuid')
            
            from_event = self.event_cache.get(from_uuid)
            to_event = self.event_cache.get(to_uuid)
            
            if not from_event or not to_event:
                continue
            
            NarrativeConnection.objects.update_or_create(
                fabula_uuid=conn_data['fabula_uuid'],
                defaults={
                    'from_event': from_event,
                    'to_event': to_event,
                    'connection_type': conn_data.get('connection_type', ConnectionType.CAUSAL),
                    'strength': conn_data.get('strength', ConnectionStrength.MEDIUM),
                    'description': conn_data.get('description', ''),
                }
            )
            self.stats['connections'] += 1

    def _clear_existing_data(self):
        """Clear all existing narrative data. USE WITH CAUTION."""
        self.stdout.write(self.style.WARNING("⚠️  Clearing existing data..."))

        NarrativeConnection.objects.all().delete()
        ObjectInvolvement.objects.all().delete()
        LocationInvolvement.objects.all().delete()
        OrganizationInvolvement.objects.all().delete()
        EventParticipation.objects.all().delete()
        EventPage.objects.all().delete()
        ObjectPage.objects.all().delete()
        CharacterPage.objects.all().delete()
        OrganizationPage.objects.all().delete()
        EpisodePage.objects.all().delete()
        SeasonPage.objects.all().delete()
        SeriesIndexPage.objects.all().delete()
        Theme.objects.all().delete()
        ConflictArc.objects.all().delete()
        Location.objects.all().delete()

    def _print_stats(self):
        """Print import statistics."""
        self.stdout.write("")
        self.stdout.write("✅ Import complete!")
        self.stdout.write(f"   Themes:                   {self.stats['themes']}")
        self.stdout.write(f"   Arcs:                     {self.stats['arcs']}")
        self.stdout.write(f"   Locations:                {self.stats['locations']}")
        self.stdout.write(f"   Objects:                  {self.stats['objects']}")
        self.stdout.write(f"   Organizations:            {self.stats['organizations']}")
        self.stdout.write(f"   Characters:               {self.stats['characters']}")
        self.stdout.write(f"   Episodes:                 {self.stats['episodes']}")
        self.stdout.write(f"   Events:                   {self.stats['events']}")
        self.stdout.write(f"   Participations:           {self.stats['participations']}")
        self.stdout.write(f"   Object involvements:      {self.stats['object_involvements']}")
        self.stdout.write(f"   Location involvements:    {self.stats['location_involvements']}")
        self.stdout.write(f"   Organization involvements:{self.stats['organization_involvements']}")
        self.stdout.write(f"   Connections:              {self.stats['connections']}")


class DryRunRollback(Exception):
    """Exception to trigger rollback in dry-run mode."""
    pass
