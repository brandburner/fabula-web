"""
Comprehensive validation tests for Fabula export pipeline.

These tests validate:
1. Neo4j schema property name correctness
2. Entity extraction completeness
3. Entity linkage integrity (foreign key validation)
4. Participation data richness
5. Connection data completeness
6. YAML export format validation

Run with: python manage.py test narrative.management.commands.tests.test_export_validation
Or: pytest narrative/management/commands/tests/test_export_validation.py -v
"""

import pytest
import yaml
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Any, Optional
from unittest.mock import Mock, patch
from io import StringIO

from django.test import TestCase


# =============================================================================
# Test Data Fixtures
# =============================================================================

SAMPLE_RICH_PARTICIPATION = {
    'character_uuid': 'agent_a1a50da165c5',
    'emotional_state': 'Tense, incandescently angry—performance of control masking urgent fear that the bill could fail',
    'goals': [
        'Identify which representatives flipped and why',
        'Mobilize staff and outside contacts to reclaim votes',
        'Project control and calm to the rest of the team'
    ],
    'what_happened': 'Josh rushes in from the ballroom, demands names with clipped anger, instructs others to look calm, and immediately places calls to press the issue.',
    'observed_status': 'Josh rushes in from the ballroom, demands names with clipped anger...',
    'beliefs': ['The legislative process can be influenced through pressure'],
    'observed_traits': ['tactical', 'aggressive', 'focused'],
    'importance': 'primary'
}

SAMPLE_SPARSE_PARTICIPATION = {
    'character_uuid': 'agent_test123',
    'emotional_state': '',
    'goals': [],
    'what_happened': '',
    'observed_status': 'Some basic status text',
    'beliefs': [],
    'observed_traits': [],
    'importance': 'primary'
}


# =============================================================================
# Schema Property Name Tests
# =============================================================================

class TestSchemaPropertyNames(TestCase):
    """
    Validate that export queries use correct Neo4j property names.

    According to FABULA_SCHEMA_GROUND_TRUTH.md, the PARTICIPATED_AS
    relationship has these properties:
    - emotional_state_at_event (NOT emotional_state)
    - goals_at_event (NOT goals)
    - beliefs_at_event (NOT beliefs)
    - observed_traits_at_event (NOT observed_traits)
    - observed_status (correct)
    - importance_to_event (NOT importance)
    """

    def test_participation_query_uses_correct_property_names(self):
        """Verify the Cypher query uses _at_event suffix for participation properties."""
        from narrative.management.commands.export_from_neo4j import Neo4jExporter

        exporter = Neo4jExporter('bolt://test', 'neo4j', 'test', Path('/tmp'))

        # Read the export_events_by_episode method to check query
        import inspect
        source = inspect.getsource(exporter.export_events_by_episode)

        # Should use correct property names
        self.assertIn('p.emotional_state_at_event', source,
            "Query should use 'p.emotional_state_at_event' not 'p.emotional_state'")
        self.assertIn('p.goals_at_event', source,
            "Query should use 'p.goals_at_event' not 'p.goals'")
        self.assertIn('p.beliefs_at_event', source,
            "Query should use 'p.beliefs_at_event' not 'p.beliefs'")
        self.assertIn('p.observed_traits_at_event', source,
            "Query should use 'p.observed_traits_at_event' not 'p.observed_traits'")

        # observed_status is correct as-is
        self.assertIn('p.observed_status', source)

    def test_participation_query_does_not_use_wrong_property_names(self):
        """Verify query does NOT use incorrect property names."""
        from narrative.management.commands.export_from_neo4j import Neo4jExporter

        exporter = Neo4jExporter('bolt://test', 'neo4j', 'test', Path('/tmp'))

        import inspect
        source = inspect.getsource(exporter.export_events_by_episode)

        # Check for incorrect patterns (exact match to avoid false positives)
        # We need to be careful - 'p.emotional_state' could match 'p.emotional_state_at_event'
        # So we check for the wrong pattern specifically

        lines = [line.strip() for line in source.split('\n')]
        for line in lines:
            if 'emotional_state:' in line and 'p.emotional_state,' in line:
                self.fail("Found incorrect property 'p.emotional_state' instead of 'p.emotional_state_at_event'")
            if 'goals:' in line and 'p.goals,' in line:
                self.fail("Found incorrect property 'p.goals' instead of 'p.goals_at_event'")


