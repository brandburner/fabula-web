"""
Fabula YAML Schema Reference

This document defines the YAML intermediary format for transferring
narrative graph data from Neo4j/Fabula to Wagtail.

Design Principles:
1. Human-readable and editable (curation layer)
2. Version-controllable (git-friendly diffs)
3. Complete (preserves all relationship/edge data)
4. Idempotent (re-importing produces same result)

File Organization:
  fabula_export/
  ├── manifest.yaml          # Export metadata and version
  ├── series.yaml            # Series, seasons, episodes
  ├── characters.yaml        # All characters/agents
  ├── locations.yaml         # All locations
  ├── organizations.yaml     # All organizations
  ├── themes.yaml            # All themes
  ├── arcs.yaml              # All conflict arcs
  ├── events/
  │   ├── s01e01.yaml        # Events for S1E1
  │   ├── s01e02.yaml        # Events for S1E2
  │   └── ...
  └── connections.yaml       # All narrative connections

UUID Strategy:
- All entities retain their Fabula UUIDs as `fabula_uuid`
- Wagtail generates its own PKs; fabula_uuid enables re-import
- Cross-references use fabula_uuid (resolved during import)
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import yaml


# =============================================================================
# ENUMS (matching Wagtail models)
# =============================================================================

class ConnectionType(str, Enum):
    CAUSAL = "CAUSAL"
    FORESHADOWING = "FORESHADOWING"
    THEMATIC_PARALLEL = "THEMATIC_PARALLEL"
    CHARACTER_CONTINUITY = "CHARACTER_CONTINUITY"
    ESCALATION = "ESCALATION"
    CALLBACK = "CALLBACK"
    EMOTIONAL_ECHO = "EMOTIONAL_ECHO"
    SYMBOLIC_PARALLEL = "SYMBOLIC_PARALLEL"
    TEMPORAL = "TEMPORAL"


class ConnectionStrength(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"


class CharacterType(str, Enum):
    MAIN = "main"
    RECURRING = "recurring"
    GUEST = "guest"
    MENTIONED = "mentioned"


class ArcType(str, Enum):
    INTERNAL = "INTERNAL"
    INTERPERSONAL = "INTERPERSONAL"
    SOCIETAL = "SOCIETAL"
    ENVIRONMENTAL = "ENVIRONMENTAL"
    TECHNOLOGICAL = "TECHNOLOGICAL"


# =============================================================================
# SCHEMA DATACLASSES
# =============================================================================

@dataclass
class ExportManifest:
    """Metadata about the export."""
    fabula_version: str
    export_date: str
    source_graph: str  # e.g., "neo4j://localhost:7687/westwing"
    series_title: str
    season_count: int
    episode_count: int
    event_count: int
    character_count: int
    connection_count: int
    
    # Optional: git commit of fabula that produced this
    fabula_commit: Optional[str] = None
    
    # Optional: notes about this export
    notes: Optional[str] = None


@dataclass
class SeriesData:
    """Series-level data."""
    fabula_uuid: str
    title: str
    description: str
    seasons: List['SeasonData']


@dataclass
class SeasonData:
    """Season within a series."""
    fabula_uuid: str
    season_number: int
    description: str
    episodes: List['EpisodeData']


@dataclass
class EpisodeData:
    """Episode within a season."""
    fabula_uuid: str
    episode_number: int
    title: str
    logline: str
    high_level_summary: str
    dominant_tone: str


@dataclass
class CharacterData:
    """Character/Agent data."""
    fabula_uuid: str
    canonical_name: str
    title_role: Optional[str]
    description: str
    traits: List[str]
    aliases: List[str]
    character_type: CharacterType
    sphere_of_influence: Optional[str]
    appearance_count: int
    
    # Reference to organization by fabula_uuid
    affiliated_organization_uuid: Optional[str] = None


@dataclass
class LocationData:
    """Location data."""
    fabula_uuid: str
    canonical_name: str
    description: str
    location_type: str
    
    # Reference to parent location by fabula_uuid
    parent_location_uuid: Optional[str] = None


@dataclass
class OrganizationData:
    """Organization data."""
    fabula_uuid: str
    canonical_name: str
    description: str
    sphere_of_influence: str


@dataclass
class ThemeData:
    """Theme data."""
    fabula_uuid: str
    name: str
    description: str


@dataclass
class ConflictArcData:
    """Conflict arc data."""
    fabula_uuid: str
    title: str
    description: str
    arc_type: ArcType


@dataclass
class ParticipationData:
    """
    Character participation in an event.
    This is the PARTICIPATED_AS edge data.
    """
    # Reference to character by fabula_uuid
    character_uuid: str
    
    # The rich edge data
    emotional_state: str
    goals: List[str]
    what_happened: str
    observed_status: str
    beliefs: List[str] = field(default_factory=list)
    observed_traits: List[str] = field(default_factory=list)
    importance: str = "primary"


@dataclass
class EventData:
    """
    Event data including participations.
    """
    fabula_uuid: str
    title: str
    description: str
    
    # Episode context (reference by fabula_uuid)
    episode_uuid: str
    scene_sequence: int
    sequence_in_scene: int
    
    # Content
    key_dialogue: List[str] = field(default_factory=list)
    is_flashback: bool = False
    
    # Location reference by fabula_uuid
    location_uuid: Optional[str] = None
    
    # Theme/Arc references by fabula_uuid
    theme_uuids: List[str] = field(default_factory=list)
    arc_uuids: List[str] = field(default_factory=list)
    
    # Embedded participations (the edge data)
    participations: List[ParticipationData] = field(default_factory=list)


@dataclass
class NarrativeConnectionData:
    """
    Narrative connection between events.
    This is the PlotBeat relationship data (CAUSAL, FORESHADOWING, etc.)
    """
    fabula_uuid: str
    
    # References by fabula_uuid
    from_event_uuid: str
    to_event_uuid: str
    
    connection_type: ConnectionType
    strength: ConnectionStrength
    
    # THE KEY FIELD: the narrative assertion
    description: str


# =============================================================================
# YAML CUSTOM REPRESENTERS
# =============================================================================

def enum_representer(dumper, data):
    """Represent enums as their string values."""
    return dumper.represent_str(data.value)


def setup_yaml():
    """Configure YAML for clean output."""
    yaml.add_representer(ConnectionType, enum_representer)
    yaml.add_representer(ConnectionStrength, enum_representer)
    yaml.add_representer(CharacterType, enum_representer)
    yaml.add_representer(ArcType, enum_representer)
    
    # Use block style for better readability
    yaml.default_flow_style = False


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

EXAMPLE_MANIFEST = """
# Fabula Export Manifest
# Generated: 2024-01-15T10:30:00Z

