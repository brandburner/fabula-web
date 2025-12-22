"""
Unit tests for the export_from_neo4j management command.

Tests cover:
1. YAML configuration and formatting
2. Neo4j query execution and data extraction
3. Data transformation and cleaning
4. File writing and directory structure
5. Error handling and edge cases
"""

import pytest
import yaml
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from narrative.management.commands.export_from_neo4j import (
    Neo4jExporter,
    setup_yaml,
    str_representer,
    Command
)


# =============================================================================
# Test YAML Configuration
# =============================================================================

class TestYAMLConfiguration(TestCase):
    """Test YAML formatting and configuration."""

    def setUp(self):
        """Set up YAML configuration before each test."""
        setup_yaml()

    def test_multiline_string_formatting(self):
        """Test that multi-line strings use block literal style."""
        data = {
            'description': 'This is a description\nwith multiple lines\nfor testing',
            'simple': 'single line'
        }

        output = yaml.dump(data, allow_unicode=True)

        # Multi-line should use block literal (|)
        self.assertIn('description: |', output)
        # Single line should be plain
        self.assertIn('simple: single line', output)

    def test_str_representer(self):
        """Test custom string representer."""
        dumper = Mock()

        # Test multi-line string
        multiline = "Line 1\nLine 2"
        str_representer(dumper, multiline)
        dumper.represent_scalar.assert_called_with(
            'tag:yaml.org,2002:str',
            multiline,
            style='|'
        )

        # Test single line string
        dumper.reset_mock()
        singleline = "Just one line"
        str_representer(dumper, singleline)
        dumper.represent_scalar.assert_called_with(
            'tag:yaml.org,2002:str',
            singleline
        )

    def test_yaml_default_flow_style(self):
        """Test that default flow style is disabled for readability."""
        data = {
            'list': [1, 2, 3],
            'nested': {'key': 'value'}
        }

        output = yaml.dump(data)

        # Should use block style, not flow style
        self.assertNotIn('[', output)  # Flow style would use brackets
        self.assertNotIn('{', output)  # Flow style would use braces


# =============================================================================
# Test Neo4j Exporter - Initialization and Connection
# =============================================================================

class TestNeo4jExporterInit(TestCase):
    """Test Neo4jExporter initialization and connection."""

    def test_initialization(self):
        """Test exporter initializes with correct parameters."""
        output_dir = Path('/tmp/test_export')
        exporter = Neo4jExporter(
            uri='bolt://localhost:7689',
            user='neo4j',
            password='test_password',
            output_dir=output_dir
        )

        self.assertEqual(exporter.uri, 'bolt://localhost:7689')
        self.assertEqual(exporter.user, 'neo4j')
        self.assertEqual(exporter.password, 'test_password')
        self.assertEqual(exporter.output_dir, output_dir)
        self.assertIsNone(exporter.driver)

        # Check stats initialization
        self.assertEqual(exporter.stats['event_count'], 0)
        self.assertEqual(exporter.stats['character_count'], 0)

    @patch('narrative.management.commands.export_from_neo4j.GraphDatabase')
    def test_successful_connection(self, mock_graphdb):
        """Test successful Neo4j connection."""
        mock_driver = Mock()
        mock_graphdb.driver.return_value = mock_driver

        exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))
        result = exporter.connect()

        self.assertTrue(result)
        mock_graphdb.driver.assert_called_once_with(
            'bolt://localhost:7689',
            auth=('neo4j', 'password')
        )
        mock_driver.verify_connectivity.assert_called_once()
        self.assertEqual(exporter.driver, mock_driver)

    @patch('narrative.management.commands.export_from_neo4j.GraphDatabase')
    def test_failed_connection(self, mock_graphdb):
        """Test handling of connection failure."""
        mock_graphdb.driver.side_effect = Exception("Connection refused")

        exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))

        with self.assertRaises(CommandError) as cm:
            exporter.connect()

        self.assertIn('Failed to connect to Neo4j', str(cm.exception))

    def test_close_connection(self):
        """Test closing Neo4j connection."""
        exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))
        mock_driver = Mock()
        exporter.driver = mock_driver

        exporter.close()

        mock_driver.close.assert_called_once()