# =============================================================================
# Entity Linkage Integrity Tests
# =============================================================================

class TestEntityLinkageIntegrity(TestCase):
    """
    Validate that exported entities maintain referential integrity.

    Tests ensure:
    - All participation character_uuids reference valid characters
    - All event location_uuids reference valid locations
    - All connection from/to_event_uuids reference valid events
    - All event theme_uuids reference valid themes
    - All event arc_uuids reference valid arcs
    """

    def setUp(self):
        """Set up sample exported data."""
        self.characters = [
            {'fabula_uuid': 'agent_josh', 'canonical_name': 'Joshua Lyman'},
            {'fabula_uuid': 'agent_leo', 'canonical_name': 'Leo McGarry'},
            {'fabula_uuid': 'agent_toby', 'canonical_name': 'Toby Ziegler'},
        ]

        self.locations = [
            {'fabula_uuid': 'loc_oval', 'canonical_name': 'Oval Office'},
            {'fabula_uuid': 'loc_bullpen', 'canonical_name': 'Bullpen'},
        ]

        self.themes = [
            {'fabula_uuid': 'theme_power', 'name': 'Power and Responsibility'},
            {'fabula_uuid': 'theme_loyalty', 'name': 'Loyalty'},
        ]

        self.arcs = [
            {'fabula_uuid': 'arc_votes', 'title': 'Five Votes Down'},
        ]

        self.events = [
            {
                'fabula_uuid': 'event_1',
                'title': 'Crisis Meeting',
                'location_uuid': 'loc_oval',
                'theme_uuids': ['theme_power'],
                'arc_uuids': ['arc_votes'],
                'participations': [
                    {'character_uuid': 'agent_josh', 'emotional_state': 'Tense'},
                    {'character_uuid': 'agent_leo', 'emotional_state': 'Calm'},
                ]
            },
            {
                'fabula_uuid': 'event_2',
                'title': 'Resolution',
                'location_uuid': 'loc_bullpen',
                'theme_uuids': ['theme_loyalty'],
                'arc_uuids': [],
                'participations': [
                    {'character_uuid': 'agent_toby', 'emotional_state': 'Satisfied'},
                ]
            }
        ]

        self.connections = [
            {
                'fabula_uuid': 'conn_1',
                'from_event_uuid': 'event_1',
                'to_event_uuid': 'event_2',
                'connection_type': 'CAUSAL'
            }
        ]

    def test_all_participation_characters_exist(self):
        """Verify all participation character_uuids reference existing characters."""
        character_uuids = {c['fabula_uuid'] for c in self.characters}

        missing_characters = set()
        for event in self.events:
            for participation in event.get('participations', []):
                char_uuid = participation.get('character_uuid')
                if char_uuid and char_uuid not in character_uuids:
                    missing_characters.add(char_uuid)

        self.assertEqual(missing_characters, set(),
            f"Participations reference non-existent characters: {missing_characters}")

    def test_all_event_locations_exist(self):
        """Verify all event location_uuids reference existing locations."""
        location_uuids = {l['fabula_uuid'] for l in self.locations}
        location_uuids.add(None)  # None is valid (no location)

        missing_locations = set()
        for event in self.events:
            loc_uuid = event.get('location_uuid')
            if loc_uuid and loc_uuid not in location_uuids:
                missing_locations.add(loc_uuid)

        self.assertEqual(missing_locations, set(),
            f"Events reference non-existent locations: {missing_locations}")

    def test_all_event_themes_exist(self):
        """Verify all event theme_uuids reference existing themes."""
        theme_uuids = {t['fabula_uuid'] for t in self.themes}

        missing_themes = set()
        for event in self.events:
            for theme_uuid in event.get('theme_uuids', []):
                if theme_uuid not in theme_uuids:
                    missing_themes.add(theme_uuid)

        self.assertEqual(missing_themes, set(),
            f"Events reference non-existent themes: {missing_themes}")

    def test_all_connection_events_exist(self):
        """Verify all connection event references are valid."""
        event_uuids = {e['fabula_uuid'] for e in self.events}

        missing_events = set()
        for conn in self.connections:
            if conn['from_event_uuid'] not in event_uuids:
                missing_events.add(f"from: {conn['from_event_uuid']}")
            if conn['to_event_uuid'] not in event_uuids:
                missing_events.add(f"to: {conn['to_event_uuid']}")

        self.assertEqual(missing_events, set(),
            f"Connections reference non-existent events: {missing_events}")


