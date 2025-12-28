"""
Fabula Neo4j → YAML Export Script

This script exports narrative graph data from Neo4j to the YAML
intermediary format for Wagtail import.

Usage:
    python export_to_yaml.py --output ./fabula_export --series "The West Wing"

The script:
1. Connects to Neo4j
2. Queries all relevant nodes and relationships
3. Writes organized YAML files
4. Generates a manifest with export metadata

This creates the curation layer between the live graph and the published site.
"""

import os
import argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
import yaml

# Neo4j driver - install with: pip install neo4j
from neo4j import GraphDatabase


# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_NEO4J_URI = "bolt://localhost:7687"
DEFAULT_NEO4J_USER = "neo4j"
DEFAULT_NEO4J_PASSWORD = "password"


# =============================================================================
# YAML SETUP
# =============================================================================

def str_representer(dumper, data):
    """Use literal block style for multi-line strings."""
    if '\n' in data:
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

yaml.add_representer(str, str_representer)


def write_yaml(data: Any, filepath: str):
    """Write data to YAML file with nice formatting."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    print(f"  ✓ Wrote {filepath}")


# =============================================================================
# NEO4J QUERIES
# =============================================================================

class FabulaExporter:
    """Exports Fabula graph data to YAML."""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.stats = {
            'episodes': 0,
            'events': 0,
            'characters': 0,
            'locations': 0,
            'themes': 0,
            'connections': 0,
        }
    
    def close(self):
        self.driver.close()
    
    def _run_query(self, query: str, params: dict = None) -> List[dict]:
        """Execute a Cypher query and return results as dicts."""
        with self.driver.session() as session:
            result = session.run(query, params or {})
            return [record.data() for record in result]
    
    # -------------------------------------------------------------------------
    # Export methods
    # -------------------------------------------------------------------------
    
    def export_series(self) -> dict:
        """Export series, seasons, and episodes."""
        query = """
        MATCH (series:Series)-[:BELONGS_TO_UNIVERSE]->(u:Universe)
        OPTIONAL MATCH (season:Season)-[:BELONGS_TO_SERIES]->(series)
        OPTIONAL MATCH (ep:Episode)-[:BELONGS_TO_SEASON]->(season)
        RETURN 
            series.series_uuid as series_uuid,
            series.title as series_title,
            u.name as universe_name,
            season.season_uuid as season_uuid,
            season.number as season_number,
            ep.episode_uuid as episode_uuid,
            ep.number as episode_number,
            ep.title as episode_title,
            ep.logline as logline,
            ep.high_level_summary as summary,
            ep.final_dominant_tone as tone
        ORDER BY season.number, ep.number
        """
        results = self._run_query(query)
        
        # Organize into hierarchy
        series_data = None
        seasons_map = {}
        
        for row in results:
            if series_data is None:
                series_data = {
                    'fabula_uuid': row['series_uuid'],
                    'title': row['series_title'],
                    'universe': row['universe_name'],
                    'description': f"Narrative analysis of {row['series_title']}",
                    'seasons': []
                }
            
            season_uuid = row['season_uuid']
            if season_uuid and season_uuid not in seasons_map:
                season = {
                    'fabula_uuid': season_uuid,
                    'season_number': row['season_number'],
                    'description': f"Season {row['season_number']}",
                    'episodes': []
                }
                seasons_map[season_uuid] = season
                series_data['seasons'].append(season)
            
            if row['episode_uuid']:
                episode = {
                    'fabula_uuid': row['episode_uuid'],
                    'episode_number': row['episode_number'],
                    'title': row['episode_title'] or f"Episode {row['episode_number']}",
                    'logline': row['logline'] or '',
                    'high_level_summary': row['summary'] or '',
                    'dominant_tone': row['tone'] or ''
                }
                if season_uuid:
                    seasons_map[season_uuid]['episodes'].append(episode)
                self.stats['episodes'] += 1
        
        return series_data
    
    def export_characters(self) -> List[dict]:
        """Export all canonical characters/agents."""
        query = """
        MATCH (a:Agent)
        WHERE a.status = 'canonical' AND a.canonical_name IS NOT NULL
        OPTIONAL MATCH (a)-[:AFFILIATED_WITH]->(org:Organization)
        RETURN 
            a.agent_uuid as fabula_uuid,
            a.canonical_name as canonical_name,
            a.title as title_role,
            a.foundational_description as description,
            a.foundational_traits as traits,
            a.aliases as aliases,
            a.character_type as character_type,
            a.sphere_of_influence as sphere_of_influence,
            a.appearance_count as appearance_count,
            org.org_uuid as affiliated_organization_uuid
        ORDER BY a.appearance_count DESC
        """
        results = self._run_query(query)
        
        characters = []
        for row in results:
            char = {
                'fabula_uuid': row['fabula_uuid'],
                'canonical_name': row['canonical_name'],
                'title_role': row['title_role'] or '',
                'description': row['description'] or '',
                'traits': row['traits'] or [],
                'aliases': row['aliases'] or [],
                'character_type': row['character_type'] or 'recurring',
                'sphere_of_influence': row['sphere_of_influence'] or '',
                'appearance_count': row['appearance_count'] or 0,
                'affiliated_organization_uuid': row['affiliated_organization_uuid']
            }
            characters.append(char)
            self.stats['characters'] += 1
        
        return characters
    
    def export_locations(self) -> List[dict]:
        """Export all canonical locations."""
        query = """
        MATCH (l:Location)
        WHERE l.status = 'canonical' AND l.canonical_name IS NOT NULL
        RETURN 
            l.location_uuid as fabula_uuid,
            l.canonical_name as canonical_name,
            l.foundational_description as description,
            l.foundational_type as location_type,
            l.part_of_location_uuid as parent_location_uuid
        ORDER BY l.canonical_name
        """
        results = self._run_query(query)
        
        locations = []
        for row in results:
            loc = {
                'fabula_uuid': row['fabula_uuid'],
                'canonical_name': row['canonical_name'],
                'description': row['description'] or '',
                'location_type': row['location_type'] or '',
                'parent_location_uuid': row['parent_location_uuid']
            }
            locations.append(loc)
            self.stats['locations'] += 1
        
        return locations
    
    def export_themes(self) -> List[dict]:
        """Export all themes."""
        query = """
        MATCH (t:Theme)
        RETURN 
            t.theme_uuid as fabula_uuid,
            t.name as name,
            t.description as description
        ORDER BY t.name
        """
        results = self._run_query(query)
        
        themes = []
        for row in results:
            theme = {
                'fabula_uuid': row['fabula_uuid'],
                'name': row['name'],
                'description': row['description'] or ''
            }
            themes.append(theme)
            self.stats['themes'] += 1
        
        return themes
    
    def export_arcs(self) -> List[dict]:
        """Export all conflict arcs."""
        query = """
        MATCH (arc:ConflictArc)
        RETURN 
            arc.arc_uuid as fabula_uuid,
            arc.conflict_description as description,
            arc.type as arc_type
        ORDER BY arc.type
        """
        results = self._run_query(query)
        
        arcs = []
        for row in results:
            # Generate title from description
            desc = row['description'] or ''
            title = desc[:50] + '...' if len(desc) > 50 else desc
            
            arc = {
                'fabula_uuid': row['fabula_uuid'],
                'title': title,
                'description': desc,
                'arc_type': row['arc_type'] or 'INTERPERSONAL'
            }
            arcs.append(arc)
        
        return arcs
    
    def export_events_for_episode(self, episode_uuid: str) -> List[dict]:
        """Export all events for a specific episode with participations."""
        # Get events
        event_query = """
        MATCH (e:Event)-[:PART_OF_EPISODE]->(ep:Episode {episode_uuid: $episode_uuid})
        OPTIONAL MATCH (e)-[:OCCURS_IN]->(scene:SceneBoundary)
        OPTIONAL MATCH (e)-[:EXEMPLIFIES_THEME]->(t:Theme)
        OPTIONAL MATCH (e)-[:PART_OF_ARC]->(arc:ConflictArc)
        OPTIONAL MATCH (l:Location)-[:IN_EVENT]->(e)
        WITH e, scene, 
             collect(DISTINCT t.theme_uuid) as theme_uuids,
             collect(DISTINCT arc.arc_uuid) as arc_uuids,
             collect(DISTINCT l.location_uuid)[0] as location_uuid
        RETURN 
            e.event_uuid as fabula_uuid,
            e.title as title,
            e.description as description,
            e.sequence_in_scene as sequence_in_scene,
            e.key_dialogue as key_dialogue,
            e.is_flashback as is_flashback,
            scene.scene_uuid as scene_uuid,
            theme_uuids,
            arc_uuids,
            location_uuid
        ORDER BY e.sequence_in_scene
        """
        event_results = self._run_query(event_query, {'episode_uuid': episode_uuid})
        
        events = []
        scene_sequence = 0
        last_scene = None
        
        for row in event_results:
            # Track scene sequence
            if row['scene_uuid'] != last_scene:
                scene_sequence += 1
                last_scene = row['scene_uuid']
            
            # Get participations for this event
            participation_query = """
            MATCH (a:Agent)-[p:PARTICIPATED_AS]->(e:Event {event_uuid: $event_uuid})
            WHERE a.status = 'canonical'
            RETURN 
                a.agent_uuid as character_uuid,
                p.emotional_state_at_event as emotional_state,
                p.goals_at_event as goals,
                p.observed_status as what_happened,
                p.beliefs_at_event as beliefs,
                p.observed_traits_at_event as observed_traits,
                p.importance_to_event as importance
            """
            participation_results = self._run_query(
                participation_query, 
                {'event_uuid': row['fabula_uuid']}
            )
            
            participations = []
            for p_row in participation_results:
                participation = {
                    'character_uuid': p_row['character_uuid'],
                    'emotional_state': p_row['emotional_state'] or '',
                    'goals': p_row['goals'] or [],
                    'what_happened': p_row['what_happened'] or '',
                    'observed_status': p_row['what_happened'] or '',
                    'beliefs': p_row['beliefs'] or [],
                    'observed_traits': p_row['observed_traits'] or [],
                    'importance': p_row['importance'] or 'primary'
                }
                participations.append(participation)
            
            event = {
                'fabula_uuid': row['fabula_uuid'],
                'title': row['title'] or 'Untitled Event',
                'description': row['description'] or '',
                'episode_uuid': episode_uuid,
                'scene_sequence': scene_sequence,
                'sequence_in_scene': row['sequence_in_scene'] or 0,
                'key_dialogue': row['key_dialogue'] or [],
                'is_flashback': row['is_flashback'] or False,
                'location_uuid': row['location_uuid'],
                'theme_uuids': row['theme_uuids'] or [],
                'arc_uuids': row['arc_uuids'] or [],
                'participations': participations
            }
            events.append(event)
            self.stats['events'] += 1
        
        return events
    
    def export_connections(self) -> List[dict]:
        """Export all narrative connections between events."""
        query = """
        MATCH (pb1:PlotBeat)-[r]->(pb2:PlotBeat)
        WHERE type(r) IN ['CAUSAL', 'FORESHADOWING', 'THEMATIC_PARALLEL', 
                          'CHARACTER_CONTINUITY', 'ESCALATION', 'CALLBACK',
                          'EMOTIONAL_ECHO', 'SYMBOLIC_PARALLEL', 'TEMPORAL']
        
        // Get the events these beats belong to
        MATCH (e1:Event)
        WHERE pb1.beat_uuid IN e1.derived_from_beat_uuids
        MATCH (e2:Event)  
        WHERE pb2.beat_uuid IN e2.derived_from_beat_uuids
        
        RETURN DISTINCT
            r.connection_uuid as fabula_uuid,
            e1.event_uuid as from_event_uuid,
            e2.event_uuid as to_event_uuid,
            type(r) as connection_type,
            r.strength as strength,
            r.description as description
        """
        results = self._run_query(query)
        
        connections = []
        seen = set()  # Deduplicate
        
        for row in results:
            key = (row['from_event_uuid'], row['to_event_uuid'], row['connection_type'])
            if key in seen:
                continue
            seen.add(key)
            
            conn = {
                'fabula_uuid': row['fabula_uuid'] or f"conn_{len(connections)}",
                'from_event_uuid': row['from_event_uuid'],
                'to_event_uuid': row['to_event_uuid'],
                'connection_type': row['connection_type'],
                'strength': row['strength'] or 'medium',
                'description': row['description'] or ''
            }
            connections.append(conn)
            self.stats['connections'] += 1
        
        return connections


# =============================================================================
# MAIN EXPORT FUNCTION
# =============================================================================

def export_fabula_to_yaml(
    output_dir: str,
    neo4j_uri: str = DEFAULT_NEO4J_URI,
    neo4j_user: str = DEFAULT_NEO4J_USER,
    neo4j_password: str = DEFAULT_NEO4J_PASSWORD
):
    """
    Export entire Fabula graph to YAML files.
    """
    print(f"\n🚀 Fabula → YAML Export")
    print(f"   Output: {output_dir}")
    print(f"   Neo4j:  {neo4j_uri}")
    print()
    
    exporter = FabulaExporter(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        # Export series structure
        print("📺 Exporting series structure...")
        series_data = exporter.export_series()
        write_yaml(series_data, os.path.join(output_dir, 'series.yaml'))
        
        # Export characters
        print("👥 Exporting characters...")
        characters = exporter.export_characters()
        write_yaml({'characters': characters}, os.path.join(output_dir, 'characters.yaml'))
        
        # Export locations
        print("📍 Exporting locations...")
        locations = exporter.export_locations()
        write_yaml({'locations': locations}, os.path.join(output_dir, 'locations.yaml'))
        
        # Export themes
        print("💡 Exporting themes...")
        themes = exporter.export_themes()
        write_yaml({'themes': themes}, os.path.join(output_dir, 'themes.yaml'))
        
        # Export arcs
        print("📈 Exporting conflict arcs...")
        arcs = exporter.export_arcs()
        write_yaml({'arcs': arcs}, os.path.join(output_dir, 'arcs.yaml'))
        
        # Export events per episode
        print("⚡ Exporting events by episode...")
        events_dir = os.path.join(output_dir, 'events')
        os.makedirs(events_dir, exist_ok=True)
        
        for season in series_data.get('seasons', []):
            for episode in season.get('episodes', []):
                ep_num = episode['episode_number']
                season_num = season['season_number']
                filename = f"s{season_num:02d}e{ep_num:02d}.yaml"
                
                events = exporter.export_events_for_episode(episode['fabula_uuid'])
                write_yaml({
                    'episode_uuid': episode['fabula_uuid'],
                    'episode_title': episode['title'],
                    'events': events
                }, os.path.join(events_dir, filename))
        
        # Export connections
        print("🔗 Exporting narrative connections...")
        connections = exporter.export_connections()
        write_yaml({'connections': connections}, os.path.join(output_dir, 'connections.yaml'))
        
        # Write manifest
        print("📋 Writing manifest...")
        manifest = {
            'fabula_version': '2.0.0',
            'export_date': datetime.utcnow().isoformat() + 'Z',
            'source_graph': neo4j_uri,
            'series_title': series_data['title'] if series_data else 'Unknown',
            'season_count': len(series_data.get('seasons', [])) if series_data else 0,
            'episode_count': exporter.stats['episodes'],
            'event_count': exporter.stats['events'],
            'character_count': exporter.stats['characters'],
            'connection_count': exporter.stats['connections'],
        }
        write_yaml(manifest, os.path.join(output_dir, 'manifest.yaml'))
        
        print()
        print("✅ Export complete!")
        print(f"   Episodes:    {exporter.stats['episodes']}")
        print(f"   Events:      {exporter.stats['events']}")
        print(f"   Characters:  {exporter.stats['characters']}")
        print(f"   Locations:   {exporter.stats['locations']}")
        print(f"   Themes:      {exporter.stats['themes']}")
        print(f"   Connections: {exporter.stats['connections']}")
        
    finally:
        exporter.close()


# =============================================================================
# CLI
# =============================================================================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Export Fabula narrative graph to YAML'
    )
    parser.add_argument(
        '--output', '-o',
        default='./fabula_export',
        help='Output directory for YAML files'
    )
    parser.add_argument(
        '--neo4j-uri',
        default=DEFAULT_NEO4J_URI,
        help='Neo4j connection URI'
    )
    parser.add_argument(
        '--neo4j-user',
        default=DEFAULT_NEO4J_USER,
        help='Neo4j username'
    )
    parser.add_argument(
        '--neo4j-password',
        default=DEFAULT_NEO4J_PASSWORD,
        help='Neo4j password'
    )
    
    args = parser.parse_args()
    
    export_fabula_to_yaml(
        output_dir=args.output,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password
    )
