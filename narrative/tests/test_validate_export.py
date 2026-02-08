"""
Tests for the validate_export management command and ExportValidator class.
"""
import os
import tempfile
from pathlib import Path

import yaml
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO

from narrative.management.commands.validate_export import ExportValidator


class ExportValidatorExtractListTest(TestCase):
    """Tests for ExportValidator.extract_list helper."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'), verbose=False)

    def test_none_input(self):
        self.assertEqual(self.validator.extract_list(None), [])

    def test_list_input(self):
        data = [{'a': 1}, {'b': 2}]
        self.assertEqual(self.validator.extract_list(data), data)

    def test_dict_with_items_key(self):
        data = {'items': [{'a': 1}]}
        self.assertEqual(self.validator.extract_list(data), [{'a': 1}])

    def test_dict_with_data_key(self):
        data = {'data': [{'a': 1}]}
        self.assertEqual(self.validator.extract_list(data), [{'a': 1}])

    def test_dict_with_custom_key(self):
        data = {'characters': [{'name': 'Josh'}]}
        result = self.validator.extract_list(data, ['characters'])
        self.assertEqual(result, [{'name': 'Josh'}])

    def test_dict_without_matching_key(self):
        data = {'other': 'value'}
        result = self.validator.extract_list(data)
        self.assertEqual(result, [data])


class ExportValidatorValidateCharactersTest(TestCase):
    """Tests for character validation."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))

    def test_valid_characters(self):
        self.validator.characters = [
            {'fabula_uuid': 'char_001', 'canonical_name': 'Josh Lyman'},
            {'fabula_uuid': 'char_002', 'canonical_name': 'Donna Moss'},
        ]
        result = self.validator.validate_characters()
        self.assertEqual(result['errors'], 0)

    def test_missing_uuid(self):
        self.validator.characters = [
            {'canonical_name': 'Josh Lyman'},
        ]
        result = self.validator.validate_characters()
        self.assertEqual(result['errors'], 1)
        self.assertIn('missing fabula_uuid', result['details'][0])

    def test_missing_canonical_name(self):
        self.validator.characters = [
            {'fabula_uuid': 'char_001'},
        ]
        result = self.validator.validate_characters()
        self.assertEqual(result['errors'], 1)
        self.assertIn('missing canonical_name', result['details'][0])

    def test_both_missing(self):
        self.validator.characters = [{}]
        result = self.validator.validate_characters()
        self.assertEqual(result['errors'], 2)


class ExportValidatorValidateLocationsTest(TestCase):
    """Tests for location validation."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))

    def test_valid_locations(self):
        self.validator.locations = [
            {'fabula_uuid': 'loc_001', 'canonical_name': 'Oval Office'},
        ]
        result = self.validator.validate_locations()
        self.assertEqual(result['errors'], 0)

    def test_missing_uuid(self):
        self.validator.locations = [{'canonical_name': 'Oval Office'}]
        result = self.validator.validate_locations()
        self.assertEqual(result['errors'], 1)

    def test_missing_name(self):
        self.validator.locations = [{'fabula_uuid': 'loc_001'}]
        result = self.validator.validate_locations()
        self.assertEqual(result['errors'], 1)


class ExportValidatorValidateThemesTest(TestCase):
    """Tests for theme validation."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))

    def test_valid_themes(self):
        self.validator.themes = [
            {'fabula_uuid': 'theme_001', 'name': 'Power'},
        ]
        result = self.validator.validate_themes()
        self.assertEqual(result['errors'], 0)

    def test_missing_name(self):
        self.validator.themes = [{'fabula_uuid': 'theme_001'}]
        result = self.validator.validate_themes()
        self.assertEqual(result['errors'], 1)