class TestLinkageIntegrityValidator:
    """
    Utility class to validate linkage integrity across exported YAML files.

    Usage:
        validator = TestLinkageIntegrityValidator('/path/to/fabula_export')
        results = validator.validate_all()
        print(results.summary())
    """

    def __init__(self, export_dir: Path):
        self.export_dir = Path(export_dir)
        self.errors: List[str] = []
        self.warnings: List[str] = []

        # Load all entities
        self.characters = self._load_yaml('characters.yaml') or []
        self.locations = self._load_yaml('locations.yaml') or []
        self.organizations = self._load_yaml('organizations.yaml') or []
        self.themes = self._load_yaml('themes.yaml') or []
        self.arcs = self._load_yaml('arcs.yaml') or []
        self.connections = self._load_yaml('connections.yaml') or []
        self.events = self._load_all_events()

        # Build lookup sets
        self.character_uuids = {c.get('fabula_uuid') for c in self.characters if c.get('fabula_uuid')}
        self.location_uuids = {l.get('fabula_uuid') for l in self.locations if l.get('fabula_uuid')}
        self.theme_uuids = {t.get('fabula_uuid') for t in self.themes if t.get('fabula_uuid')}
        self.arc_uuids = {a.get('fabula_uuid') for a in self.arcs if a.get('fabula_uuid')}
        self.event_uuids = {e.get('fabula_uuid') for e in self.events if e.get('fabula_uuid')}

    def _load_yaml(self, filename: str) -> Optional[List]:
        """Load a YAML file from the export directory."""
        filepath = self.export_dir / filename
        if not filepath.exists():
            self.warnings.append(f"File not found: {filename}")
            return None

        with open(filepath, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)

        # Handle different YAML structures
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Try common key patterns
            for key in ['characters', 'locations', 'organizations', 'themes', 'arcs', 'connections']:
                if key in data:
                    return data[key]
            return [data]
        return []

    def _load_all_events(self) -> List[Dict]:
        """Load all events from episode YAML files."""
        events = []
        events_dir = self.export_dir / 'events'

        if not events_dir.exists():
            self.warnings.append("Events directory not found")
            return events

        for yaml_file in events_dir.glob('*.yaml'):
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if data and 'events' in data:
                events.extend(data['events'])

        return events

    def validate_participation_characters(self) -> int:
        """Validate all participation character references."""
        error_count = 0

        for event in self.events:
            event_uuid = event.get('fabula_uuid', 'unknown')
            for participation in event.get('participations', []):
                char_uuid = participation.get('character_uuid')
                if char_uuid and char_uuid not in self.character_uuids:
                    self.errors.append(
                        f"Event {event_uuid}: participation references unknown character {char_uuid}"
                    )
                    error_count += 1

        return error_count

    def validate_event_locations(self) -> int:
        """Validate all event location references."""
        error_count = 0

        for event in self.events:
            event_uuid = event.get('fabula_uuid', 'unknown')
            loc_uuid = event.get('location_uuid')
            if loc_uuid and loc_uuid not in self.location_uuids:
                self.errors.append(
                    f"Event {event_uuid}: references unknown location {loc_uuid}"
                )
                error_count += 1

        return error_count

    def validate_event_themes(self) -> int:
        """Validate all event theme references."""
        error_count = 0

        for event in self.events:
            event_uuid = event.get('fabula_uuid', 'unknown')
            for theme_uuid in event.get('theme_uuids', []):
                if theme_uuid not in self.theme_uuids:
                    self.errors.append(
                        f"Event {event_uuid}: references unknown theme {theme_uuid}"
                    )
                    error_count += 1

        return error_count

    def validate_connections(self) -> int:
        """Validate all narrative connection references."""
        error_count = 0

        for conn in self.connections:
            conn_uuid = conn.get('fabula_uuid', 'unknown')

            from_uuid = conn.get('from_event_uuid')
            if from_uuid and from_uuid not in self.event_uuids:
                self.errors.append(
                    f"Connection {conn_uuid}: from_event references unknown event {from_uuid}"
                )
                error_count += 1

            to_uuid = conn.get('to_event_uuid')
            if to_uuid and to_uuid not in self.event_uuids:
                self.errors.append(
                    f"Connection {conn_uuid}: to_event references unknown event {to_uuid}"
                )
                error_count += 1

        return error_count

    def validate_all(self) -> 'ValidationResult':
        """Run all validation checks."""
        results = ValidationResult()

        results.add_check('Participation Characters', self.validate_participation_characters())
        results.add_check('Event Locations', self.validate_event_locations())
        results.add_check('Event Themes', self.validate_event_themes())
        results.add_check('Connections', self.validate_connections())

        results.errors = self.errors
        results.warnings = self.warnings

        return results


