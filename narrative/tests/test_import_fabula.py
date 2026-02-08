"""
Tests for the import_fabula management command.

Focuses on ImportStats, utility methods, and importable snippet methods.
Does NOT test the full import pipeline (which requires complex YAML fixtures).
"""
import tempfile
from pathlib import Path
from io import StringIO

import yaml
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from wagtail.models import Page

from narrative.management.commands.import_fabula import Command, ImportStats
from narrative.models import (
    Theme, ConflictArc, Location,
    SeriesIndexPage, SeasonPage, EpisodePage,
    CharacterPage, CharacterIndexPage,
    OrganizationPage, OrganizationIndexPage,
    ObjectPage, ObjectIndexPage,
    EventPage, EventIndexPage,
)


# =============================================================================
# IMPORT STATS TESTS
# =============================================================================

class ImportStatsTest(TestCase):
    """Tests for ImportStats tracking class."""

    def test_record_created(self):
        stats = ImportStats()
        stats.record_created('Theme')
        stats.record_created('Theme')
        stats.record_created('Location')
        self.assertEqual(stats.created['Theme'], 2)
        self.assertEqual(stats.created['Location'], 1)

    def test_record_updated(self):
        stats = ImportStats()
        stats.record_updated('Theme')
        self.assertEqual(stats.updated['Theme'], 1)

    def test_record_cross_season_match(self):
        stats = ImportStats()
        stats.record_cross_season_match('CharacterPage')
        self.assertEqual(stats.cross_season_matched['CharacterPage'], 1)

    def test_record_error(self):
        stats = ImportStats()
        stats.record_error('Something went wrong')
        self.assertEqual(len(stats.errors), 1)
        self.assertEqual(stats.errors[0], 'Something went wrong')

    def test_summary_created(self):
        stats = ImportStats()
        stats.record_created('Theme')
        stats.record_created('Theme')
        summary = stats.summary()
        self.assertIn('Created:', summary)
        self.assertIn('Theme: 2', summary)

    def test_summary_updated(self):
        stats = ImportStats()
        stats.record_updated('Location')
        summary = stats.summary()
        self.assertIn('Updated:', summary)
        self.assertIn('Location: 1', summary)

    def test_summary_cross_season(self):
        stats = ImportStats()
        stats.record_cross_season_match('CharacterPage')
        summary = stats.summary()
        self.assertIn('Cross-Season Matched', summary)

    def test_summary_errors(self):
        stats = ImportStats()
        for i in range(15):
            stats.record_error(f'Error {i}')
        summary = stats.summary()
        self.assertIn('Errors: 15', summary)
        self.assertIn('... and 5 more', summary)

    def test_summary_empty(self):
        stats = ImportStats()
        summary = stats.summary()
        self.assertIn('Import Summary', summary)


# =============================================================================
# COMMAND UTILITY METHOD TESTS
# =============================================================================