class ExportValidatorValidateArcsTest(TestCase):
    """Tests for arc validation."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))

    def test_valid_arcs(self):
        self.validator.arcs = [
            {'fabula_uuid': 'arc_001', 'title': 'Internal Conflict', 'arc_type': 'INTERNAL'},
        ]
        result = self.validator.validate_arcs()
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['warnings'], 0)

    def test_unknown_arc_type_warning(self):
        self.validator.arcs = [
            {'fabula_uuid': 'arc_001', 'title': 'Test', 'arc_type': 'UNKNOWN_TYPE'},
        ]
        result = self.validator.validate_arcs()
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['warnings'], 1)

    def test_missing_title_and_description(self):
        self.validator.arcs = [{'fabula_uuid': 'arc_001'}]
        result = self.validator.validate_arcs()
        self.assertEqual(result['errors'], 1)

    def test_has_description_but_no_title(self):
        self.validator.arcs = [
            {'fabula_uuid': 'arc_001', 'description': 'Some desc'},
        ]
        result = self.validator.validate_arcs()
        self.assertEqual(result['errors'], 0)


class ExportValidatorValidateEventsTest(TestCase):
    """Tests for event validation."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))
        self.validator.location_uuids = {'loc_001'}
        self.validator.theme_uuids = {'theme_001'}
        self.validator.arc_uuids = {'arc_001'}

    def test_valid_event(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'title': 'Staff Meeting',
                'description': 'The staff meets',
                'location_uuid': 'loc_001',
                'theme_uuids': ['theme_001'],
                'arc_uuids': ['arc_001'],
            },
        ]
        result = self.validator.validate_events()
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['warnings'], 0)

    def test_missing_uuid(self):
        self.validator.events = [{'title': 'No UUID'}]
        result = self.validator.validate_events()
        self.assertEqual(result['errors'], 1)

    def test_missing_title_warning(self):
        self.validator.events = [
            {'fabula_uuid': 'event_001', 'description': 'Has desc'},
        ]
        result = self.validator.validate_events()
        self.assertEqual(result['warnings'], 1)

    def test_unknown_location_error(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'title': 'Test',
                'description': 'Test',
                'location_uuid': 'loc_nonexistent',
            },
        ]
        result = self.validator.validate_events()
        self.assertEqual(result['errors'], 1)
        self.assertIn('unknown location', result['details'][0])

    def test_unknown_theme_error(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'title': 'Test',
                'description': 'Test',
                'theme_uuids': ['theme_nonexistent'],
            },
        ]
        result = self.validator.validate_events()
        self.assertEqual(result['errors'], 1)
        self.assertIn('unknown theme', result['details'][0])

    def test_unknown_arc_error(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'title': 'Test',
                'description': 'Test',
                'arc_uuids': ['arc_nonexistent'],
            },
        ]
        result = self.validator.validate_events()
        self.assertEqual(result['errors'], 1)
        self.assertIn('unknown arc', result['details'][0])


class ExportValidatorValidateParticipationsTest(TestCase):
    """Tests for participation validation."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))
        self.validator.character_uuids = {'char_001', 'char_002'}

    def test_valid_participations(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'participations': [
                    {'character_uuid': 'char_001'},
                    {'character_uuid': 'char_002'},
                ],
            },
        ]
        result = self.validator.validate_participations()
        self.assertEqual(result['errors'], 0)

    def test_missing_character_uuid(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'participations': [
                    {'emotional_state': 'happy'},
                ],
            },
        ]
        result = self.validator.validate_participations()
        self.assertEqual(result['errors'], 1)
        self.assertIn('missing character_uuid', result['details'][0])

    def test_unknown_character(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'participations': [
                    {'character_uuid': 'char_nonexistent'},
                ],
            },
        ]
        result = self.validator.validate_participations()
        self.assertEqual(result['errors'], 1)
        self.assertIn('unknown character', result['details'][0])


class ExportValidatorValidateConnectionsTest(TestCase):
    """Tests for connection validation."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))
        self.validator.event_uuids = {'event_001', 'event_002'}

    def test_valid_connection(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'from_event_uuid': 'event_001',
                'to_event_uuid': 'event_002',
                'connection_type': 'CAUSAL',
                'strength': 'strong',
                'description': 'A causes B',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['errors'], 0)
        self.assertEqual(result['warnings'], 0)

    def test_missing_from_event(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'to_event_uuid': 'event_002',
                'connection_type': 'CAUSAL',
                'description': 'Test',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['errors'], 1)
        self.assertIn('missing from_event_uuid', result['details'][0])

    def test_missing_to_event(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'from_event_uuid': 'event_001',
                'connection_type': 'CAUSAL',
                'description': 'Test',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['errors'], 1)
        self.assertIn('missing to_event_uuid', result['details'][0])

    def test_unknown_from_event(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'from_event_uuid': 'event_nonexistent',
                'to_event_uuid': 'event_002',
                'connection_type': 'CAUSAL',
                'description': 'Test',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['errors'], 1)
        self.assertIn('from unknown event', result['details'][0])

    def test_missing_connection_type(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'from_event_uuid': 'event_001',
                'to_event_uuid': 'event_002',
                'description': 'Test',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['errors'], 1)
        self.assertIn('missing connection_type', result['details'][0])

    def test_unknown_connection_type_warning(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'from_event_uuid': 'event_001',
                'to_event_uuid': 'event_002',
                'connection_type': 'BOGUS_TYPE',
                'description': 'Test',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['warnings'], 1)

    def test_unknown_strength_warning(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'from_event_uuid': 'event_001',
                'to_event_uuid': 'event_002',
                'connection_type': 'CAUSAL',
                'strength': 'ultra',
                'description': 'Test',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['warnings'], 1)

    def test_missing_description_warning(self):
        self.validator.connections = [
            {
                'fabula_uuid': 'conn_001',
                'from_event_uuid': 'event_001',
                'to_event_uuid': 'event_002',
                'connection_type': 'CAUSAL',
            },
        ]
        result = self.validator.validate_connections()
        self.assertEqual(result['warnings'], 1)