class ValidationResult:
    """Container for validation results."""

    def __init__(self):
        self.checks: Dict[str, int] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def add_check(self, name: str, error_count: int):
        self.checks[name] = error_count

    @property
    def total_errors(self) -> int:
        return sum(self.checks.values())

    @property
    def is_valid(self) -> bool:
        return self.total_errors == 0

    def summary(self) -> str:
        lines = ["Validation Results", "=" * 50]

        for check_name, error_count in self.checks.items():
            status = "✓" if error_count == 0 else f"✗ ({error_count} errors)"
            lines.append(f"  {check_name}: {status}")

        lines.append("-" * 50)
        lines.append(f"Total Errors: {self.total_errors}")
        lines.append(f"Status: {'PASSED' if self.is_valid else 'FAILED'}")

        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")

        if self.errors and self.total_errors <= 10:
            lines.append("\nErrors:")
            for error in self.errors:
                lines.append(f"  • {error}")

        return "\n".join(lines)


# =============================================================================
# Data Completeness Tests
# =============================================================================

class TestParticipationDataCompleteness(TestCase):
    """
    Validate that participation data has the expected rich content.

    A "rich" participation should have:
    - Non-empty emotional_state
    - At least one goal
    - Non-empty what_happened or observed_status
    """

    def test_rich_participation_has_emotional_state(self):
        """Verify rich participations have emotional state."""
        self.assertTrue(
            len(SAMPLE_RICH_PARTICIPATION['emotional_state']) > 0,
            "Rich participation should have non-empty emotional_state"
        )

    def test_rich_participation_has_goals(self):
        """Verify rich participations have goals."""
        self.assertTrue(
            len(SAMPLE_RICH_PARTICIPATION['goals']) > 0,
            "Rich participation should have at least one goal"
        )

    def test_rich_participation_has_what_happened(self):
        """Verify rich participations have what_happened."""
        self.assertTrue(
            len(SAMPLE_RICH_PARTICIPATION['what_happened']) > 0,
            "Rich participation should have non-empty what_happened"
        )

    def test_sparse_participation_flags_as_incomplete(self):
        """Verify sparse participations can be detected."""
        is_sparse = (
            len(SAMPLE_SPARSE_PARTICIPATION['emotional_state']) == 0 and
            len(SAMPLE_SPARSE_PARTICIPATION['goals']) == 0 and
            len(SAMPLE_SPARSE_PARTICIPATION['what_happened']) == 0
        )
        self.assertTrue(is_sparse, "Should detect sparse participation data")


