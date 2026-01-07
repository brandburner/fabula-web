"""
Global Entity Registry (GER) Client for fabula_wagtail.

This module provides a client for querying the GER database (fabulager) to support
cross-season entity resolution. The GER links season-specific entities (with their
own UUIDs) through a global identity layer.

Architecture:
    Season DB (westwing.s01, westwing.s02) -> fabulager DB -> GlobalEntityRef + SeasonMapping

Key concepts:
    - fabula_uuid: Season-specific UUID (e.g., agent_abc123 from S1)
    - global_id: GER-assigned cross-season identity (e.g., ger_agent_josh_lyman_001)
    - SeasonMapping: Links a global_id to its season-specific local_uuid

Usage:
    from narrative.ger_client import GERClient

    client = GERClient()
    client.connect()

    # Resolve local UUID to global identity
    global_info = client.resolve_local_to_global('agent_abc123')

    # Get all season appearances for an entity
    appearances = client.get_cross_season_appearances('ger_agent_josh_lyman_001')

    # Find all recurring characters (appear in 2+ seasons)
    recurring = client.get_recurring_entities('Agent', min_seasons=2)

    client.close()
"""

import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

from neo4j import GraphDatabase, Driver
from django.conf import settings


class EntityType(str, Enum):
    """Entity types supported by GER."""
    AGENT = 'Agent'
    LOCATION = 'Location'
    OBJECT = 'Object'
    ORGANIZATION = 'Organization'
    THEME = 'Theme'
    CONFLICT_ARC = 'ConflictArc'


@dataclass
class GlobalEntity:
    """Represents a GER GlobalEntityRef."""
    global_id: str
    entity_type: str
    canonical_name: str
    canonical_description: Optional[str] = None
    canonical_aliases: Optional[List[str]] = None
    verification_status: str = 'pending'
    seasons: Optional[List[int]] = None


@dataclass
class SeasonMapping:
    """Represents a GER SeasonMapping."""
    mapping_id: str
    season_number: int
    local_uuid: str
    local_name: str
    local_database: str
    confidence: float
    phase: str  # 'anchor', 'matched', or 'reconciled'