class ExportValidatorAnalyzeRichnessTest(TestCase):
    """Tests for participation richness analysis."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))

    def test_rich_participation(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'participations': [
                    {
                        'character_uuid': 'char_001',
                        'emotional_state': 'Determined',
                        'goals': ['Win'],
                        'what_happened': 'Argued',
                        'observed_status': 'Leader',
                        'beliefs': ['Democracy'],
                        'observed_traits': ['passionate'],
                    },
                ],
            },
        ]
        result = self.validator.analyze_richness()
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rich'], 1)
        self.assertEqual(result['sparse'], 0)
        self.assertAlmostEqual(result['rich_percentage'], 100.0)
        self.assertAlmostEqual(result['field_coverage']['emotional_state']['percentage'], 100.0)

    def test_sparse_participation(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'participations': [
                    {
                        'character_uuid': 'char_001',
                        'what_happened': 'Was there',
                    },
                ],
            },
        ]
        result = self.validator.analyze_richness()
        self.assertEqual(result['total'], 1)
        self.assertEqual(result['rich'], 0)
        self.assertEqual(result['sparse'], 1)

    def test_empty_participations(self):
        self.validator.events = []
        result = self.validator.analyze_richness()
        self.assertEqual(result['total'], 0)
        self.assertAlmostEqual(result['rich_percentage'], 0.0)

    def test_mixed_richness(self):
        self.validator.events = [
            {
                'fabula_uuid': 'event_001',
                'participations': [
                    {'character_uuid': 'c1', 'emotional_state': 'happy'},
                    {'character_uuid': 'c2', 'what_happened': 'stood there'},
                ],
            },
        ]
        result = self.validator.analyze_richness()
        self.assertEqual(result['total'], 2)
        self.assertEqual(result['rich'], 1)
        self.assertAlmostEqual(result['rich_percentage'], 50.0)


class ExportValidatorValidateAllTest(TestCase):
    """Tests for validate_all integration."""

    def setUp(self):
        self.validator = ExportValidator(Path('/tmp'))

    def test_empty_data(self):
        results = self.validator.validate_all()
        self.assertIn('Characters', results)
        self.assertIn('Locations', results)
        self.assertIn('Themes', results)
        self.assertIn('Arcs', results)
        self.assertIn('Events', results)
        self.assertIn('Participations', results)
        self.assertIn('Connections', results)
        # All should pass with empty data
        for name, result in results.items():
            self.assertEqual(result['errors'], 0, f"{name} should have 0 errors")


class ExportValidatorLoadYamlTest(TestCase):
    """Tests for YAML file loading."""

    def test_nonexistent_file(self):
        validator = ExportValidator(Path('/tmp'))
        result = validator.load_yaml('nonexistent.yaml')
        self.assertIsNone(result)

    def test_load_valid_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = Path(tmpdir) / 'test.yaml'
            filepath.write_text(yaml.dump({'key': 'value'}))
            validator = ExportValidator(Path(tmpdir))
            result = validator.load_yaml('test.yaml')
            self.assertEqual(result, {'key': 'value'})


class ExportValidatorLoadAllDataTest(TestCase):
    """Tests for load_all_data with YAML files."""

    def test_load_from_yaml_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create test YAML files
            (tmppath / 'characters.yaml').write_text(yaml.dump([
                {'fabula_uuid': 'char_001', 'canonical_name': 'Josh'},
            ]))
            (tmppath / 'locations.yaml').write_text(yaml.dump([
                {'fabula_uuid': 'loc_001', 'canonical_name': 'Oval Office'},
            ]))
            (tmppath / 'organizations.yaml').write_text(yaml.dump([]))
            (tmppath / 'themes.yaml').write_text(yaml.dump([
                {'fabula_uuid': 'theme_001', 'name': 'Power'},
            ]))
            (tmppath / 'arcs.yaml').write_text(yaml.dump([]))
            (tmppath / 'connections.yaml').write_text(yaml.dump([]))

            validator = ExportValidator(tmppath)
            validator.load_all_data()

            self.assertEqual(len(validator.characters), 1)
            self.assertEqual(len(validator.locations), 1)
            self.assertEqual(len(validator.themes), 1)
            self.assertIn('char_001', validator.character_uuids)
            self.assertIn('loc_001', validator.location_uuids)
            self.assertIn('theme_001', validator.theme_uuids)

    def test_load_events_from_subdirectory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create minimal files
            for fname in ['characters.yaml', 'locations.yaml', 'organizations.yaml',
                          'themes.yaml', 'arcs.yaml', 'connections.yaml']:
                (tmppath / fname).write_text(yaml.dump([]))

            # Create events subdirectory
            events_dir = tmppath / 'events'
            events_dir.mkdir()
            (events_dir / 'episode_001.yaml').write_text(yaml.dump({
                'events': [
                    {'fabula_uuid': 'event_001', 'title': 'Staff Meeting'},
                    {'fabula_uuid': 'event_002', 'title': 'Confrontation'},
                ]
            }))

            validator = ExportValidator(tmppath)
            validator.load_all_data()

            self.assertEqual(len(validator.events), 2)
            self.assertIn('event_001', validator.event_uuids)
            self.assertIn('event_002', validator.event_uuids)


class ValidateExportCommandTest(TestCase):
    """Tests for the management command itself."""

    def test_nonexistent_directory(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command('validate_export', '--input=/nonexistent/path', stdout=out, stderr=out)

    def test_valid_export_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create minimal valid export
            (tmppath / 'characters.yaml').write_text(yaml.dump([
                {'fabula_uuid': 'char_001', 'canonical_name': 'Josh'},
            ]))
            (tmppath / 'locations.yaml').write_text(yaml.dump([
                {'fabula_uuid': 'loc_001', 'canonical_name': 'Office'},
            ]))
            for fname in ['organizations.yaml', 'themes.yaml', 'arcs.yaml', 'connections.yaml']:
                (tmppath / fname).write_text(yaml.dump([]))

            out = StringIO()
            call_command('validate_export', f'--input={tmpdir}', stdout=out)
            output = out.getvalue()
            self.assertIn('Validation PASSED', output)

    def test_strict_mode_raises_on_errors(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)

            # Create export with errors (character missing uuid)
            (tmppath / 'characters.yaml').write_text(yaml.dump([
                {'canonical_name': 'Missing UUID'},
            ]))
            for fname in ['locations.yaml', 'organizations.yaml', 'themes.yaml',
                          'arcs.yaml', 'connections.yaml']:
                (tmppath / fname).write_text(yaml.dump([]))

            out = StringIO()
            with self.assertRaises(CommandError) as ctx:
                call_command('validate_export', f'--input={tmpdir}', '--strict',
                             stdout=out, stderr=out)
            self.assertIn('FAILED', str(ctx.exception))