class CommandUtilityTest(TestCase):
    """Tests for Command utility methods."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.style = self.cmd.style  # Use default style
        self.cmd.verbose = False

    def test_unwrap_data_dict_with_key(self):
        data = {'themes': [{'name': 'Power'}]}
        result = self.cmd.unwrap_data(data, 'themes')
        self.assertEqual(result, [{'name': 'Power'}])

    def test_unwrap_data_bare_list(self):
        data = [{'name': 'Power'}]
        result = self.cmd.unwrap_data(data, 'themes')
        self.assertEqual(result, [{'name': 'Power'}])

    def test_unwrap_data_dict_without_key(self):
        data = {'other_key': [{'name': 'Power'}]}
        result = self.cmd.unwrap_data(data, 'themes')
        # Returns as-is since key not found and it's a dict
        self.assertEqual(result, data)

    def test_unwrap_data_none(self):
        result = self.cmd.unwrap_data(None, 'themes')
        self.assertEqual(result, [])

    def test_load_yaml_valid(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'key': 'value'}, f)
            f.flush()
            result = self.cmd.load_yaml(Path(f.name))
            self.assertEqual(result, {'key': 'value'})

    def test_load_yaml_required_missing(self):
        with self.assertRaises(CommandError):
            self.cmd.load_yaml(Path('/nonexistent/file.yaml'), required=True)

    def test_load_yaml_optional_missing(self):
        result = self.cmd.load_yaml(Path('/nonexistent/file.yaml'), required=False)
        self.assertIsNone(result)

    def test_make_unique_slug(self):
        slug = self.cmd.make_unique_slug('josh-lyman', 'agent_001')
        self.assertEqual(slug, 'josh-lyman-agent_001')

    def test_make_unique_slug_empty_uuid(self):
        slug = self.cmd.make_unique_slug('josh-lyman', '')
        self.assertEqual(slug, 'josh-lyman')

    def test_normalize_character_type_main(self):
        self.assertEqual(self.cmd.normalize_character_type('main'), 'main')
        self.assertEqual(self.cmd.normalize_character_type('Main Character'), 'main')
        self.assertEqual(self.cmd.normalize_character_type('MAIN'), 'main')

    def test_normalize_character_type_recurring(self):
        self.assertEqual(self.cmd.normalize_character_type('recurring'), 'recurring')
        self.assertEqual(self.cmd.normalize_character_type('Recurring Character'), 'recurring')

    def test_normalize_character_type_guest(self):
        self.assertEqual(self.cmd.normalize_character_type('guest'), 'guest')
        self.assertEqual(self.cmd.normalize_character_type('Guest Character'), 'guest')

    def test_normalize_character_type_mentioned(self):
        self.assertEqual(self.cmd.normalize_character_type('mentioned'), 'mentioned')
        self.assertEqual(self.cmd.normalize_character_type('Mentioned Only'), 'mentioned')

    def test_normalize_character_type_unknown(self):
        self.assertEqual(self.cmd.normalize_character_type('alien'), 'recurring')

    def test_normalize_character_type_empty(self):
        self.assertEqual(self.cmd.normalize_character_type(''), 'recurring')

    def test_truncate_field_short(self):
        self.assertEqual(self.cmd.truncate_field('short', 255), 'short')

    def test_truncate_field_none(self):
        self.assertIsNone(self.cmd.truncate_field(None, 255))

    def test_truncate_field_exact(self):
        text = 'x' * 255
        self.assertEqual(self.cmd.truncate_field(text, 255), text)

    def test_truncate_field_long(self):
        text = 'x' * 300
        result = self.cmd.truncate_field(text, 255)
        self.assertEqual(len(result), 255)
        self.assertTrue(result.endswith('...'))


class DedupeByGlobalIdTest(TestCase):
    """Tests for dedupe_by_global_id method."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False

    def test_no_duplicates(self):
        data = [
            {'global_id': 'ger_001', 'fabula_uuid': 'uuid_001', 'name': 'A'},
            {'global_id': 'ger_002', 'fabula_uuid': 'uuid_002', 'name': 'B'},
        ]
        result = self.cmd.dedupe_by_global_id(data, 'test')
        self.assertEqual(len(result), 2)

    def test_duplicate_global_id(self):
        data = [
            {'global_id': 'ger_001', 'fabula_uuid': 'uuid_001', 'name': 'A'},
            {'global_id': 'ger_001', 'fabula_uuid': 'uuid_002', 'name': 'A duplicate'},
        ]
        result = self.cmd.dedupe_by_global_id(data, 'test')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['name'], 'A')  # Keeps first occurrence

    def test_duplicate_fabula_uuid(self):
        data = [
            {'global_id': '', 'fabula_uuid': 'uuid_001', 'name': 'A'},
            {'global_id': '', 'fabula_uuid': 'uuid_001', 'name': 'A duplicate'},
        ]
        result = self.cmd.dedupe_by_global_id(data, 'test')
        self.assertEqual(len(result), 1)

    def test_empty_list(self):
        result = self.cmd.dedupe_by_global_id([], 'test')
        self.assertEqual(result, [])

    def test_no_ids(self):
        """Items without global_id or fabula_uuid are kept."""
        data = [
            {'name': 'A'},
            {'name': 'B'},
        ]
        result = self.cmd.dedupe_by_global_id(data, 'test')
        self.assertEqual(len(result), 2)

    def test_mixed_dedup(self):
        """Mix of items with and without global_id."""
        data = [
            {'global_id': 'ger_001', 'fabula_uuid': 'uuid_001', 'name': 'A'},
            {'global_id': 'ger_001', 'fabula_uuid': 'uuid_002', 'name': 'A dup'},
            {'global_id': 'ger_002', 'fabula_uuid': 'uuid_003', 'name': 'B'},
            {'name': 'C'},
        ]
        result = self.cmd.dedupe_by_global_id(data, 'test')
        self.assertEqual(len(result), 3)