class GERClient:
    """
    Client for querying the Global Entity Registry from fabula_wagtail.

    This client connects to the fabulager Neo4j database and provides methods
    to resolve cross-season entity identities.
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        ger_database: str = 'fabulager'
    ):
        """
        Initialize the GER client.

        Args:
            uri: Neo4j connection URI. Defaults to NEO4J_URI from settings/env.
            user: Neo4j username. Defaults to NEO4J_USER from settings/env.
            password: Neo4j password. Defaults to NEO4J_PASSWORD from settings/env.
            ger_database: Name of the GER database. Defaults to 'fabulager'.
        """
        self.uri = uri or getattr(settings, 'NEO4J_URI', None) or os.environ.get('NEO4J_URI', 'bolt://localhost:7689')
        self.user = user or getattr(settings, 'NEO4J_USER', None) or os.environ.get('NEO4J_USER', 'neo4j')
        self.password = password or getattr(settings, 'NEO4J_PASSWORD', None) or os.environ.get('NEO4J_PASSWORD', '')
        self.ger_database = ger_database
        self.driver: Optional[Driver] = None

    def connect(self) -> bool:
        """
        Establish connection to Neo4j.

        Returns:
            True if connection successful.

        Raises:
            Exception if connection fails.
        """
        try:
            self.driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password)
            )
            self.driver.verify_connectivity()
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Neo4j GER database: {e}")

    def close(self):
        """Close the Neo4j connection."""
        if self.driver:
            self.driver.close()
            self.driver = None

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def _execute_query(self, query: str, parameters: Optional[Dict] = None) -> List[Dict]:
        """
        Execute a Cypher query against the GER database.

        Args:
            query: Cypher query string
            parameters: Optional query parameters

        Returns:
            List of result records as dictionaries
        """
        if not self.driver:
            raise RuntimeError("Not connected. Call connect() first.")

        with self.driver.session(database=self.ger_database) as session:
            result = session.run(query, parameters or {})
            return [dict(record) for record in result]

    def is_available(self) -> bool:
        """
        Check if the GER database is available.

        Returns:
            True if GER database exists and is accessible.
        """
        try:
            if not self.driver:
                self.connect()
            # Try a simple query
            self._execute_query("RETURN 1 AS test")
            return True
        except Exception:
            return False

    # =========================================================================
    # Core Resolution Methods
    # =========================================================================

    def resolve_local_to_global(self, local_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get global identity for a local entity UUID.

        Given a season-specific fabula_uuid, returns the GER global identity
        if the entity has been registered in GER.

        Args:
            local_uuid: Season-specific UUID (e.g., 'agent_abc123')

        Returns:
            Dictionary with global_id, canonical_name, entity_type, etc.
            None if no GER entry exists for this UUID.
        """
        query = """
        MATCH (g:GlobalEntityRef)-[:HAS_SEASON_MAPPING]->(m:SeasonMapping {local_uuid: $local_uuid})
        RETURN g.global_id AS global_id,
               g.canonical_name AS canonical_name,
               g.entity_type AS entity_type,
               g.canonical_description AS description,
               g.canonical_aliases AS aliases,
               g.verification_status AS status
        LIMIT 1
        """
        results = self._execute_query(query, {'local_uuid': local_uuid})
        return results[0] if results else None

    def resolve_global_to_local(
        self,
        global_id: str,
        season_number: Optional[int] = None,
        database: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get season-specific mappings for a global entity.

        Args:
            global_id: GER global identity (e.g., 'ger_agent_josh_lyman_001')
            season_number: Optional filter by season
            database: Optional filter by database name

        Returns:
            List of season mappings with local_uuid, database, confidence, etc.
        """
        query = """
        MATCH (g:GlobalEntityRef {global_id: $global_id})
              -[:HAS_SEASON_MAPPING]->(m:SeasonMapping)
        WHERE ($season_number IS NULL OR m.season_number = $season_number)
          AND ($database IS NULL OR m.local_database = $database)
        RETURN m.season_number AS season,
               m.local_uuid AS local_uuid,
               m.local_name AS local_name,
               m.local_database AS database,
               m.confidence AS confidence,
               m.phase AS phase
        ORDER BY m.season_number
        """
        return self._execute_query(query, {
            'global_id': global_id,
            'season_number': season_number,
            'database': database
        })

    def get_cross_season_appearances(self, global_id: str) -> List[Dict[str, Any]]:
        """
        Get all season appearances for an entity.

        Args:
            global_id: GER global identity

        Returns:
            List of season mappings showing where this entity appears
        """
        return self.resolve_global_to_local(global_id)

    # =========================================================================
    # Bulk Query Methods
    # =========================================================================

    def get_recurring_entities(
        self,
        entity_type: str,
        min_seasons: int = 2,
        series_uuid: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get entities appearing in multiple seasons.

        Args:
            entity_type: Entity type (Agent, Location, etc.)
            min_seasons: Minimum number of seasons to qualify
            series_uuid: Optional series filter
            limit: Maximum results to return

        Returns:
            List of entities with their global_id, name, aliases, and seasons
        """
        query = """
        MATCH (g:GlobalEntityRef {entity_type: $entity_type})
              -[:HAS_SEASON_MAPPING]->(m:SeasonMapping)
        WHERE ($series_uuid IS NULL OR m.series_uuid = $series_uuid)
        WITH g, collect(DISTINCT m.season_number) AS seasons
        WHERE size(seasons) >= $min_seasons
        RETURN g.global_id AS global_id,
               g.canonical_name AS canonical_name,
               g.canonical_aliases AS aliases,
               g.canonical_description AS description,
               seasons,
               size(seasons) AS season_count
        ORDER BY size(seasons) DESC, g.canonical_name
        LIMIT $limit
        """
        return self._execute_query(query, {
            'entity_type': entity_type,
            'min_seasons': min_seasons,
            'series_uuid': series_uuid,
            'limit': limit
        })

    def get_all_global_ids_for_database(
        self,
        database: str,
        entity_type: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get mapping of local_uuid -> global_id for all entities in a database.

        This is useful during export to efficiently look up global IDs.

        Args:
            database: Season database name (e.g., 'westwing.s01')
            entity_type: Optional filter by entity type

        Returns:
            Dictionary mapping local_uuid to global_id
        """
        query = """
        MATCH (g:GlobalEntityRef)-[:HAS_SEASON_MAPPING]->(m:SeasonMapping)
        WHERE m.local_database = $database
          AND ($entity_type IS NULL OR g.entity_type = $entity_type)
        RETURN m.local_uuid AS local_uuid, g.global_id AS global_id
        """
        results = self._execute_query(query, {
            'database': database,
            'entity_type': entity_type
        })
        return {r['local_uuid']: r['global_id'] for r in results}

    def bulk_resolve_local_uuids(
        self,
        local_uuids: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Bulk resolve multiple local UUIDs to their global identities.

        Args:
            local_uuids: List of season-specific UUIDs

        Returns:
            Dictionary mapping local_uuid to global entity info
        """
        if not local_uuids:
            return {}

        query = """
        UNWIND $local_uuids AS uuid
        OPTIONAL MATCH (g:GlobalEntityRef)-[:HAS_SEASON_MAPPING]->(m:SeasonMapping {local_uuid: uuid})
        RETURN uuid AS local_uuid,
               g.global_id AS global_id,
               g.canonical_name AS canonical_name,
               g.entity_type AS entity_type
        """
        results = self._execute_query(query, {'local_uuids': local_uuids})
        return {
            r['local_uuid']: {
                'global_id': r['global_id'],
                'canonical_name': r['canonical_name'],
                'entity_type': r['entity_type']
            }
            for r in results if r['global_id']
        }

    # =========================================================================
    # Statistics and Discovery
    # =========================================================================

    def get_statistics(self, series_uuid: Optional[str] = None) -> Dict[str, Any]:
        """
        Get GER statistics.

        Args:
            series_uuid: Optional series filter

        Returns:
            Dictionary with entity counts by type, status, and season coverage
        """
        # Base count query
        count_query = """
        MATCH (g:GlobalEntityRef)
        OPTIONAL MATCH (g)-[:HAS_SEASON_MAPPING]->(m:SeasonMapping)
        WHERE $series_uuid IS NULL OR m.series_uuid = $series_uuid
        WITH g, collect(DISTINCT m.season_number) AS seasons
        WHERE size(seasons) > 0 OR $series_uuid IS NULL
        RETURN g.entity_type AS entity_type,
               g.verification_status AS status,
               count(*) AS count,
               sum(CASE WHEN size(seasons) >= 2 THEN 1 ELSE 0 END) AS cross_season_count
        """
        results = self._execute_query(count_query, {'series_uuid': series_uuid})

        # Aggregate results
        stats = {
            'total_entities': 0,
            'cross_season_entities': 0,
            'by_type': {},
            'by_status': {}
        }

        for r in results:
            entity_type = r['entity_type']
            status = r['status']
            count = r['count']
            cross_season = r['cross_season_count']

            stats['total_entities'] += count
            stats['cross_season_entities'] += cross_season

            stats['by_type'][entity_type] = stats['by_type'].get(entity_type, 0) + count
            stats['by_status'][status] = stats['by_status'].get(status, 0) + count

        return stats

    def get_entity_profile(self, global_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete profile for a GER entity including all season mappings.

        Args:
            global_id: GER global identity

        Returns:
            Complete entity profile with all metadata and season appearances
        """
        query = """
        MATCH (g:GlobalEntityRef {global_id: $global_id})
        OPTIONAL MATCH (g)-[:HAS_SEASON_MAPPING]->(m:SeasonMapping)
        WITH g, collect({
          season: m.season_number,
          local_uuid: m.local_uuid,
          local_name: m.local_name,
          database: m.local_database,
          confidence: m.confidence,
          phase: m.phase
        }) AS mappings
        RETURN g.global_id AS global_id,
               g.entity_type AS entity_type,
               g.canonical_name AS canonical_name,
               g.canonical_description AS description,
               g.canonical_aliases AS aliases,
               g.verification_status AS status,
               [m IN mappings | m.season] AS seasons,
               size(mappings) AS mapping_count,
               mappings
        """
        results = self._execute_query(query, {'global_id': global_id})
        return results[0] if results else None

    def find_entity_by_name(
        self,
        name: str,
        entity_type: Optional[str] = None,
        fuzzy: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Find GER entities by name.

        Args:
            name: Name to search for
            entity_type: Optional entity type filter
            fuzzy: If True, use contains match; otherwise exact match

        Returns:
            List of matching entities
        """
        if fuzzy:
            query = """
            MATCH (g:GlobalEntityRef)
            WHERE toLower(g.canonical_name) CONTAINS toLower($name)
              AND ($entity_type IS NULL OR g.entity_type = $entity_type)
            RETURN g.global_id AS global_id,
                   g.canonical_name AS canonical_name,
                   g.entity_type AS entity_type,
                   g.canonical_aliases AS aliases
            ORDER BY g.canonical_name
            LIMIT 20
            """
        else:
            query = """
            MATCH (g:GlobalEntityRef)
            WHERE toLower(g.canonical_name) = toLower($name)
              AND ($entity_type IS NULL OR g.entity_type = $entity_type)
            RETURN g.global_id AS global_id,
                   g.canonical_name AS canonical_name,
                   g.entity_type AS entity_type,
                   g.canonical_aliases AS aliases
            """
        return self._execute_query(query, {
            'name': name,
            'entity_type': entity_type
        })


# =============================================================================
# Convenience Functions
# =============================================================================

def get_ger_client() -> GERClient:
    """
    Get a GER client instance using Django settings.

    Returns:
        Connected GERClient instance

    Usage:
        with get_ger_client() as client:
            global_id = client.resolve_local_to_global(uuid)
    """
    client = GERClient()
    return client


def resolve_entity_global_id(local_uuid: str) -> Optional[str]:
    """
    Quick helper to resolve a local UUID to its global_id.

    Args:
        local_uuid: Season-specific entity UUID

    Returns:
        GER global_id or None if not found
    """
    try:
        with get_ger_client() as client:
            result = client.resolve_local_to_global(local_uuid)
            return result['global_id'] if result else None
    except Exception:
        return None


def get_cross_season_count(local_uuid: str) -> int:
    """
    Get the number of seasons an entity appears in.

    Args:
        local_uuid: Season-specific entity UUID

    Returns:
        Number of seasons (0 if entity not in GER)
    """
    try:
        with get_ger_client() as client:
            result = client.resolve_local_to_global(local_uuid)
            if not result:
                return 0
            appearances = client.get_cross_season_appearances(result['global_id'])
            return len(appearances)
    except Exception:
        return 0