# =============================================================================
# Test Query Execution and Data Extraction
# =============================================================================

class TestQueryExecution(TestCase):
    """Test Neo4j query execution and result handling."""

    def setUp(self):
        """Set up mock driver for tests."""
        self.exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))
        self.mock_driver = Mock()
        self.exporter.driver = self.mock_driver

    def test_execute_query(self):
        """Test query execution returns correct results."""
        # Mock session and result
        mock_session = Mock()
        mock_result = [
            {'name': 'Test1', 'value': 123},
            {'name': 'Test2', 'value': 456}
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        query = "MATCH (n) RETURN n"
        params = {'key': 'value'}

        results = self.exporter.execute_query(query, params)

        mock_session.run.assert_called_once_with(query, params)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['name'], 'Test1')

    def test_safe_get_with_valid_node(self):
        """Test safe_get retrieves property from node."""
        node = {'uuid': '12345', 'name': 'Test'}

        result = self.exporter.safe_get(node, 'uuid')
        self.assertEqual(result, '12345')

        result = self.exporter.safe_get(node, 'missing', 'default')
        self.assertEqual(result, 'default')

    def test_safe_get_with_none_node(self):
        """Test safe_get handles None node gracefully."""
        result = self.exporter.safe_get(None, 'key', 'default')
        self.assertEqual(result, 'default')


# =============================================================================
# Test Character Export
# =============================================================================