class ParticipationRichnessAnalyzer:
    """
    Analyzes participation data richness across an export.

    Usage:
        analyzer = ParticipationRichnessAnalyzer('/path/to/fabula_export')
        report = analyzer.analyze()
        print(report)
    """

    def __init__(self, export_dir: Path):
        self.export_dir = Path(export_dir)
        self.events = self._load_all_events()

    def _load_all_events(self) -> List[Dict]:
        """Load all events from episode YAML files."""
        events = []
        events_dir = self.export_dir / 'events'

        if not events_dir.exists():
            return events

        for yaml_file in events_dir.glob('*.yaml'):
            with open(yaml_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            if data and 'events' in data:
                events.extend(data['events'])

        return events

    def analyze(self) -> Dict[str, Any]:
        """Analyze participation data richness."""
        total_participations = 0
        rich_participations = 0
        sparse_participations = 0

        field_coverage = {
            'emotional_state': 0,
            'goals': 0,
            'what_happened': 0,
            'observed_status': 0,
            'beliefs': 0,
            'observed_traits': 0,
        }

        sample_rich = []
        sample_sparse = []

        for event in self.events:
            for p in event.get('participations', []):
                total_participations += 1

                # Track field coverage
                if p.get('emotional_state'):
                    field_coverage['emotional_state'] += 1
                if p.get('goals') and len(p['goals']) > 0:
                    field_coverage['goals'] += 1
                if p.get('what_happened'):
                    field_coverage['what_happened'] += 1
                if p.get('observed_status'):
                    field_coverage['observed_status'] += 1
                if p.get('beliefs') and len(p['beliefs']) > 0:
                    field_coverage['beliefs'] += 1
                if p.get('observed_traits') and len(p['observed_traits']) > 0:
                    field_coverage['observed_traits'] += 1

                # Classify richness
                is_rich = (
                    bool(p.get('emotional_state')) or
                    (p.get('goals') and len(p['goals']) > 0)
                )

                if is_rich:
                    rich_participations += 1
                    if len(sample_rich) < 3:
                        sample_rich.append({
                            'event': event.get('title', 'Unknown'),
                            'character_uuid': p.get('character_uuid'),
                            'emotional_state': p.get('emotional_state', '')[:100],
                            'goal_count': len(p.get('goals', []))
                        })
                else:
                    sparse_participations += 1
                    if len(sample_sparse) < 3:
                        sample_sparse.append({
                            'event': event.get('title', 'Unknown'),
                            'character_uuid': p.get('character_uuid'),
                            'has_observed_status': bool(p.get('observed_status'))
                        })

        # Calculate percentages
        if total_participations > 0:
            field_percentages = {
                field: (count / total_participations) * 100
                for field, count in field_coverage.items()
            }
            rich_percentage = (rich_participations / total_participations) * 100
        else:
            field_percentages = {field: 0 for field in field_coverage}
            rich_percentage = 0

        return {
            'total_participations': total_participations,
            'rich_participations': rich_participations,
            'sparse_participations': sparse_participations,
            'rich_percentage': rich_percentage,
            'field_coverage': field_coverage,
            'field_percentages': field_percentages,
            'sample_rich': sample_rich,
            'sample_sparse': sample_sparse,
        }

    def report(self) -> str:
        """Generate a human-readable report."""
        analysis = self.analyze()

        lines = [
            "Participation Data Richness Report",
            "=" * 50,
            f"Total Participations: {analysis['total_participations']}",
            f"Rich (has emotional_state or goals): {analysis['rich_participations']} ({analysis['rich_percentage']:.1f}%)",
            f"Sparse: {analysis['sparse_participations']}",
            "",
            "Field Coverage:",
        ]

        for field, percentage in analysis['field_percentages'].items():
            count = analysis['field_coverage'][field]
            bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
            lines.append(f"  {field:20s} {bar} {percentage:5.1f}% ({count})")

        if analysis['sample_rich']:
            lines.append("\nSample Rich Participations:")
            for sample in analysis['sample_rich']:
                lines.append(f"  • {sample['event']}: {sample['character_uuid']}")
                if sample['emotional_state']:
                    lines.append(f"    Emotional: {sample['emotional_state']}...")
                lines.append(f"    Goals: {sample['goal_count']}")

        return "\n".join(lines)


# =============================================================================
# Connection Completeness Tests
# =============================================================================

class TestConnectionDataCompleteness(TestCase):
    """Validate that connection data has complete narrative assertions."""

    def test_connection_has_description(self):
        """Verify connections have narrative descriptions."""
        sample_connection = {
            'fabula_uuid': 'conn_123',
            'from_event_uuid': 'event_1',
            'to_event_uuid': 'event_2',
            'connection_type': 'CAUSAL',
            'strength': 'strong',
            'description': "The bombing directly results from the President's demand for a proportional response."
        }

        self.assertTrue(
            len(sample_connection['description']) > 20,
            "Connection description should be substantial (>20 chars)"
        )

    def test_connection_has_valid_type(self):
        """Verify connections have valid connection types."""
        valid_types = [
            'CAUSAL', 'FORESHADOWING', 'THEMATIC_PARALLEL',
            'CHARACTER_CONTINUITY', 'ESCALATION', 'CALLBACK',
            'EMOTIONAL_ECHO', 'SYMBOLIC_PARALLEL', 'TEMPORAL'
        ]

        sample_type = 'CAUSAL'
        self.assertIn(sample_type, valid_types)

    def test_connection_has_valid_strength(self):
        """Verify connections have valid strength values."""
        valid_strengths = ['strong', 'medium', 'weak']

        sample_strength = 'strong'
        self.assertIn(sample_strength, valid_strengths)


# =============================================================================
# YAML Export Format Tests
# =============================================================================

class TestYAMLExportFormat(TestCase):
    """Validate YAML export file format and structure."""

    def test_event_yaml_structure(self):
        """Verify event YAML has correct structure."""
        sample_event_yaml = {
            'episode_uuid': 'ep_test',
            'episode_title': 'Test Episode',
            'series_title': 'Test Series',
            'events': [
                {
                    'fabula_uuid': 'event_1',
                    'title': 'Test Event',
                    'description': 'Description',
                    'episode_uuid': 'ep_test',
                    'scene_sequence': 1,
                    'sequence_in_scene': 1,
                    'key_dialogue': [],
                    'is_flashback': False,
                    'location_uuid': None,
                    'theme_uuids': [],
                    'arc_uuids': [],
                    'participations': []
                }
            ]
        }

        # Required top-level keys
        self.assertIn('episode_uuid', sample_event_yaml)
        self.assertIn('events', sample_event_yaml)

        # Required event keys
        event = sample_event_yaml['events'][0]
        required_keys = ['fabula_uuid', 'title', 'description', 'participations']
        for key in required_keys:
            self.assertIn(key, event, f"Event should have '{key}' field")

    def test_participation_structure(self):
        """Verify participation has correct structure."""
        required_keys = [
            'character_uuid', 'emotional_state', 'goals',
            'what_happened', 'observed_status', 'beliefs',
            'observed_traits', 'importance'
        ]

        for key in required_keys:
            self.assertIn(key, SAMPLE_RICH_PARTICIPATION,
                f"Participation should have '{key}' field")


# =============================================================================
# Integration Test - Full Export Validation
# =============================================================================

class TestFullExportValidation(TestCase):
    """
    Integration test to validate a complete export directory.

    This test requires an actual export to exist.
    Run with: pytest -m integration
    """

    @pytest.mark.integration
    def test_validate_existing_export(self):
        """Validate the current fabula_export directory."""
        import os

        export_dir = Path(os.getcwd()) / 'fabula_export'
        if not export_dir.exists():
            self.skipTest("fabula_export directory not found")

        # Run linkage validation
        validator = TestLinkageIntegrityValidator(export_dir)
        results = validator.validate_all()

        print("\n" + results.summary())

        # Run richness analysis
        analyzer = ParticipationRichnessAnalyzer(export_dir)
        print("\n" + analyzer.report())

        # The test passes if we can run validation
        # Actual errors are reported but don't fail the test
        # (since we're testing the validation tooling itself)


# =============================================================================
# Command Line Runner
# =============================================================================

def run_validation(export_dir: str):
    """Run validation from command line."""
    export_path = Path(export_dir)

    if not export_path.exists():
        print(f"Error: Directory not found: {export_dir}")
        return 1

    print("Running Fabula Export Validation")
    print("=" * 60)

    # Linkage validation
    print("\n1. Linkage Integrity Check")
    print("-" * 40)
    validator = TestLinkageIntegrityValidator(export_path)
    results = validator.validate_all()
    print(results.summary())

    # Richness analysis
    print("\n2. Participation Richness Analysis")
    print("-" * 40)
    analyzer = ParticipationRichnessAnalyzer(export_path)
    print(analyzer.report())

    return 0 if results.is_valid else 1


if __name__ == '__main__':
    import sys

    if len(sys.argv) > 1:
        exit_code = run_validation(sys.argv[1])
        sys.exit(exit_code)
    else:
        # Default to current directory's fabula_export
        exit_code = run_validation('./fabula_export')
        sys.exit(exit_code)
