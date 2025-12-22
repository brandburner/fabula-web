"""
Django management command to export narrative data from Neo4j to YAML files.

This command connects to a Neo4j database containing West Wing Season 1 data
and exports it to a structured YAML format suitable for import into Wagtail.

Usage:
    python manage.py export_from_neo4j --output ./fabula_export

The command creates:
- manifest.yaml: Export metadata
- series.yaml: Series, seasons, and episodes
- characters.yaml: All character/agent data
- locations.yaml: All locations
- organizations.yaml: All organizations
- themes.yaml: All themes
- arcs.yaml: All conflict arcs
- connections.yaml: All narrative connections between events
- events/: Directory containing one YAML file per episode (s01e01.yaml, etc.)
"""

from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import os
import sys

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

import yaml
from neo4j import GraphDatabase, Driver


# =============================================================================
# YAML Configuration for Clean Multi-line Output
# =============================================================================

def str_representer(dumper, data):
    """
    Custom YAML representer for multi-line strings.
    Uses block literal style (|) for strings with newlines.
    """
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)


def setup_yaml():
    """Configure YAML for clean, readable output."""
    yaml.add_representer(str, str_representer)
    yaml.default_flow_style = False


# =============================================================================
# Neo4j Data Exporter
# =============================================================================

class Neo4jExporter:
    """
    Exports narrative graph data from Neo4j to YAML files.

    This class handles:
    1. Connecting to Neo4j
    2. Querying all entity types (Series, Episodes, Events, Characters, etc.)
    3. Extracting all relationships (participations, connections)
    4. Converting to YAML-serializable dictionaries
    5. Writing organized YAML files
    """

    def __init__(self, uri: str, user: str, password: str, output_dir: Path):
        """
        Initialize the Neo4j exporter.

        Args:
            uri: Neo4j connection URI (e.g., bolt://localhost:7689)
            user: Neo4j username
            password: Neo4j password
            output_dir: Directory to write YAML files
        """
        self.uri = uri
        self.user = user
        self.password = password
        self.output_dir = output_dir
        self.driver: Optional[Driver] = None

        # Statistics for manifest
        self.stats = {
            'series_count': 0,
            'season_count': 0,
            'episode_count': 0,
            'event_count': 0,
            'character_count': 0,
            'location_count': 0,
            'organization_count': 0,
            'theme_count': 0,
            'arc_count': 0,
            'connection_count': 0,
        }

    def connect(self):
        """Establish connection to Neo4j."""
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            # Verify connection
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            raise CommandError(f"Failed to connect to Neo4j: {e}")

    def close(self):
        """Close Neo4j connection."""
        if self.driver:
            self.driver.close()

    def execute_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a Cypher query and return results.

        Args:
            query: Cypher query string
            parameters: Optional query parameters

        Returns:
            List of result records as dictionaries
        """
        with self.driver.session() as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def safe_get(self, node: Any, key: str, default: Any = None) -> Any:
        """
        Safely get a property from a Neo4j node.

        Args:
            node: Neo4j node object
            key: Property key
            default: Default value if key not found

        Returns:
            Property value or default
        """
        if node is None:
            return default
        try:
            return node.get(key, default)
        except (AttributeError, TypeError):
            return default

    # =========================================================================
    # Export Series, Seasons, Episodes
    # =========================================================================

    def export_series(self) -> Dict:
        """
        Export series hierarchy: Series -> Seasons -> Episodes.

        Returns:
            Dictionary containing series data with nested seasons and episodes
        """
        print("Exporting series hierarchy...")

        # Query matches actual Neo4j schema:
        # Episode-[:BELONGS_TO_SEASON]->Season-[:BELONGS_TO_SERIES]->Series
        query = """
        MATCH (ep:Episode)-[:BELONGS_TO_SEASON]->(season:Season)-[:BELONGS_TO_SERIES]->(s:Series)
        RETURN s, season, ep
        ORDER BY season.number, ep.number
        """

        results = self.execute_query(query)

        # Organize hierarchically
        series_map = {}

        for record in results:
            series_node = record['s']
            season_node = record['season']
            episode_node = record['ep']

            series_uuid = self.safe_get(series_node, 'series_uuid')
            if not series_uuid:
                continue

            # Initialize series
            if series_uuid not in series_map:
                series_map[series_uuid] = {
                    'fabula_uuid': series_uuid,
                    'title': self.safe_get(series_node, 'title', 'Unknown Series'),
                    'description': self.safe_get(series_node, 'description', ''),
                    'seasons': {}
                }
                self.stats['series_count'] += 1

            # Add season
            if season_node:
                season_uuid = self.safe_get(season_node, 'season_uuid')
                season_num = self.safe_get(season_node, 'number', 0)

                if season_uuid and season_uuid not in series_map[series_uuid]['seasons']:
                    series_map[series_uuid]['seasons'][season_uuid] = {
                        'fabula_uuid': season_uuid,
                        'season_number': season_num,
                        'description': self.safe_get(season_node, 'description', ''),
                        'episodes': []
                    }
                    self.stats['season_count'] += 1

                # Add episode
                if episode_node and season_uuid:
                    episode_uuid = self.safe_get(episode_node, 'episode_uuid')
                    if episode_uuid:
                        episode_data = {
                            'fabula_uuid': episode_uuid,
                            'episode_number': self.safe_get(episode_node, 'number', 0),
                            'title': self.safe_get(episode_node, 'title') or self.safe_get(episode_node, 'episode_title', 'Untitled'),
                            'logline': self.safe_get(episode_node, 'logline', ''),
                            'high_level_summary': self.safe_get(episode_node, 'high_level_summary', ''),
                            'dominant_tone': self.safe_get(episode_node, 'final_dominant_tone', '')
                        }
                        series_map[series_uuid]['seasons'][season_uuid]['episodes'].append(episode_data)
                        self.stats['episode_count'] += 1

        # Convert seasons dict to list
        for series_uuid in series_map:
            seasons_list = sorted(
                series_map[series_uuid]['seasons'].values(),
                key=lambda s: s['season_number']
            )
            series_map[series_uuid]['seasons'] = seasons_list

        # Return all series as a list
        series_list = list(series_map.values())
        return series_list

    # =========================================================================
    # Export Characters
    # =========================================================================

    def export_characters(self) -> List[Dict]:
        """
        Export all characters/agents with their metadata.

        Returns:
            List of character dictionaries
        """
        print("Exporting characters...")

        query = """
        MATCH (a:Agent)
        OPTIONAL MATCH (a)-[:AFFILIATED_WITH]->(org:Organization)
        RETURN a, org.uuid as org_uuid
        ORDER BY a.canonical_name
        """

        results = self.execute_query(query)
        characters = []

        for record in results:
            agent = record['a']
            org_uuid = record.get('org_uuid')

            # Parse traits and aliases (may be stored as strings or lists)
            traits = self.safe_get(agent, 'foundational_traits', [])
            if isinstance(traits, str):
                traits = [t.strip() for t in traits.split(',') if t.strip()]

            aliases = self.safe_get(agent, 'aliases', [])
            if isinstance(aliases, str):
                aliases = [a.strip() for a in aliases.split(',') if a.strip()]

            character = {
                'fabula_uuid': self.safe_get(agent, 'agent_uuid', ''),
                'canonical_name': self.safe_get(agent, 'canonical_name', 'Unknown'),
                'title_role': self.safe_get(agent, 'title_role'),
                'description': self.safe_get(agent, 'foundational_description', ''),
                'traits': traits,
                'aliases': aliases,
                'character_type': self.safe_get(agent, 'character_type', 'guest'),
                'sphere_of_influence': self.safe_get(agent, 'sphere_of_influence'),
                'appearance_count': self.safe_get(agent, 'appearance_count', 0),
                'affiliated_organization_uuid': org_uuid
            }

            characters.append(character)
            self.stats['character_count'] += 1

        return characters

    # =========================================================================
    # Export Locations
    # =========================================================================

    def export_locations(self) -> List[Dict]:
        """
        Export all locations with parent relationships.

        Returns:
            List of location dictionaries
        """
        print("Exporting locations...")

        query = """
        MATCH (loc:Location)
        RETURN loc
        ORDER BY loc.canonical_name
        """

        results = self.execute_query(query)
        locations = []

        for record in results:
            loc = record['loc']

            location = {
                'fabula_uuid': self.safe_get(loc, 'location_uuid', ''),
                'canonical_name': self.safe_get(loc, 'canonical_name', 'Unknown'),
                'description': self.safe_get(loc, 'foundational_description', ''),
                'location_type': self.safe_get(loc, 'foundational_type', ''),
                'parent_location_uuid': None
            }

            locations.append(location)
            self.stats['location_count'] += 1

        return locations

    # =========================================================================
    # Export Organizations
    # =========================================================================

    def export_organizations(self) -> List[Dict]:
        """
        Export all organizations.

        Returns:
            List of organization dictionaries
        """
        print("Exporting organizations...")

        query = """
        MATCH (org:Organization)
        RETURN org
        ORDER BY org.canonical_name
        """

        results = self.execute_query(query)
        organizations = []

        for record in results:
            org = record['org']

            organization = {
                'fabula_uuid': self.safe_get(org, 'organization_uuid') or self.safe_get(org, 'org_uuid', ''),
                'canonical_name': self.safe_get(org, 'canonical_name', 'Unknown'),
                'description': self.safe_get(org, 'foundational_description', ''),
                'sphere_of_influence': self.safe_get(org, 'foundational_sphere_of_influence', '')
            }

            organizations.append(organization)
            self.stats['organization_count'] += 1

        return organizations

    # =========================================================================
    # Export Themes
    # =========================================================================

    def export_themes(self) -> List[Dict]:
        """
        Export all themes.

        Returns:
            List of theme dictionaries
        """
        print("Exporting themes...")

        query = """
        MATCH (t:Theme)
        RETURN t
        ORDER BY t.name
        """

        results = self.execute_query(query)
        themes = []

        for record in results:
            theme = record['t']

            theme_data = {
                'fabula_uuid': self.safe_get(theme, 'theme_uuid', ''),
                'name': self.safe_get(theme, 'name', 'Unknown'),
                'description': self.safe_get(theme, 'description', '')
            }

            themes.append(theme_data)
            self.stats['theme_count'] += 1

        return themes

    # =========================================================================
    # Export Conflict Arcs
    # =========================================================================

    def export_arcs(self) -> List[Dict]:
        """
        Export all conflict arcs.

        Returns:
            List of conflict arc dictionaries
        """
        print("Exporting conflict arcs...")

        query = """
        MATCH (arc:ConflictArc)
        RETURN arc
        ORDER BY arc.conflict_description
        """

        results = self.execute_query(query)
        arcs = []

        for record in results:
            arc = record['arc']

            arc_data = {
                'fabula_uuid': self.safe_get(arc, 'arc_uuid', ''),
                'title': self.safe_get(arc, 'conflict_description', 'Unknown'),
                'description': self.safe_get(arc, 'conflict_description', ''),
                'arc_type': self.safe_get(arc, 'type', 'INTERPERSONAL')
            }

            arcs.append(arc_data)
            self.stats['arc_count'] += 1

        return arcs

    # =========================================================================
    # Export Events (by episode)
    # =========================================================================

    def export_events_by_episode(self, episode_uuid: str) -> List[Dict]:
        """
        Export all events for a specific episode.

        Args:
            episode_uuid: Episode UUID to filter events

        Returns:
            List of event dictionaries with participations
        """
        query = """
        MATCH (e:Event)-[:PART_OF_EPISODE]->(ep:Episode {episode_uuid: $episode_uuid})

        // Get location
        OPTIONAL MATCH (e)-[:OCCURS_IN]->(loc:Location)

        // Get themes
        OPTIONAL MATCH (e)-[:EXEMPLIFIES_THEME]->(theme:Theme)

        // Get arcs
        OPTIONAL MATCH (e)-[:PART_OF_ARC]->(arc:ConflictArc)

        // Get participations with edge properties
        OPTIONAL MATCH (agent:Agent)-[p:PARTICIPATED_AS]->(e)

        RETURN e,
               loc.location_uuid as location_uuid,
               collect(DISTINCT theme.theme_uuid) as theme_uuids,
               collect(DISTINCT arc.arc_uuid) as arc_uuids,
               collect(DISTINCT {
                   character_uuid: agent.agent_uuid,
                   emotional_state: p.emotional_state,
                   goals: p.goals,
                   what_happened: p.what_happened,
                   observed_status: p.observed_status,
                   beliefs: p.beliefs,
                   observed_traits: p.observed_traits,
                   importance: p.importance
               }) as participations
        ORDER BY e.sequence_in_scene
        """

        results = self.execute_query(query, {'episode_uuid': episode_uuid})
        events = []

        for record in results:
            event = record['e']

            # Parse key_dialogue (may be string or list)
            key_dialogue = self.safe_get(event, 'key_dialogue', [])
            if isinstance(key_dialogue, str):
                key_dialogue = [key_dialogue] if key_dialogue else []

            # Filter out null participations (from OPTIONAL MATCH)
            participations = [
                p for p in record.get('participations', [])
                if p.get('character_uuid')
            ]

            # Clean up participation data
            for p in participations:
                # Convert goals and beliefs from string to list if needed
                if isinstance(p.get('goals'), str):
                    p['goals'] = [g.strip() for g in p['goals'].split('\n') if g.strip()]
                elif not p.get('goals'):
                    p['goals'] = []

                if isinstance(p.get('beliefs'), str):
                    p['beliefs'] = [b.strip() for b in p['beliefs'].split('\n') if b.strip()]
                elif not p.get('beliefs'):
                    p['beliefs'] = []

                if isinstance(p.get('observed_traits'), str):
                    p['observed_traits'] = [t.strip() for t in p['observed_traits'].split(',') if t.strip()]
                elif not p.get('observed_traits'):
                    p['observed_traits'] = []

                # Set defaults
                p['emotional_state'] = p.get('emotional_state') or ''
                p['what_happened'] = p.get('what_happened') or ''
                p['observed_status'] = p.get('observed_status') or ''
                p['importance'] = p.get('importance') or 'primary'

            # Filter out null UUIDs from collections
            theme_uuids = [uid for uid in record.get('theme_uuids', []) if uid]
            arc_uuids = [uid for uid in record.get('arc_uuids', []) if uid]

            event_data = {
                'fabula_uuid': self.safe_get(event, 'event_uuid', ''),
                'title': self.safe_get(event, 'title', 'Untitled Event'),
                'description': self.safe_get(event, 'description', ''),
                'episode_uuid': episode_uuid,
                'scene_sequence': self.safe_get(event, 'scene_sequence', 0),
                'sequence_in_scene': self.safe_get(event, 'sequence_in_scene', 0),
                'key_dialogue': key_dialogue,
                'is_flashback': self.safe_get(event, 'is_flashback', False),
                'location_uuid': record.get('location_uuid'),
                'theme_uuids': theme_uuids,
                'arc_uuids': arc_uuids,
                'participations': participations
            }

            events.append(event_data)
            self.stats['event_count'] += 1

        return events

    # =========================================================================
    # Export Narrative Connections
    # =========================================================================

    def export_connections(self) -> List[Dict]:
        """
        Export all narrative connections between events.

        Connections in Neo4j are between PlotBeats, so we map them to Events
        using the derived_from_beat_uuids property on Events.

        Returns:
            List of connection dictionaries
        """
        print("Exporting narrative connections...")

        # First, build a mapping of beat_uuid -> event_uuid
        beat_to_event_query = """
        MATCH (e:Event)
        WHERE e.derived_from_beat_uuids IS NOT NULL
        UNWIND e.derived_from_beat_uuids AS beat_uuid
        RETURN beat_uuid, e.event_uuid as event_uuid
        """
        beat_results = self.execute_query(beat_to_event_query)
        beat_to_event = {}
        for r in beat_results:
            beat_uuid = r.get('beat_uuid')
            if beat_uuid:
                beat_to_event[beat_uuid] = r.get('event_uuid')

        # Query all PlotBeat relationship types
        connection_types = [
            'CAUSAL', 'CHARACTER_CONTINUITY', 'THEMATIC_PARALLEL',
            'SYMBOLIC_PARALLEL', 'EMOTIONAL_ECHO', 'ESCALATION',
            'CALLBACK', 'FORESHADOWING', 'TEMPORAL', 'NARRATIVELY_FOLLOWS'
        ]

        query = """
        MATCH (from:PlotBeat)-[r]->(to:PlotBeat)
        WHERE type(r) IN $connection_types
        RETURN from.beat_uuid as from_beat,
               to.beat_uuid as to_beat,
               type(r) as connection_type,
               r.strength as strength,
               r.description as description,
               r.connection_uuid as connection_uuid
        """

        results = self.execute_query(query, {'connection_types': connection_types})
        connections = []
        seen = set()  # Avoid duplicate event connections

        for record in results:
            from_beat = record.get('from_beat')
            to_beat = record.get('to_beat')

            # Map beats to events
            from_event = beat_to_event.get(from_beat)
            to_event = beat_to_event.get(to_beat)

            if from_event and to_event:
                # Create unique key to avoid duplicates
                conn_key = (from_event, to_event, record.get('connection_type'))
                if conn_key in seen:
                    continue
                seen.add(conn_key)

                connection = {
                    'fabula_uuid': record.get('connection_uuid', ''),
                    'from_event_uuid': from_event,
                    'to_event_uuid': to_event,
                    'connection_type': record.get('connection_type', 'CAUSAL'),
                    'strength': record.get('strength', 'medium'),
                    'description': record.get('description', '')
                }

                connections.append(connection)
                self.stats['connection_count'] += 1

        return connections

    # =========================================================================
    # Export Manifest
    # =========================================================================

    def create_manifest(self, all_series: List[Dict]) -> Dict:
        """
        Create export manifest with metadata.

        Args:
            all_series: List of series data dictionaries

        Returns:
            Manifest dictionary
        """
        series_titles = [s.get('title', 'Unknown') for s in all_series]
        manifest = {
            'fabula_version': '2.0.0',
            'export_date': datetime.now().isoformat(),
            'source_graph': self.uri,
            'series_titles': series_titles,
            'series_count': self.stats['series_count'],
            'season_count': self.stats['season_count'],
            'episode_count': self.stats['episode_count'],
            'event_count': self.stats['event_count'],
            'character_count': self.stats['character_count'],
            'location_count': self.stats['location_count'],
            'organization_count': self.stats['organization_count'],
            'theme_count': self.stats['theme_count'],
            'arc_count': self.stats['arc_count'],
            'connection_count': self.stats['connection_count'],
            'notes': 'Export generated by Django management command export_from_neo4j'
        }

        return manifest

    # =========================================================================
    # File Writing
    # =========================================================================

    def write_yaml(self, filepath: Path, data: Any, header_comment: str = None):
        """
        Write data to YAML file with optional header comment.

        Args:
            filepath: Path to write file
            data: Data to serialize
            header_comment: Optional header comment
        """
        filepath.parent.mkdir(parents=True, exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            if header_comment:
                f.write(f"# {header_comment}\n")
                f.write(f"# Generated: {datetime.now().isoformat()}\n\n")

            yaml.dump(data, f, allow_unicode=True, sort_keys=False)

        print(f"  Wrote: {filepath}")

    # =========================================================================
    # Main Export Orchestration
    # =========================================================================

    def export_all(self):
        """
        Execute full export process.

        This method orchestrates the entire export:
        1. Export series/seasons/episodes
        2. Export all entity types
        3. Export events by episode
        4. Export narrative connections
        5. Create manifest
        """
        print("\n" + "=" * 70)
        print("Starting Neo4j to YAML export")
        print("=" * 70 + "\n")

        # Connect to Neo4j
        self.connect()

        try:
            # Export series hierarchy (returns list of all series)
            all_series = self.export_series()
            self.write_yaml(
                self.output_dir / 'series.yaml',
                all_series,
                'Series, Seasons, and Episodes'
            )

            # Export characters
            characters = self.export_characters()
            self.write_yaml(
                self.output_dir / 'characters.yaml',
                characters,
                'Character/Agent Data'
            )

            # Export locations
            locations = self.export_locations()
            self.write_yaml(
                self.output_dir / 'locations.yaml',
                locations,
                'Location Data'
            )

            # Export organizations
            organizations = self.export_organizations()
            self.write_yaml(
                self.output_dir / 'organizations.yaml',
                organizations,
                'Organization Data'
            )

            # Export themes
            themes = self.export_themes()
            self.write_yaml(
                self.output_dir / 'themes.yaml',
                themes,
                'Theme Data'
            )

            # Export conflict arcs
            arcs = self.export_arcs()
            self.write_yaml(
                self.output_dir / 'arcs.yaml',
                arcs,
                'Conflict Arc Data'
            )

            # Export events by episode for all series
            events_dir = self.output_dir / 'events'
            events_dir.mkdir(exist_ok=True)

            for series_data in all_series:
                series_title = series_data.get('title', 'Unknown')
                for season in series_data.get('seasons', []):
                    for episode in season.get('episodes', []):
                        episode_uuid = episode['fabula_uuid']
                        season_num = season['season_number']
                        episode_num = episode['episode_number']

                        # Use series-specific prefix to avoid collisions
                        series_prefix = series_data['fabula_uuid'].replace('ser_', '')[:10]
                        filename = f"{series_prefix}_s{season_num:02d}e{episode_num:02d}.yaml"

                        print(f"Exporting events for {series_title} - {episode['title']}...")
                        events = self.export_events_by_episode(episode_uuid)

                        self.write_yaml(
                            events_dir / filename,
                            {
                                'episode_uuid': episode_uuid,
                                'episode_title': episode['title'],
                                'series_title': series_title,
                                'events': events
                            },
                            f"Events for {episode['title']}"
                        )

            # Export narrative connections
            connections = self.export_connections()
            self.write_yaml(
                self.output_dir / 'connections.yaml',
                connections,
                'Narrative Connections Between Events'
            )

            # Create and write manifest
            manifest = self.create_manifest(all_series)
            self.write_yaml(
                self.output_dir / 'manifest.yaml',
                manifest,
                'Export Manifest'
            )

            # Print summary
            print("\n" + "=" * 70)
            print("Export complete!")
            print("=" * 70)
            print(f"\nOutput directory: {self.output_dir.absolute()}")
            print("\nStatistics:")
            print(f"  Series: {self.stats['series_count']}")
            print(f"  Seasons: {self.stats['season_count']}")
            print(f"  Episodes: {self.stats['episode_count']}")
            print(f"  Events: {self.stats['event_count']}")
            print(f"  Characters: {self.stats['character_count']}")
            print(f"  Locations: {self.stats['location_count']}")
            print(f"  Organizations: {self.stats['organization_count']}")
            print(f"  Themes: {self.stats['theme_count']}")
            print(f"  Conflict Arcs: {self.stats['arc_count']}")
            print(f"  Narrative Connections: {self.stats['connection_count']}")
            print()

        finally:
            self.close()


# =============================================================================
# Django Management Command
# =============================================================================

class Command(BaseCommand):
    """
    Django management command to export Neo4j data to YAML files.
    """

    help = 'Export narrative data from Neo4j to YAML files'

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            '--output',
            type=str,
            default='./fabula_export',
            help='Output directory for YAML files (default: ./fabula_export)'
        )
        parser.add_argument(
            '--uri',
            type=str,
            default=None,
            help='Neo4j URI (default: from settings or bolt://localhost:7689)'
        )
        parser.add_argument(
            '--user',
            type=str,
            default=None,
            help='Neo4j username (default: from settings or neo4j)'
        )
        parser.add_argument(
            '--password',
            type=str,
            default=None,
            help='Neo4j password (default: from settings or mythology)'
        )

    def handle(self, *args, **options):
        """Execute the export command."""

        # Setup YAML configuration
        setup_yaml()

        # Get connection details (from args, settings, or defaults)
        uri = options['uri'] or getattr(settings, 'NEO4J_URI', 'bolt://localhost:7689')
        user = options['user'] or getattr(settings, 'NEO4J_USER', 'neo4j')
        password = options['password'] or getattr(settings, 'NEO4J_PASSWORD', 'mythology')

        # Get output directory
        output_dir = Path(options['output']).absolute()

        # Display configuration
        self.stdout.write(self.style.SUCCESS('\nNeo4j Export Configuration:'))
        self.stdout.write(f"  URI: {uri}")
        self.stdout.write(f"  User: {user}")
        self.stdout.write(f"  Output: {output_dir}\n")

        # Confirm if output directory exists and is not empty
        if output_dir.exists():
            existing_files = list(output_dir.glob('*'))
            if existing_files:
                self.stdout.write(
                    self.style.WARNING(
                        f"\nWarning: Output directory {output_dir} already exists "
                        f"and contains {len(existing_files)} files."
                    )
                )
                response = input("Continue and overwrite? [y/N] ")
                if response.lower() not in ['y', 'yes']:
                    self.stdout.write(self.style.ERROR('Export cancelled.'))
                    return

        # Create exporter and run
        try:
            exporter = Neo4jExporter(uri, user, password, output_dir)
            exporter.export_all()

            self.stdout.write(
                self.style.SUCCESS(
                    f'\nSuccessfully exported data to {output_dir}'
                )
            )

        except Exception as e:
            raise CommandError(f'Export failed: {e}')