class TestCharacterExport(TestCase):
    """Test character/agent data export."""

    def setUp(self):
        """Set up exporter with mocked driver."""
        self.exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))
        self.mock_driver = Mock()
        self.exporter.driver = self.mock_driver

    def test_export_characters_basic(self):
        """Test basic character export."""
        mock_session = Mock()
        mock_result = [
            {
                'a': {
                    'uuid': 'agent_josh',
                    'canonical_name': 'Joshua Lyman',
                    'title_role': 'Deputy Chief of Staff',
                    'description': 'Political operator',
                    'traits': ['tactical', 'sarcastic'],
                    'aliases': ['Josh'],
                    'character_type': 'main',
                    'sphere_of_influence': 'Legislative affairs',
                    'appearance_count': 443
                },
                'org_uuid': 'org_white_house'
            }
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        characters = self.exporter.export_characters()

        self.assertEqual(len(characters), 1)
        self.assertEqual(characters[0]['fabula_uuid'], 'agent_josh')
        self.assertEqual(characters[0]['canonical_name'], 'Joshua Lyman')
        self.assertEqual(characters[0]['affiliated_organization_uuid'], 'org_white_house')
        self.assertEqual(self.exporter.stats['character_count'], 1)

    def test_export_characters_parses_string_traits(self):
        """Test that comma-separated trait strings are parsed to lists."""
        mock_session = Mock()
        mock_result = [
            {
                'a': {
                    'uuid': 'agent_test',
                    'canonical_name': 'Test Character',
                    'description': 'Test',
                    'traits': 'smart, brave, funny',  # String instead of list
                    'aliases': 'Tester, TC',  # String instead of list
                    'character_type': 'guest',
                    'appearance_count': 5
                },
                'org_uuid': None
            }
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        characters = self.exporter.export_characters()

        self.assertEqual(characters[0]['traits'], ['smart', 'brave', 'funny'])
        self.assertEqual(characters[0]['aliases'], ['Tester', 'TC'])


# =============================================================================
# Test Event Export
# =============================================================================

class TestEventExport(TestCase):
    """Test event data export."""

    def setUp(self):
        """Set up exporter with mocked driver."""
        self.exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))
        self.mock_driver = Mock()
        self.exporter.driver = self.mock_driver

    def test_export_events_by_episode(self):
        """Test exporting events for a specific episode."""
        mock_session = Mock()
        mock_result = [
            {
                'e': {
                    'uuid': 'event_123',
                    'title': 'Test Event',
                    'description': 'Event description',
                    'scene_sequence': 5,
                    'sequence_in_scene': 2,
                    'key_dialogue': ['Line 1', 'Line 2'],
                    'is_flashback': False
                },
                'location_uuid': 'loc_oval_office',
                'theme_uuids': ['theme_1', 'theme_2'],
                'arc_uuids': ['arc_1'],
                'participations': [
                    {
                        'character_uuid': 'agent_josh',
                        'emotional_state': 'Tense',
                        'goals': ['Win the vote', 'Stay calm'],
                        'what_happened': 'Josh argued',
                        'observed_status': 'Primary',
                        'beliefs': ['Democracy works'],
                        'observed_traits': ['tactical'],
                        'importance': 'primary'
                    }
                ]
            }
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        events = self.exporter.export_events_by_episode('ep_test')

        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event['fabula_uuid'], 'event_123')
        self.assertEqual(event['title'], 'Test Event')
        self.assertEqual(event['location_uuid'], 'loc_oval_office')
        self.assertEqual(len(event['participations']), 1)
        self.assertEqual(event['participations'][0]['character_uuid'], 'agent_josh')

    def test_export_events_parses_string_goals(self):
        """Test that newline-separated goals are parsed to lists."""
        mock_session = Mock()
        mock_result = [
            {
                'e': {
                    'uuid': 'event_123',
                    'title': 'Test Event',
                    'description': 'Test',
                    'scene_sequence': 1,
                    'sequence_in_scene': 1,
                    'key_dialogue': [],
                    'is_flashback': False
                },
                'location_uuid': None,
                'theme_uuids': [],
                'arc_uuids': [],
                'participations': [
                    {
                        'character_uuid': 'agent_test',
                        'emotional_state': 'Happy',
                        'goals': 'Goal 1\nGoal 2\nGoal 3',  # String with newlines
                        'what_happened': 'Something',
                        'observed_status': 'Status',
                        'beliefs': None,
                        'observed_traits': None,
                        'importance': 'primary'
                    }
                ]
            }
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        events = self.exporter.export_events_by_episode('ep_test')

        participation = events[0]['participations'][0]
        self.assertEqual(participation['goals'], ['Goal 1', 'Goal 2', 'Goal 3'])
        self.assertEqual(participation['beliefs'], [])
        self.assertEqual(participation['observed_traits'], [])

    def test_export_events_filters_null_participations(self):
        """Test that null participations from OPTIONAL MATCH are filtered out."""
        mock_session = Mock()
        mock_result = [
            {
                'e': {
                    'uuid': 'event_123',
                    'title': 'Test Event',
                    'description': 'Test',
                    'scene_sequence': 1,
                    'sequence_in_scene': 1,
                    'key_dialogue': [],
                    'is_flashback': False
                },
                'location_uuid': None,
                'theme_uuids': [],
                'arc_uuids': [],
                'participations': [
                    {'character_uuid': None},  # Should be filtered
                    {
                        'character_uuid': 'agent_valid',
                        'emotional_state': 'Test',
                        'goals': [],
                        'what_happened': 'Test',
                        'observed_status': 'Test',
                        'beliefs': [],
                        'observed_traits': [],
                        'importance': 'primary'
                    }
                ]
            }
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        events = self.exporter.export_events_by_episode('ep_test')

        # Should only have 1 participation (the valid one)
        self.assertEqual(len(events[0]['participations']), 1)
        self.assertEqual(events[0]['participations'][0]['character_uuid'], 'agent_valid')


# =============================================================================
# Test Series Export
# =============================================================================

class TestSeriesExport(TestCase):
    """Test series/season/episode hierarchy export."""

    def setUp(self):
        """Set up exporter with mocked driver."""
        self.exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))
        self.mock_driver = Mock()
        self.exporter.driver = self.mock_driver

    def test_export_series_hierarchy(self):
        """Test exporting nested series/season/episode structure."""
        mock_session = Mock()
        mock_result = [
            {
                's': {
                    'uuid': 'series_westwing',
                    'title': 'The West Wing',
                    'description': 'Political drama'
                },
                'season': {
                    'uuid': 'season_1',
                    'season_number': 1,
                    'description': 'Season 1'
                },
                'ep': {
                    'uuid': 'ep_1',
                    'episode_number': 1,
                    'title': 'Pilot',
                    'logline': 'The beginning',
                    'high_level_summary': 'Summary',
                    'dominant_tone': 'Hopeful'
                }
            },
            {
                's': {
                    'uuid': 'series_westwing',
                    'title': 'The West Wing',
                    'description': 'Political drama'
                },
                'season': {
                    'uuid': 'season_1',
                    'season_number': 1,
                    'description': 'Season 1'
                },
                'ep': {
                    'uuid': 'ep_2',
                    'episode_number': 2,
                    'title': 'Post Hoc Ergo Propter Hoc',
                    'logline': 'Episode 2',
                    'high_level_summary': 'Summary 2',
                    'dominant_tone': 'Tense'
                }
            }
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        series = self.exporter.export_series()

        self.assertEqual(series['fabula_uuid'], 'series_westwing')
        self.assertEqual(series['title'], 'The West Wing')
        self.assertEqual(len(series['seasons']), 1)
        self.assertEqual(len(series['seasons'][0]['episodes']), 2)
        self.assertEqual(series['seasons'][0]['episodes'][0]['title'], 'Pilot')


# =============================================================================
# Test Connection Export
# =============================================================================

class TestConnectionExport(TestCase):
    """Test narrative connection export."""

    def setUp(self):
        """Set up exporter with mocked driver."""
        self.exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))
        self.mock_driver = Mock()
        self.exporter.driver = self.mock_driver

    def test_export_connections(self):
        """Test exporting narrative connections."""
        mock_session = Mock()
        mock_result = [
            {
                'from_uuid': 'event_1',
                'to_uuid': 'event_2',
                'connection_type': 'CAUSAL',
                'strength': 'strong',
                'description': 'Event 1 caused Event 2',
                'connection_uuid': 'conn_123'
            },
            {
                'from_uuid': 'event_2',
                'to_uuid': 'event_3',
                'connection_type': 'FORESHADOWING',
                'strength': 'medium',
                'description': 'Event 2 foreshadows Event 3',
                'connection_uuid': 'conn_456'
            }
        ]

        self.mock_driver.session.return_value.__enter__.return_value = mock_session
        mock_session.run.return_value = mock_result

        connections = self.exporter.export_connections()

        self.assertEqual(len(connections), 2)
        self.assertEqual(connections[0]['connection_type'], 'CAUSAL')
        self.assertEqual(connections[1]['connection_type'], 'FORESHADOWING')
        self.assertEqual(self.exporter.stats['connection_count'], 2)