class LoadEventsTest(TestCase):
    """Tests for load_events method."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False

    def test_load_events_from_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            events_dir = Path(tmpdir)
            (events_dir / 'ep01.yaml').write_text(yaml.dump({
                'episode_title': 'Pilot',
                'events': [{'fabula_uuid': 'event_001'}],
            }))
            (events_dir / 'ep02.yaml').write_text(yaml.dump({
                'episode_title': 'Episode 2',
                'events': [{'fabula_uuid': 'event_002'}],
            }))
            result = self.cmd.load_events(events_dir)
            self.assertEqual(len(result), 2)

    def test_load_events_nonexistent_dir(self):
        with self.assertRaises(CommandError):
            self.cmd.load_events(Path('/nonexistent/events'))

    def test_load_events_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.cmd.load_events(Path(tmpdir))
            self.assertEqual(result, [])


# =============================================================================
# IMPORT THEMES/ARCS/LOCATIONS TESTS
# =============================================================================

class ImportThemesTest(TestCase):
    """Tests for import_themes method."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False
        self.cmd.dry_run = False

    def test_import_creates_new_theme(self):
        themes_data = [
            {
                'fabula_uuid': 'theme_test_001',
                'name': 'Power',
                'description': 'The nature of power',
                'global_id': 'ger_theme_001',
            },
        ]
        self.cmd.import_themes(themes_data)
        self.assertEqual(Theme.objects.filter(fabula_uuid='theme_test_001').count(), 1)
        theme = Theme.objects.get(fabula_uuid='theme_test_001')
        self.assertEqual(theme.name, 'Power')
        self.assertEqual(theme.global_id, 'ger_theme_001')
        self.assertEqual(self.cmd.stats.created.get('Theme', 0), 1)

    def test_import_updates_existing_theme(self):
        Theme.objects.create(
            fabula_uuid='theme_test_002',
            name='Old Name',
            description='Old description',
        )
        themes_data = [
            {
                'fabula_uuid': 'theme_test_002',
                'name': 'New Name',
                'description': 'New description',
            },
        ]
        self.cmd.import_themes(themes_data)
        theme = Theme.objects.get(fabula_uuid='theme_test_002')
        self.assertEqual(theme.name, 'New Name')
        self.assertEqual(self.cmd.stats.updated.get('Theme', 0), 1)

    def test_import_cross_season_match(self):
        """Test that global_id lookup resolves cross-season matches."""
        existing = Theme.objects.create(
            fabula_uuid='theme_old_uuid',
            name='Season 1 Theme',
            description='From season 1',
            global_id='ger_theme_cross_001',
        )
        self.cmd.themes_by_global_id = {'ger_theme_cross_001': existing}

        themes_data = [
            {
                'fabula_uuid': 'theme_new_uuid',
                'name': 'Season 2 Theme (same entity)',
                'description': 'Updated in season 2',
                'global_id': 'ger_theme_cross_001',
            },
        ]
        self.cmd.import_themes(themes_data)
        # Should update existing, not create new
        self.assertEqual(Theme.objects.filter(global_id='ger_theme_cross_001').count(), 1)
        self.assertEqual(self.cmd.stats.cross_season_matched.get('Theme', 0), 1)

    def test_import_dry_run(self):
        self.cmd.dry_run = True
        themes_data = [
            {
                'fabula_uuid': 'theme_dry_001',
                'name': 'Dry Run Theme',
                'description': 'Should not be saved',
            },
        ]
        self.cmd.import_themes(themes_data)
        self.assertEqual(Theme.objects.filter(fabula_uuid='theme_dry_001').count(), 0)

    def test_import_truncates_long_name(self):
        themes_data = [
            {
                'fabula_uuid': 'theme_long_001',
                'name': 'x' * 300,
                'description': 'Test',
            },
        ]
        self.cmd.import_themes(themes_data)
        theme = Theme.objects.get(fabula_uuid='theme_long_001')
        self.assertLessEqual(len(theme.name), 255)

    def test_import_uses_theme_uuid_fallback(self):
        """Test that 'theme_uuid' key is used as fallback for 'fabula_uuid'."""
        themes_data = [
            {
                'theme_uuid': 'theme_fallback_001',
                'name': 'Fallback Theme',
                'description': 'Test',
            },
        ]
        self.cmd.import_themes(themes_data)
        self.assertEqual(Theme.objects.filter(fabula_uuid='theme_fallback_001').count(), 1)