fabula_version: "2.0.0"
export_date: "2024-01-15T10:30:00Z"
source_graph: "neo4j://localhost:7687/westwing"
series_title: "The West Wing"
season_count: 1
episode_count: 22
event_count: 956
character_count: 781
connection_count: 401
fabula_commit: "abc123def456"
notes: |
  Season 1 complete export.
  Includes all narrative connections.
  Ready for Wagtail import.
"""

EXAMPLE_CHARACTER = """
# Character: Joshua Lyman
fabula_uuid: "agent_josh_lyman_canonical"
canonical_name: "Joshua Lyman"
title_role: "Deputy Chief of Staff"
description: |
  Joshua Lyman serves as the White House Deputy Chief of Staff and the 
  administration's frontline political operator. He orchestrates tactical 
  responses to congressional pressure, manages high-stakes nominations and 
  confirmations, and converts crises into controlled political theater.
traits:
  - tactical
  - sarcastic
  - loyal
  - volatile
  - brilliant
aliases:
  - Josh
  - J. Lyman
  - Deputy Chief of Staff Lyman
character_type: main
sphere_of_influence: "Legislative affairs and political operations"
appearance_count: 443
affiliated_organization_uuid: "org_white_house"
"""

EXAMPLE_EVENT = """
# Event: Triumph on Stage, Crisis Backstage
fabula_uuid: "event_triumph_crisis_12345"
title: "Triumph on Stage, Crisis Backstage"
description: |
  President Bartlet delivers a rousing, mobilizing speech celebrating the 
  gun-control push while the ballroom erupts in applause. Offstage, Leo 
  learns—to his horror—that five crucial votes have defected. The celebration 
  instantly flips to crisis: Josh demands names and mobilizes the staff.

episode_uuid: "ep_s01e04_five_votes_down"
scene_sequence: 12
sequence_in_scene: 1
is_flashback: false

location_uuid: "location_ballroom_backstage"

theme_uuids:
  - "theme_ceremony_vs_crisis"
  - "theme_damage_control"
  
arc_uuids:
  - "arc_five_votes_crisis"
  - "arc_leo_marriage"

participations:
  - character_uuid: "agent_josh_lyman_canonical"
    emotional_state: |
      Tense, incandescently angry—performance of control masking 
      urgent fear that the bill could fail
    goals:
      - Identify which representatives flipped and why
      - Mobilize staff and outside contacts to reclaim votes
      - Project control and calm to the rest of the team
      - Assign immediate tactical tasks so the crisis has direction
    what_happened: |
      Josh rushes in from the ballroom, demands names with clipped anger, 
      instructs others to look calm, and immediately places calls to press 
      the issue—converting celebration energy into aggressive retrieval.
    observed_status: "Primary crisis responder, converting celebration to action"
    importance: primary
    
  - character_uuid: "agent_leo_mcgarry_canonical"
    emotional_state: |
      Controlled horror—outwardly procedural but internally alarmed 
      and racing to contain political fallout
    goals:
      - Verify the vote count and identify the defectors
      - Mobilize staff to repair the margin
      - Contain panic and convert confusion into an operational plan
    what_happened: |
      Leo watches the speech backstage, answers a ringing phone, receives 
      the whip's arithmetic, and reports aloud that 'we lost five votes.'
    observed_status: "Receiving devastating news, triggering crisis response"
    importance: primary
"""

EXAMPLE_CONNECTION = """
# Connection: Leo's news triggers Josh's confrontation
fabula_uuid: "conn_leo_news_josh_confronts"
from_event_uuid: "event_triumph_crisis_12345"
to_event_uuid: "event_josh_confronts_katzenmoyer"
connection_type: CAUSAL
strength: strong
description: |
  Leo's receipt of the devastating news about the lost votes directly 
  leads to Josh's aggressive confrontation with Katzenmoyer to reclaim 
  one of the votes.
"""


if __name__ == "__main__":
    # Print example YAML
    print("=" * 60)
    print("MANIFEST EXAMPLE:")
    print("=" * 60)
    print(EXAMPLE_MANIFEST)
    
    print("=" * 60)
    print("CHARACTER EXAMPLE:")
    print("=" * 60)
    print(EXAMPLE_CHARACTER)
    
    print("=" * 60)
    print("EVENT EXAMPLE:")
    print("=" * 60)
    print(EXAMPLE_EVENT)
    
    print("=" * 60)
    print("CONNECTION EXAMPLE:")
    print("=" * 60)
    print(EXAMPLE_CONNECTION)