# =============================================================================
# Test File Writing
# =============================================================================

class TestFileWriting(TestCase):
    """Test YAML file writing functionality."""

    def setUp(self):
        """Set up exporter and temp directory."""
        import tempfile
        self.temp_dir = Path(tempfile.mkdtemp())
        self.exporter = Neo4jExporter(
            'bolt://localhost:7689',
            'neo4j',
            'password',
            self.temp_dir
        )

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_write_yaml_creates_directory(self):
        """Test that write_yaml creates parent directories."""
        setup_yaml()

        nested_path = self.temp_dir / 'nested' / 'dir' / 'test.yaml'
        data = {'key': 'value'}

        self.exporter.write_yaml(nested_path, data)

        self.assertTrue(nested_path.exists())
        self.assertTrue(nested_path.parent.exists())

    def test_write_yaml_with_header(self):
        """Test that write_yaml includes header comment."""
        setup_yaml()

        filepath = self.temp_dir / 'test.yaml'
        data = {'key': 'value'}

        self.exporter.write_yaml(filepath, data, header_comment='Test Header')

        with open(filepath, 'r') as f:
            content = f.read()

        self.assertIn('# Test Header', content)
        self.assertIn('# Generated:', content)

    def test_write_yaml_preserves_unicode(self):
        """Test that YAML writing preserves unicode characters."""
        setup_yaml()

        filepath = self.temp_dir / 'unicode.yaml'
        data = {'name': 'José García', 'description': '日本語'}

        self.exporter.write_yaml(filepath, data)

        with open(filepath, 'r', encoding='utf-8') as f:
            loaded = yaml.safe_load(f)

        self.assertEqual(loaded['name'], 'José García')
        self.assertEqual(loaded['description'], '日本語')