class ImportArcsTest(TestCase):
    """Tests for import_arcs method."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False
        self.cmd.dry_run = False

    def test_import_creates_new_arc(self):
        arcs_data = [
            {
                'fabula_uuid': 'arc_test_001',
                'title': 'Internal Conflict',
                'description': 'A character struggles',
                'arc_type': 'INTERNAL',
            },
        ]
        self.cmd.import_arcs(arcs_data)
        self.assertEqual(ConflictArc.objects.filter(fabula_uuid='arc_test_001').count(), 1)
        arc = ConflictArc.objects.get(fabula_uuid='arc_test_001')
        self.assertEqual(arc.title, 'Internal Conflict')
        self.assertEqual(arc.arc_type, 'INTERNAL')

    def test_import_updates_existing_arc(self):
        ConflictArc.objects.create(
            fabula_uuid='arc_test_002',
            title='Old Title',
            description='Old',
        )
        arcs_data = [
            {
                'fabula_uuid': 'arc_test_002',
                'title': 'New Title',
                'description': 'New',
                'arc_type': 'SOCIETAL',
            },
        ]
        self.cmd.import_arcs(arcs_data)
        arc = ConflictArc.objects.get(fabula_uuid='arc_test_002')
        self.assertEqual(arc.title, 'New Title')


class ImportLocationsTest(TestCase):
    """Tests for import_locations method."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False
        self.cmd.dry_run = False

    def test_import_creates_new_location(self):
        locations_data = [
            {
                'fabula_uuid': 'loc_test_001',
                'canonical_name': 'Oval Office',
                'description': 'The president\'s office',
                'location_type': 'Office',
            },
        ]
        self.cmd.import_locations(locations_data)
        self.assertEqual(Location.objects.filter(fabula_uuid='loc_test_001').count(), 1)
        loc = Location.objects.get(fabula_uuid='loc_test_001')
        self.assertEqual(loc.canonical_name, 'Oval Office')
        self.assertEqual(loc.location_type, 'Office')

    def test_import_updates_existing_location(self):
        Location.objects.create(
            fabula_uuid='loc_test_002',
            canonical_name='Old Name',
            description='Old',
        )
        locations_data = [
            {
                'fabula_uuid': 'loc_test_002',
                'canonical_name': 'New Name',
                'description': 'New description',
                'location_type': 'Updated',
            },
        ]
        self.cmd.import_locations(locations_data)
        loc = Location.objects.get(fabula_uuid='loc_test_002')
        self.assertEqual(loc.canonical_name, 'New Name')


# =============================================================================
# COMMAND INTEGRATION TESTS
# =============================================================================

class ImportCommandErrorsTest(TestCase):
    """Tests for command-level error handling."""

    def test_nonexistent_directory(self):
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command('import_fabula', '/nonexistent/path', stdout=out, stderr=out)

    def test_missing_required_files(self):
        """Missing required YAML files should raise CommandError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out = StringIO()
            with self.assertRaises(CommandError):
                call_command('import_fabula', tmpdir, stdout=out, stderr=out)