# =============================================================================
# Test Manifest Creation
# =============================================================================

class TestManifestCreation(TestCase):
    """Test export manifest creation."""

    def test_create_manifest(self):
        """Test manifest contains correct metadata."""
        exporter = Neo4jExporter('bolt://localhost:7689', 'neo4j', 'password', Path('/tmp'))

        # Set some stats
        exporter.stats['season_count'] = 1
        exporter.stats['episode_count'] = 22
        exporter.stats['event_count'] = 500
        exporter.stats['character_count'] = 50

        series_data = {'title': 'The West Wing'}

        manifest = exporter.create_manifest(series_data)

        self.assertEqual(manifest['fabula_version'], '2.0.0')
        self.assertEqual(manifest['series_title'], 'The West Wing')
        self.assertEqual(manifest['season_count'], 1)
        self.assertEqual(manifest['episode_count'], 22)
        self.assertEqual(manifest['event_count'], 500)
        self.assertEqual(manifest['character_count'], 50)
        self.assertIn('export_date', manifest)
        self.assertIn('source_graph', manifest)


# =============================================================================
# Test Django Command
# =============================================================================

class TestDjangoCommand(TestCase):
    """Test Django management command interface."""

    @patch('narrative.management.commands.export_from_neo4j.Neo4jExporter')
    @patch('narrative.management.commands.export_from_neo4j.Path')
    def test_command_with_defaults(self, mock_path, mock_exporter_class):
        """Test command execution with default arguments."""
        mock_exporter = Mock()
        mock_exporter_class.return_value = mock_exporter
        mock_path.return_value.absolute.return_value = Path('/tmp/fabula_export')

        out = StringIO()
        call_command('export_from_neo4j', stdout=out)

        mock_exporter.export_all.assert_called_once()

    @patch('narrative.management.commands.export_from_neo4j.Neo4jExporter')
    def test_command_with_custom_output(self, mock_exporter_class):
        """Test command with custom output directory."""
        mock_exporter = Mock()
        mock_exporter_class.return_value = mock_exporter

        out = StringIO()
        call_command('export_from_neo4j', '--output', '/custom/path', stdout=out)

        # Check exporter was initialized with custom path
        args = mock_exporter_class.call_args
        self.assertIn('/custom/path', str(args[0][3]))

    @patch('narrative.management.commands.export_from_neo4j.Neo4jExporter')
    def test_command_handles_export_failure(self, mock_exporter_class):
        """Test command handles export failures gracefully."""
        mock_exporter = Mock()
        mock_exporter.export_all.side_effect = Exception("Export failed")
        mock_exporter_class.return_value = mock_exporter

        with self.assertRaises(CommandError) as cm:
            call_command('export_from_neo4j', '--output', '/tmp/test')

        self.assertIn('Export failed', str(cm.exception))


# =============================================================================
# Integration Test (requires running Neo4j)
# =============================================================================

@pytest.mark.integration
class TestNeo4jIntegration(TestCase):
    """
    Integration tests that require a running Neo4j instance.

    These tests are marked with @pytest.mark.integration and should be
    run separately with: pytest -m integration

    Skip these tests in normal test runs.
    """

    @pytest.mark.skip(reason="Requires running Neo4j instance")
    def test_full_export_integration(self):
        """Test full export against real Neo4j database."""
        import tempfile
        import shutil

        temp_dir = Path(tempfile.mkdtemp())

        try:
            exporter = Neo4jExporter(
                'bolt://localhost:7689',
                'neo4j',
                'mythology',
                temp_dir
            )

            exporter.export_all()

            # Verify files were created
            self.assertTrue((temp_dir / 'manifest.yaml').exists())
            self.assertTrue((temp_dir / 'series.yaml').exists())
            self.assertTrue((temp_dir / 'characters.yaml').exists())
            self.assertTrue((temp_dir / 'events').exists())

        finally:
            shutil.rmtree(temp_dir)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
