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

from narrative.management.commands.import_fabula import Command, ImportData, ImportStats
from narrative.models import (
    Theme, ConflictArc, Location,
    SeriesIndexPage, SeasonPage, EpisodePage,
    CharacterPage, CharacterIndexPage,
    OrganizationPage, OrganizationIndexPage,
    ObjectPage, ObjectIndexPage,
    EventPage, EventIndexPage,
    NarrativeConnection,
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


class CleanupScopingTest(TestCase):
    """
    Regression tests for ISS-001: ``run_cleanup`` must never touch series
    that were not part of the current import.
    """

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False
        self.cmd.dry_run = False
        # Tests run non-interactively; without this the ISS-007 confirmation
        # gate aborts every non-dry-run cleanup (covered by its own test).
        self.cmd.assume_yes = True

        root = Page.objects.get(depth=1)

        # Series A: the one we're "importing" cleanup for.
        self.series_a = SeriesIndexPage(
            title="Series A",
            slug="series-a",
            fabula_uuid="series-a-uuid",
        )
        root.add_child(instance=self.series_a)

        self.chars_a = CharacterIndexPage(title="Characters A", slug="chars-a")
        self.series_a.add_child(instance=self.chars_a)

        # Keeper: still in canonical_uuids on next import.
        self.char_keep = CharacterPage(
            title="Keeper A",
            slug="keep-a",
            canonical_name="Keeper A",
            description="<p>placeholder</p>",
            fabula_uuid="char-keep-a",
        )
        self.chars_a.add_child(instance=self.char_keep)

        # Deprecated: not in canonical_uuids -- should be deleted.
        self.char_drop = CharacterPage(
            title="Drop A",
            slug="drop-a",
            canonical_name="Drop A",
            description="<p>placeholder</p>",
            fabula_uuid="char-drop-a",
        )
        self.chars_a.add_child(instance=self.char_drop)

        # Series B: a completely separate series that must survive.
        self.series_b = SeriesIndexPage(
            title="Series B",
            slug="series-b",
            fabula_uuid="series-b-uuid",
        )
        root.add_child(instance=self.series_b)

        self.chars_b = CharacterIndexPage(title="Characters B", slug="chars-b")
        self.series_b.add_child(instance=self.chars_b)

        self.char_b = CharacterPage(
            title="Bystander B",
            slug="bystander-b",
            canonical_name="Bystander B",
            description="<p>placeholder</p>",
            fabula_uuid="char-b",
        )
        self.chars_b.add_child(instance=self.char_b)

        # Organization pages live under series_a's OrganizationIndexPage
        self.orgs_a = OrganizationIndexPage(title="Orgs A", slug="orgs-a")
        self.series_a.add_child(instance=self.orgs_a)
        self.org_keep = OrganizationPage(
            title="Org Keep A",
            slug="org-keep-a",
            canonical_name="Org Keep A",
            description="<p>x</p>",
            fabula_uuid="org-keep-a",
        )
        self.orgs_a.add_child(instance=self.org_keep)
        self.org_drop = OrganizationPage(
            title="Org Drop A",
            slug="org-drop-a",
            canonical_name="Org Drop A",
            description="<p>x</p>",
            fabula_uuid="org-drop-a",
        )
        self.orgs_a.add_child(instance=self.org_drop)

        # Season -> Episode -> Event tree under series_a
        self.season_keep = SeasonPage(
            title="Season 1 A",
            slug="s1-a",
            season_number=1,
            fabula_uuid="season-keep-a",
        )
        self.series_a.add_child(instance=self.season_keep)
        self.season_drop = SeasonPage(
            title="Season 99 A",
            slug="s99-a",
            season_number=99,
            fabula_uuid="season-drop-a",
        )
        self.series_a.add_child(instance=self.season_drop)

        self.ep_keep = EpisodePage(
            title="Episode Keep",
            slug="ep-keep-a",
            episode_number=1,
            fabula_uuid="ep-keep-a",
        )
        self.season_keep.add_child(instance=self.ep_keep)
        self.ep_drop = EpisodePage(
            title="Episode Drop",
            slug="ep-drop-a",
            episode_number=2,
            fabula_uuid="ep-drop-a",
        )
        self.season_keep.add_child(instance=self.ep_drop)

        # Events live under an EventIndexPage (not under episodes), but
        # are FK-linked to episode. For the cleanup test we only need them
        # under SOMETHING with series_a in its tree path.
        self.events_idx_a = EventIndexPage(title="Events A", slug="events-a")
        self.series_a.add_child(instance=self.events_idx_a)
        self.event_keep = EventPage(
            title="Event Keep",
            slug="event-keep-a",
            episode=self.ep_keep,
            description="<p>x</p>",
            fabula_uuid="event-keep-a",
        )
        self.events_idx_a.add_child(instance=self.event_keep)
        # Deprecated event is linked to a deprecated episode so cascade
        # deletion can happen without ProtectedError from a canonical event.
        self.event_drop = EventPage(
            title="Event Drop",
            slug="event-drop-a",
            episode=self.ep_drop,
            description="<p>x</p>",
            fabula_uuid="event-drop-a",
        )
        self.events_idx_a.add_child(instance=self.event_drop)

        self.loc_a = Location.objects.create(
            fabula_uuid="loc-keep-a",
            canonical_name="Loc Keep A",
            description="",
            series=self.series_a,
        )
        self.loc_a_drop = Location.objects.create(
            fabula_uuid="loc-drop-a",
            canonical_name="Loc Drop A",
            description="",
            series=self.series_a,
        )
        self.loc_b = Location.objects.create(
            fabula_uuid="loc-b",
            canonical_name="Loc B",
            description="",
            series=self.series_b,
        )

    def _run_cleanup_for_series_a(
        self,
        char_uuids=("char-keep-a",),
        loc_uuids=("loc-keep-a",),
        org_uuids=("org-keep-a",),
        season_uuids=("season-keep-a",),
        episode_uuids=("ep-keep-a",),
        event_uuids=("event-keep-a",),
    ):
        series_data = [{
            "fabula_uuid": "series-a-uuid",
            "title": "Series A",
            "seasons": [
                {
                    "fabula_uuid": s,
                    "episodes": [
                        {"fabula_uuid": e}
                        for e in episode_uuids
                    ] if s == "season-keep-a" else [],
                }
                for s in season_uuids
            ],
        }]
        characters_data = [{"fabula_uuid": u} for u in char_uuids]
        locations_data = [{"fabula_uuid": u} for u in loc_uuids]
        organizations_data = [{"fabula_uuid": u} for u in org_uuids]
        events_data = [{"events": [{"fabula_uuid": u} for u in event_uuids]}]
        self.cmd.run_cleanup(
            series_data=series_data,
            events_data=events_data,
            characters_data=characters_data,
            organizations_data=organizations_data,
            locations_data=locations_data,
        )

    def test_cleanup_preserves_other_series_characters(self):
        """ISS-001 regression: a Series A import must NEVER delete Series B characters."""
        self._run_cleanup_for_series_a()
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_b.pk).exists())

    def test_cleanup_deletes_deprecated_in_imported_series(self):
        """Deprecated characters within the imported series ARE pruned."""
        self._run_cleanup_for_series_a()
        self.assertFalse(CharacterPage.objects.filter(pk=self.char_drop.pk).exists())
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_keep.pk).exists())

    def test_cleanup_preserves_other_series_locations(self):
        """ISS-001 regression: locations on a different series must survive."""
        self._run_cleanup_for_series_a()
        self.assertTrue(Location.objects.filter(pk=self.loc_b.pk).exists())

    def test_cleanup_deletes_deprecated_locations_in_scope(self):
        """Deprecated locations within the imported series ARE pruned."""
        self._run_cleanup_for_series_a()
        self.assertFalse(Location.objects.filter(pk=self.loc_a_drop.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.loc_a.pk).exists())

    def test_cleanup_dry_run_deletes_nothing(self):
        """T-001: --cleanup --dry-run must build the plan but not delete anything."""
        self.cmd.dry_run = True
        self._run_cleanup_for_series_a()
        # All in-scope deprecated rows must survive a dry-run cleanup.
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_drop.pk).exists())
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_keep.pk).exists())
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_b.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.loc_a_drop.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.loc_a.pk).exists())
        # And the summary block was printed.
        self.assertIn("Planned deletions", self.cmd.stdout.getvalue())
        self.assertIn("[DRY RUN]", self.cmd.stdout.getvalue())

    def test_build_cleanup_plan_is_read_only(self):
        """T-001: build_cleanup_plan is a pure read — no rows are deleted."""
        before = {
            'chars_a_drop': CharacterPage.objects.filter(pk=self.char_drop.pk).exists(),
            'chars_a_keep': CharacterPage.objects.filter(pk=self.char_keep.pk).exists(),
            'chars_b': CharacterPage.objects.filter(pk=self.char_b.pk).exists(),
            'loc_a_drop': Location.objects.filter(pk=self.loc_a_drop.pk).exists(),
            'loc_a': Location.objects.filter(pk=self.loc_a.pk).exists(),
            'loc_b': Location.objects.filter(pk=self.loc_b.pk).exists(),
        }
        plan = self.cmd.build_cleanup_plan(
            series_data=[{
                "fabula_uuid": "series-a-uuid",
                "title": "Series A",
                "seasons": [],
            }],
            events_data=[],
            characters_data=[{"fabula_uuid": "char-keep-a"}],
            organizations_data=[],
            locations_data=[{"fabula_uuid": "loc-keep-a"}],
        )
        # Structural sanity on the plan itself.
        self.assertIsNotNone(plan)
        labels = {e['label'] for e in plan['entries']}
        self.assertEqual(
            labels,
            {'events', 'episodes', 'seasons', 'characters', 'organizations', 'locations'},
        )
        # Content sanity: characters entry contains char_drop and NOT char_keep / char_b.
        chars_entry = next(e for e in plan['entries'] if e['label'] == 'characters')
        self.assertEqual(
            {o.pk for o in chars_entry['deprecated']},
            {self.char_drop.pk},
        )
        # And the Series B character must not appear in ANY entry.
        all_deprecated_pks = {
            o.pk
            for e in plan['entries']
            for o in e['deprecated']
        }
        self.assertNotIn(self.char_b.pk, all_deprecated_pks)
        self.assertNotIn(self.loc_b.pk, all_deprecated_pks)
        # Pure-read: every row still exists.
        for key, value in before.items():
            self.assertEqual(
                value,
                {
                    'chars_a_drop': CharacterPage.objects.filter(pk=self.char_drop.pk).exists(),
                    'chars_a_keep': CharacterPage.objects.filter(pk=self.char_keep.pk).exists(),
                    'chars_b': CharacterPage.objects.filter(pk=self.char_b.pk).exists(),
                    'loc_a_drop': Location.objects.filter(pk=self.loc_a_drop.pk).exists(),
                    'loc_a': Location.objects.filter(pk=self.loc_a.pk).exists(),
                    'loc_b': Location.objects.filter(pk=self.loc_b.pk).exists(),
                }[key],
                f"build_cleanup_plan mutated row '{key}'",
            )

    def test_cleanup_plan_totals_match_actual_deletions(self):
        """T-001: per-model 'deprecated' counts in the plan must equal the
        number of rows actually deleted when --cleanup runs."""
        char_qs_before = CharacterPage.objects.count()
        loc_qs_before = Location.objects.count()
        plan = self.cmd.build_cleanup_plan(
            series_data=[{
                "fabula_uuid": "series-a-uuid",
                "title": "Series A",
                "seasons": [],
            }],
            events_data=[],
            characters_data=[{"fabula_uuid": "char-keep-a"}],
            organizations_data=[],
            locations_data=[{"fabula_uuid": "loc-keep-a"}],
        )
        planned = {e['label']: len(e['deprecated']) for e in plan['entries']}

        self._run_cleanup_for_series_a()

        char_deleted = char_qs_before - CharacterPage.objects.count()
        loc_deleted = loc_qs_before - Location.objects.count()
        self.assertEqual(planned['characters'], char_deleted)
        self.assertEqual(planned['locations'], loc_deleted)

    def test_cleanup_deletes_deprecated_across_all_six_entry_types(self):
        """T-001: plan totals must equal actual deletions for ALL six entry types."""
        counts_before = {
            'events': EventPage.objects.count(),
            'episodes': EpisodePage.objects.count(),
            'seasons': SeasonPage.objects.count(),
            'characters': CharacterPage.objects.count(),
            'organizations': OrganizationPage.objects.count(),
            'locations': Location.objects.count(),
        }
        # Pre-flight: build the plan and capture its per-entry deprecated counts.
        plan = self.cmd.build_cleanup_plan(
            series_data=[{
                "fabula_uuid": "series-a-uuid",
                "title": "Series A",
                "seasons": [{
                    "fabula_uuid": "season-keep-a",
                    "episodes": [{"fabula_uuid": "ep-keep-a"}],
                }],
            }],
            events_data=[{"events": [{"fabula_uuid": "event-keep-a"}]}],
            characters_data=[{"fabula_uuid": "char-keep-a"}],
            organizations_data=[{"fabula_uuid": "org-keep-a"}],
            locations_data=[{"fabula_uuid": "loc-keep-a"}],
        )
        planned = {e['label']: len(e['deprecated']) for e in plan['entries']}

        # Each entry type should have exactly one deprecated row in the fixture.
        for label in ('events', 'episodes', 'seasons', 'characters', 'organizations', 'locations'):
            self.assertEqual(planned[label], 1, f"expected 1 deprecated {label}")

        self._run_cleanup_for_series_a()

        counts_after = {
            'events': EventPage.objects.count(),
            'episodes': EpisodePage.objects.count(),
            'seasons': SeasonPage.objects.count(),
            'characters': CharacterPage.objects.count(),
            'organizations': OrganizationPage.objects.count(),
            'locations': Location.objects.count(),
        }
        for label in counts_before:
            self.assertEqual(
                planned[label],
                counts_before[label] - counts_after[label],
                f"planned[{label}] != actual deletions",
            )

    def test_cleanup_empty_plan_when_all_canonical(self):
        """T-001: if the import covers every in-scope row, the plan has zero
        deprecated entries and run_cleanup deletes nothing."""
        plan = self.cmd.build_cleanup_plan(
            series_data=[{
                "fabula_uuid": "series-a-uuid",
                "title": "Series A",
                "seasons": [{
                    "fabula_uuid": "season-keep-a",
                    "episodes": [
                        {"fabula_uuid": "ep-keep-a"},
                        {"fabula_uuid": "ep-drop-a"},
                    ],
                }, {
                    "fabula_uuid": "season-drop-a",
                    "episodes": [],
                }],
            }],
            events_data=[{"events": [
                {"fabula_uuid": "event-keep-a"},
                {"fabula_uuid": "event-drop-a"},
            ]}],
            characters_data=[
                {"fabula_uuid": "char-keep-a"},
                {"fabula_uuid": "char-drop-a"},
            ],
            organizations_data=[
                {"fabula_uuid": "org-keep-a"},
                {"fabula_uuid": "org-drop-a"},
            ],
            locations_data=[
                {"fabula_uuid": "loc-keep-a"},
                {"fabula_uuid": "loc-drop-a"},
            ],
        )
        # Every entry should report zero deprecated rows.
        for entry in plan['entries']:
            self.assertEqual(
                len(entry['deprecated']), 0,
                f"{entry['label']}: expected empty deprecated, got {entry['deprecated']}",
            )

        before = CharacterPage.objects.count() + EventPage.objects.count()
        # Run the same canonical-covers-everything call as a full cleanup.
        self._run_cleanup_for_series_a(
            char_uuids=("char-keep-a", "char-drop-a"),
            loc_uuids=("loc-keep-a", "loc-drop-a"),
            org_uuids=("org-keep-a", "org-drop-a"),
            season_uuids=("season-keep-a", "season-drop-a"),
            episode_uuids=("ep-keep-a", "ep-drop-a"),
            event_uuids=("event-keep-a", "event-drop-a"),
        )
        # Nothing changed.
        self.assertEqual(
            before,
            CharacterPage.objects.count() + EventPage.objects.count(),
        )

    def test_cleanup_handles_multiple_imported_series(self):
        """T-001: run_cleanup must accept a list of series and scope deletion
        to all of them, while still preserving any series NOT in the list."""
        # Promote series_b to "imported" — give it a stale character so we
        # can prove the multi-series path actually deletes B's stale rows
        # too, not just A's.
        chars_b_drop = CharacterPage(
            title="Drop B",
            slug="drop-b",
            canonical_name="Drop B",
            description="<p>placeholder</p>",
            fabula_uuid="char-drop-b",
        )
        self.chars_b.add_child(instance=chars_b_drop)

        # And a third series that must survive the cleanup untouched.
        root = Page.objects.get(depth=1)
        series_c = SeriesIndexPage(
            title="Series C",
            slug="series-c",
            fabula_uuid="series-c-uuid",
        )
        root.add_child(instance=series_c)
        chars_c = CharacterIndexPage(title="Characters C", slug="chars-c")
        series_c.add_child(instance=chars_c)
        char_c = CharacterPage(
            title="Bystander C",
            slug="bystander-c",
            canonical_name="Bystander C",
            description="<p>placeholder</p>",
            fabula_uuid="char-c",
        )
        chars_c.add_child(instance=char_c)

        self.cmd.run_cleanup(
            series_data=[
                {"fabula_uuid": "series-a-uuid", "title": "A", "seasons": []},
                {"fabula_uuid": "series-b-uuid", "title": "B", "seasons": []},
            ],
            events_data=[],
            characters_data=[
                {"fabula_uuid": "char-keep-a"},
                {"fabula_uuid": "char-b"},
            ],
            organizations_data=[],
            locations_data=[
                {"fabula_uuid": "loc-keep-a"},
                {"fabula_uuid": "loc-b"},
            ],
        )

        # Series A: deprecated char dropped, keeper survives.
        self.assertFalse(CharacterPage.objects.filter(pk=self.char_drop.pk).exists())
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_keep.pk).exists())
        # Series B: deprecated char dropped, keeper survives.
        self.assertFalse(CharacterPage.objects.filter(pk=chars_b_drop.pk).exists())
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_b.pk).exists())
        # Series C: completely untouched.
        self.assertTrue(CharacterPage.objects.filter(pk=char_c.pk).exists())

    def test_cleanup_preflight_catches_protect_conflict(self):
        """T-001 F1+F2, upgraded by ISS-005: a canonical event PROTECTing a
        deprecated episode used to raise ProtectedError mid-transaction (and
        rely on rollback). The blocker preflight now aborts BEFORE any
        delete — same guarantee (nothing half-deleted), no exception.
        """
        event_second = EventPage(
            title="Event Second",
            slug="event-second-a",
            episode=self.ep_drop,
            description="<p>x</p>",
            fabula_uuid="event-second-a",
        )
        self.events_idx_a.add_child(instance=event_second)

        events_before = set(EventPage.objects.values_list('pk', flat=True))
        chars_before = set(CharacterPage.objects.values_list('pk', flat=True))
        locs_before = set(Location.objects.values_list('pk', flat=True))

        self.cmd.run_cleanup(
            series_data=[{
                "fabula_uuid": "series-a-uuid",
                "title": "Series A",
                "seasons": [{
                    "fabula_uuid": "season-keep-a",
                    "episodes": [{"fabula_uuid": "ep-keep-a"}],
                }],
            }],
            # event_drop is NOT canonical; event-second-a IS canonical and
            # PROTECTs ep_drop — the preflight must refuse to start.
            events_data=[{"events": [
                {"fabula_uuid": "event-keep-a"},
                {"fabula_uuid": "event-second-a"},
            ]}],
            characters_data=[{"fabula_uuid": "char-keep-a"}],
            organizations_data=[{"fabula_uuid": "org-keep-a"}],
            locations_data=[{"fabula_uuid": "loc-keep-a"}],
        )

        self.assertIn("Cleanup aborted", self.cmd.stdout.getvalue())
        # Nothing at all was deleted — including entries BEFORE episodes.
        self.assertEqual(
            events_before,
            set(EventPage.objects.values_list('pk', flat=True)),
            "blocker preflight must abort before any deletion",
        )
        self.assertEqual(
            chars_before,
            set(CharacterPage.objects.values_list('pk', flat=True)),
        )
        self.assertEqual(
            locs_before,
            set(Location.objects.values_list('pk', flat=True)),
        )

    def test_cleanup_rolls_back_on_failure(self):
        """T-001 / F1+F2: an unexpected mid-delete failure must roll back the
        whole cleanup phase, including deletes from PRIOR entries. (The
        PROTECT case is now caught up-front — see the preflight test — so
        this injects a failure to exercise the transaction guarantee.)
        """
        events_before = set(EventPage.objects.values_list('pk', flat=True))
        chars_before = set(CharacterPage.objects.values_list('pk', flat=True))

        original = self.cmd._delete_cleanup_entry
        calls = {'n': 0}

        def failing_entry(entry):
            calls['n'] += 1
            if calls['n'] >= 3:  # let events + episodes delete, then blow up
                raise RuntimeError("injected mid-cleanup failure")
            return original(entry)

        self.cmd._delete_cleanup_entry = failing_entry
        try:
            with self.assertRaises(RuntimeError):
                self.cmd.run_cleanup(
                    series_data=[{
                        "fabula_uuid": "series-a-uuid",
                        "title": "Series A",
                        "seasons": [{
                            "fabula_uuid": "season-keep-a",
                            "episodes": [{"fabula_uuid": "ep-keep-a"}],
                        }],
                    }],
                    events_data=[{"events": [{"fabula_uuid": "event-keep-a"}]}],
                    characters_data=[{"fabula_uuid": "char-keep-a"}],
                    organizations_data=[{"fabula_uuid": "org-keep-a"}],
                    locations_data=[{"fabula_uuid": "loc-keep-a"}],
                )
        finally:
            self.cmd._delete_cleanup_entry = original

        # The events entry ran (and deleted event_drop) before the injected
        # failure; rollback must have restored it.
        self.assertEqual(
            events_before,
            set(EventPage.objects.values_list('pk', flat=True)),
            "transaction.atomic should have rolled back the prior event delete",
        )
        self.assertEqual(
            chars_before,
            set(CharacterPage.objects.values_list('pk', flat=True)),
        )

    def test_cleanup_aborts_when_series_unresolvable(self):
        """
        If the imported series_data doesn't match any SeriesIndexPage record,
        run_cleanup MUST refuse to delete anything (the old behaviour treated
        this as 'wipe everything').
        """
        bogus_series = [{"fabula_uuid": "no-such-series", "title": "Ghost"}]
        self.cmd.run_cleanup(
            series_data=bogus_series,
            events_data=[],
            characters_data=[],
            organizations_data=[],
            locations_data=[],
        )
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_b.pk).exists())
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_keep.pk).exists())
        self.assertTrue(CharacterPage.objects.filter(pk=self.char_drop.pk).exists())
        self.assertTrue(Location.objects.filter(pk=self.loc_b.pk).exists())


class CleanupSafetyGatesTest(TestCase):
    """ISS-005 (PROTECT-FK preflight) and ISS-007 (confirmation gate)."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False
        self.cmd.dry_run = False
        self.cmd.assume_yes = True

        root = Page.objects.get(depth=1)
        self.series = SeriesIndexPage(
            title="Series G", slug="series-g", fabula_uuid="series-g-uuid",
        )
        root.add_child(instance=self.series)
        self.season = SeasonPage(
            title="S1", slug="s1-g", season_number=1, fabula_uuid="season-g",
        )
        self.series.add_child(instance=self.season)
        self.ep_keep = EpisodePage(
            title="Ep Keep", slug="ep-keep-g", episode_number=1,
            fabula_uuid="ep-keep-g",
        )
        self.season.add_child(instance=self.ep_keep)
        # This episode will be deprecated but a CANONICAL event points at it.
        self.ep_drop = EpisodePage(
            title="Ep Drop", slug="ep-drop-g", episode_number=2,
            fabula_uuid="ep-drop-g",
        )
        self.season.add_child(instance=self.ep_drop)
        self.events_idx = EventIndexPage(title="Events G", slug="events-g")
        self.series.add_child(instance=self.events_idx)
        self.event_keep = EventPage(
            title="Event Keep", slug="event-keep-g", episode=self.ep_drop,
            description="<p>x</p>", fabula_uuid="event-keep-g",
        )
        self.events_idx.add_child(instance=self.event_keep)

    def _cleanup_kwargs(self):
        return dict(
            series_data=[{
                "fabula_uuid": "series-g-uuid",
                "title": "Series G",
                "seasons": [{
                    "fabula_uuid": "season-g",
                    "episodes": [{"fabula_uuid": "ep-keep-g"}],
                }],
            }],
            events_data=[{"events": [{"fabula_uuid": "event-keep-g"}]}],
            characters_data=[],
            organizations_data=[],
            locations_data=[],
        )

    def test_blocker_preflight_aborts_before_deleting(self):
        """ISS-005: a canonical event referencing a deprecated episode must
        abort the cleanup up-front — nothing at all is deleted."""
        self.cmd.run_cleanup(**self._cleanup_kwargs())
        out = self.cmd.stdout.getvalue()
        self.assertIn("Cleanup aborted", out)
        self.assertIn("canonical event", out)
        # The deprecated episode AND the canonical event both survive.
        self.assertTrue(EpisodePage.objects.filter(pk=self.ep_drop.pk).exists())
        self.assertTrue(EventPage.objects.filter(pk=self.event_keep.pk).exists())

    def test_plan_reports_blockers(self):
        plan = self.cmd.build_cleanup_plan(**self._cleanup_kwargs())
        self.assertEqual([b.pk for b in plan['blockers']], [self.event_keep.pk])

    def test_confirmation_gate_aborts_non_interactive_runs(self):
        """ISS-007: without --yes, a non-interactive cleanup must refuse."""
        # Re-point the event at the kept episode so no blockers fire and the
        # confirmation gate is what aborts.
        self.event_keep.episode = self.ep_keep
        self.event_keep.save()
        self.cmd.assume_yes = False
        self.cmd.run_cleanup(**self._cleanup_kwargs())
        out = self.cmd.stdout.getvalue()
        self.assertIn("Pass --yes to proceed", out)
        # The deprecated episode survives the refused cleanup.
        self.assertTrue(EpisodePage.objects.filter(pk=self.ep_drop.pk).exists())


class DeleteSeriesCommandTest(TestCase):
    """ISS-002: two-stage series-tree deletion via the delete_series command."""

    def setUp(self):
        root = Page.objects.get(depth=1)
        # Two-season series with events — the exact shape series.delete()
        # used to choke on (PROTECT FK from EventPage.episode).
        self.series = SeriesIndexPage(
            title="Doomed", slug="doomed", fabula_uuid="series-doomed",
        )
        root.add_child(instance=self.series)
        self.events_idx = EventIndexPage(title="Events", slug="events-doomed")
        self.series.add_child(instance=self.events_idx)
        for s in (1, 2):
            season = SeasonPage(
                title=f"S{s}", slug=f"s{s}-doomed", season_number=s,
                fabula_uuid=f"season-doomed-{s}",
            )
            self.series.add_child(instance=season)
            episode = EpisodePage(
                title=f"S{s}E1", slug=f"s{s}e1-doomed", episode_number=1,
                season_number=s, fabula_uuid=f"ep-doomed-{s}",
            )
            season.add_child(instance=episode)
            event = EventPage(
                title=f"Event S{s}", slug=f"event-s{s}-doomed",
                episode=episode, description="<p>x</p>",
                fabula_uuid=f"event-doomed-{s}",
            )
            self.events_idx.add_child(instance=event)
        events = list(EventPage.objects.descendant_of(self.series))
        self.connection = NarrativeConnection.objects.create(
            from_event=events[0], to_event=events[1],
            connection_type="CAUSAL", strength="strong",
            description="doomed connection", fabula_uuid="conn-doomed",
        )
        Location.objects.create(
            fabula_uuid="loc-doomed", canonical_name="Doomed Manor",
            description="", series=self.series,
        )

        # A bystander series that must survive.
        self.other = SeriesIndexPage(
            title="Survivor", slug="survivor", fabula_uuid="series-survivor",
        )
        root.add_child(instance=self.other)

    def test_dry_run_deletes_nothing(self):
        out = StringIO()
        call_command('delete_series', 'doomed', '--dry-run', stdout=out)
        self.assertIn("[DRY RUN]", out.getvalue())
        self.assertTrue(SeriesIndexPage.objects.filter(slug='doomed').exists())
        self.assertEqual(EventPage.objects.descendant_of(self.series).count(), 2)

    def test_two_stage_delete_removes_whole_tree(self):
        out = StringIO()
        call_command('delete_series', 'doomed', '--yes', stdout=out)
        self.assertFalse(SeriesIndexPage.objects.filter(slug='doomed').exists())
        self.assertEqual(EventPage.objects.count(), 0)
        self.assertEqual(EpisodePage.objects.count(), 0)
        self.assertEqual(SeasonPage.objects.count(), 0)
        self.assertFalse(NarrativeConnection.objects.filter(pk=self.connection.pk).exists())
        self.assertFalse(Location.objects.filter(fabula_uuid="loc-doomed").exists())
        # Bystander series untouched.
        self.assertTrue(SeriesIndexPage.objects.filter(slug='survivor').exists())

    def test_lookup_by_fabula_uuid(self):
        out = StringIO()
        call_command('delete_series', 'series-doomed', '--yes', stdout=out)
        self.assertFalse(SeriesIndexPage.objects.filter(slug='doomed').exists())

    def test_unknown_identifier_errors(self):
        with self.assertRaises(CommandError):
            call_command('delete_series', 'no-such-series', '--yes')

    def test_non_interactive_without_yes_refuses(self):
        with self.assertRaises(CommandError):
            call_command('delete_series', 'doomed')
        self.assertTrue(SeriesIndexPage.objects.filter(slug='doomed').exists())


class ContractVersionGateTest(TestCase):
    """T-019: manifest version gate + v2.4.0 shape validation."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False

    # --- parse_contract_version ---

    def test_missing_manifest_refused(self):
        with self.assertRaises(CommandError):
            self.cmd.parse_contract_version(None)

    def test_missing_version_refused(self):
        with self.assertRaises(CommandError):
            self.cmd.parse_contract_version({'export_date': 'x'})

    def test_unparseable_version_refused(self):
        with self.assertRaises(CommandError):
            self.cmd.parse_contract_version({'fabula_version': 'banana'})

    def test_newer_contract_refused(self):
        with self.assertRaises(CommandError):
            self.cmd.parse_contract_version({'fabula_version': '3.0.0'})

    def test_legacy_version_parses(self):
        self.assertEqual(
            self.cmd.parse_contract_version({'fabula_version': '2.3.0'}),
            (2, 3, 0),
        )

    def test_v24_parses(self):
        self.assertEqual(
            self.cmd.parse_contract_version({'fabula_version': '2.4.0'}),
            (2, 4, 0),
        )

    # --- validate_v24_shapes ---

    def _v24_data(self, **overrides):
        ep1 = {'uuid': 'ep_1', 'season': 1, 'number': 5, 'ordinal': 105}
        ep2 = {'uuid': 'ep_2', 'season': 2, 'number': 1, 'ordinal': 201}
        base = dict(
            manifest={'fabula_version': '2.4.0'},
            series=[],
            themes=[{
                'fabula_uuid': 'theme_1', 'name': 'Power',
                'series_uuid': 'ser_1',
                'events': [{'event_uuid': 'evt_1', 'episode': ep1}],
            }],
            arcs=[{
                'fabula_uuid': 'arc_1', 'name': 'The rise',
                'arc_type': 'SOCIETAL', 'description': 'x',
                'series_uuid': 'ser_1',
                'events': [
                    {'event_uuid': 'evt_1', 'role': 'START', 'episode': ep1},
                    {'event_uuid': 'evt_2', 'role': None, 'episode': ep2},
                ],
            }],
            locations=[], characters=[], organizations=[], objects=[],
            writers=[],
            connections=[
                {
                    'fabula_uuid': 'conn_1', 'global_id': None,
                    'from_event_uuid': 'evt_1', 'to_event_uuid': 'evt_2',
                    'connection_type': 'FORESHADOWING', 'strength': 'medium',
                    'description': 'x', 'layer': 'event',
                    'scope': 'cross_episode',
                    'inferred_by': 'llm_cross_episode_arc',
                    'cross_episode_reasoning': 'y',
                    'from_episode': ep1, 'to_episode': ep2,
                },
                {
                    'fabula_uuid': 'conn_2', 'global_id': 'ger_narrativeconnection_2',
                    'from_event_uuid': 'evt_1', 'to_event_uuid': 'evt_3',
                    'connection_type': 'CAUSAL', 'strength': 'strong',
                    'description': 'x', 'layer': 'beat',
                    'scope': 'intra_episode',
                    'from_episode': ep1, 'to_episode': ep1,
                },
            ],
            events=[],
            character_episode_profiles=[], season_profiles=[],
        )
        base.update(overrides)
        return ImportData(**base)

    def test_valid_v24_shapes_pass(self):
        self.assertEqual(self.cmd.validate_v24_shapes(self._v24_data()), [])

    def test_bad_layer_rejected(self):
        data = self._v24_data()
        data.connections[0]['layer'] = 'plasma'
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('layer' in e for e in errors))

    def test_backwards_event_edge_rejected(self):
        data = self._v24_data()
        data.connections[0]['from_episode'], data.connections[0]['to_episode'] = (
            data.connections[0]['to_episode'], data.connections[0]['from_episode']
        )
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('backwards' in e for e in errors))

    def test_beat_row_requires_global_id(self):
        data = self._v24_data()
        data.connections[1]['global_id'] = None
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('global_id' in e for e in errors))

    def test_arc_missing_series_uuid_rejected(self):
        data = self._v24_data()
        del data.arcs[0]['series_uuid']
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('series_uuid' in e for e in errors))

    def test_theme_missing_name_rejected(self):
        data = self._v24_data()
        del data.themes[0]['name']
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('themes[0]' in e and 'missing name' in e for e in errors))

    def test_theme_missing_series_uuid_rejected(self):
        data = self._v24_data()
        del data.themes[0]['series_uuid']
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('themes[0]' in e and 'series_uuid' in e for e in errors))

    def test_theme_member_missing_event_uuid_rejected(self):
        data = self._v24_data()
        del data.themes[0]['events'][0]['event_uuid']
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('themes[0]' in e and 'events[0]' in e and 'event_uuid' in e for e in errors))

    def test_theme_member_bad_episode_block_rejected(self):
        data = self._v24_data()
        data.themes[0]['events'][0]['episode'] = 'not-a-dict'
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('themes[0]' in e and 'events[0]' in e and 'episode block' in e for e in errors))

    def test_nondict_episode_block_does_not_crash_ordinal_check(self):
        # Review finding: a truthy non-dict episode block must produce an
        # error, not an AttributeError from the backwards-edge comparison.
        data = self._v24_data()
        data.connections[0]['from_episode'] = 'ep-as-string'
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('from_episode' in e for e in errors))

    def test_load_import_data_dedupe_wiring(self):
        # Review finding: assert the LOAD_SPECS dedupe flags reach the right
        # entities — characters (dedupe=True) collapse, connections
        # (dedupe=False) don't.
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / 'events').mkdir()
            dup_char = {'fabula_uuid': 'char_1', 'global_id': 'ger_char_1', 'canonical_name': 'Jane'}
            files = {
                'manifest.yaml': {'fabula_version': '2.3.0'},
                'series.yaml': [],
                'themes.yaml': [],
                'arcs.yaml': [],
                'locations.yaml': [],
                'characters.yaml': [dup_char, dict(dup_char)],
                'connections.yaml': [
                    {'fabula_uuid': 'c1', 'global_id': 'g1', 'from_event_uuid': 'a', 'to_event_uuid': 'b'},
                    {'fabula_uuid': 'c2', 'global_id': 'g2', 'from_event_uuid': 'a', 'to_event_uuid': 'b'},
                ],
            }
            for name, content in files.items():
                with open(d / name, 'w') as fh:
                    yaml.dump(content, fh)
            data = self.cmd.load_import_data(d)
        self.assertEqual(len(data.characters), 1)   # deduped
        self.assertEqual(len(data.connections), 2)  # NOT deduped
        self.assertEqual(data.organizations, [])    # optional missing -> []

    def test_bad_scope_rejected(self):
        data = self._v24_data()
        data.connections[0]['scope'] = 'interdimensional'
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('bad scope' in e for e in errors))

    def test_missing_endpoint_uuid_rejected(self):
        data = self._v24_data()
        data.connections[0]['to_event_uuid'] = None
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('missing endpoint' in e for e in errors))

    def test_event_row_missing_fabula_uuid_rejected(self):
        data = self._v24_data()
        data.connections[0]['fabula_uuid'] = None
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('missing fabula_uuid' in e for e in errors))

    def test_episode_block_missing_keys_rejected(self):
        for key in ('uuid', 'season', 'number', 'ordinal'):
            data = self._v24_data()
            block = dict(data.connections[0]['from_episode'])
            block[key] = None
            data.connections[0]['from_episode'] = block
            errors = self.cmd.validate_v24_shapes(data)
            self.assertTrue(
                any(f"episode block missing '{key}'" in e for e in errors),
                f"no error for missing episode key {key}",
            )

    def test_legacy_arc_type_accepted(self):
        # Pre-v1.2.0 graphs carry UNKNOWN / ENVIRONMENTAL / TECHNOLOGICAL;
        # they pass through verbatim (plan verification note 2).
        data = self._v24_data()
        data.arcs[0]['arc_type'] = 'UNKNOWN'
        self.assertEqual(self.cmd.validate_v24_shapes(data), [])

    def test_garbage_arc_type_rejected(self):
        data = self._v24_data()
        data.arcs[0]['arc_type'] = 'SPICY'
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('arc_type' in e for e in errors))

    def test_unknown_connection_type_rejected(self):
        data = self._v24_data()
        data.connections[0]['connection_type'] = 'VIBES'
        errors = self.cmd.validate_v24_shapes(data)
        self.assertTrue(any('connection_type' in e for e in errors))

    # --- end-to-end gate through handle() ---

    def _write_v24_export(self, tmpdir):
        """Minimal on-disk v2.4.0 export: valid shapes, no events."""
        d = Path(tmpdir)
        (d / 'events').mkdir()
        files = {
            'manifest.yaml': {'fabula_version': '2.4.0', 'export_date': 'x'},
            'series.yaml': [{'fabula_uuid': 'ser_1', 'title': 'Gate Test', 'seasons': []}],
            'themes.yaml': [],
            'arcs.yaml': [],
            'locations.yaml': [],
            'characters.yaml': [],
            'connections.yaml': [],
        }
        for name, content in files.items():
            with open(d / name, 'w') as fh:
                yaml.dump(content, fh)

    def test_v24_dry_run_validates_and_stops(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_v24_export(tmpdir)
            out = StringIO()
            call_command('import_fabula', tmpdir, '--dry-run', stdout=out)
            self.assertIn('v2.4.0 shapes validated', out.getvalue())
            self.assertIn('nothing imported', out.getvalue())
        self.assertFalse(
            SeriesIndexPage.objects.filter(fabula_uuid='ser_1').exists())

    def test_v24_real_import_succeeds(self):
        # T-028: the real v2.4.0 import path now runs (empty scope, so no
        # confirmation gate fires).
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_v24_export(tmpdir)
            out = StringIO()
            call_command('import_fabula', tmpdir, stdout=out)
        self.assertTrue(
            SeriesIndexPage.objects.filter(fabula_uuid='ser_1').exists())

    def test_real_import_clears_page_cache(self):
        # T-030: detail views are cache_page'd on the premise that data
        # only changes on import — a completed import must clear the cache.
        from django.core.cache import cache
        cache.set('sentinel', 'stale')
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_v24_export(tmpdir)
            call_command('import_fabula', tmpdir, stdout=StringIO())
        self.assertIsNone(cache.get('sentinel'))

    def test_dry_run_keeps_page_cache(self):
        from django.core.cache import cache
        cache.set('sentinel', 'kept')
        with tempfile.TemporaryDirectory() as tmpdir:
            self._write_v24_export(tmpdir)
            call_command('import_fabula', tmpdir, '--dry-run', stdout=StringIO())
        self.assertEqual(cache.get('sentinel'), 'kept')


class ConnectionPurgeScopingTest(TestCase):
    """T-028 spec point (2)+(5): the v2.4.0 purge is scoped to the imported
    series — a sibling series' connections must survive (the ISS-001
    failure class, connections edition)."""

    def setUp(self):
        self.cmd = Command()
        self.cmd.stdout = StringIO()
        self.cmd.stderr = StringIO()
        self.cmd.verbose = False
        self.cmd.dry_run = False
        self.cmd.stats = ImportStats()
        self.cmd.events_cache = {}
        self.cmd.episodes_cache = {}

        root = Page.objects.get(depth=1)
        self.pages = {}
        for slug in ('alpha', 'beta'):
            series = SeriesIndexPage(
                title=f"Series {slug}", slug=f"series-{slug}",
                fabula_uuid=f"ser_{slug}",
            )
            root.add_child(instance=series)
            idx = EventIndexPage(title=f"Events {slug}", slug=f"events-{slug}")
            series.add_child(instance=idx)
            season = SeasonPage(title='S1', slug=f's1-{slug}', season_number=1,
                                fabula_uuid=f'season_{slug}')
            series.add_child(instance=season)
            episode = EpisodePage(title='E1', slug=f'e1-{slug}',
                                  episode_number=1, season_number=1,
                                  fabula_uuid=f'ep_{slug}')
            season.add_child(instance=episode)
            events = []
            for n in (1, 2):
                ev = EventPage(
                    title=f'Event {slug} {n}', slug=f'event-{slug}-{n}',
                    episode=episode, description='<p>x</p>',
                    fabula_uuid=f'evt_{slug}_{n}',
                )
                idx.add_child(instance=ev)
                events.append(ev)
                self.cmd.events_cache[ev.fabula_uuid] = ev
            self.cmd.episodes_cache[episode.fabula_uuid] = episode
            self.pages[slug] = {'series': series, 'events': events,
                                'episode': episode}
            NarrativeConnection.objects.create(
                from_event=events[0], to_event=events[1],
                connection_type='CAUSAL', strength='strong',
                description=f'legacy {slug}',
                fabula_uuid=f'conn_legacy_{slug}',
                global_id=f'ger_narrativeconnection_{slug}',
            )

    def _v24_rows(self, slug):
        ep = {'uuid': f'ep_{slug}', 'season': 1, 'number': 1, 'ordinal': 101}
        return [
            {   # event-layer row
                'fabula_uuid': f'conn_new_{slug}', 'global_id': None,
                'from_event_uuid': f'evt_{slug}_1',
                'to_event_uuid': f'evt_{slug}_2',
                'connection_type': 'FORESHADOWING', 'strength': 'medium',
                'description': 'new event row', 'layer': 'event',
                'scope': 'intra_episode', 'inferred_by': 'llm_cross_episode_arc',
                'cross_episode_reasoning': None,
                'from_episode': ep, 'to_episode': ep,
            },
            {   # beat-layer row matching the legacy triple — keeps identity
                'fabula_uuid': f'conn_legacy_{slug}',
                'global_id': f'ger_narrativeconnection_{slug}',
                'from_event_uuid': f'evt_{slug}_1',
                'to_event_uuid': f'evt_{slug}_2',
                'connection_type': 'CAUSAL', 'strength': 'moderate',
                'description': 'beat row', 'layer': 'beat',
                'scope': 'intra_episode',
                'from_episode': ep, 'to_episode': ep,
            },
        ]

    def test_purge_scoped_to_imported_series(self):
        self.cmd.import_connections_v24(
            self._v24_rows('alpha'), [self.pages['alpha']['series']])
        # Series beta's legacy connection is untouched.
        self.assertTrue(NarrativeConnection.objects.filter(
            fabula_uuid='conn_legacy_beta').exists())
        # Series alpha now carries exactly the v2.4.0 set.
        alpha_conns = NarrativeConnection.objects.filter(
            from_event__in=[e.pk for e in self.pages['alpha']['events']])
        self.assertEqual(alpha_conns.count(), 2)
        self.assertEqual(
            set(alpha_conns.values_list('layer', flat=True)), {'event', 'beat'})

    def test_strength_normalized_and_episode_fks_set(self):
        self.cmd.import_connections_v24(
            self._v24_rows('alpha'), [self.pages['alpha']['series']])
        beat = NarrativeConnection.objects.get(fabula_uuid='conn_legacy_alpha')
        self.assertEqual(beat.strength, 'medium')  # moderate -> medium (R4)
        self.assertEqual(beat.from_episode, self.pages['alpha']['episode'])
        self.assertEqual(beat.to_episode, self.pages['alpha']['episode'])

    def test_collision_event_layer_wins(self):
        rows = self._v24_rows('alpha')
        # Make the beat row collide with the event row's triple.
        rows[1]['connection_type'] = 'FORESHADOWING'
        self.cmd.import_connections_v24(rows, [self.pages['alpha']['series']])
        survivors = NarrativeConnection.objects.filter(
            from_event=self.pages['alpha']['events'][0],
            to_event=self.pages['alpha']['events'][1],
            connection_type='FORESHADOWING',
        )
        self.assertEqual(survivors.count(), 1)
        self.assertEqual(survivors.first().layer, 'event')
        self.assertIn('event layer wins', self.cmd.stdout.getvalue())

    def test_reimport_is_idempotent(self):
        for _ in range(2):
            self.cmd.import_connections_v24(
                self._v24_rows('alpha'), [self.pages['alpha']['series']])
        alpha_conns = NarrativeConnection.objects.filter(
            from_event__in=[e.pk for e in self.pages['alpha']['events']])
        self.assertEqual(alpha_conns.count(), 2)

    def test_redirect_map_written_for_dead_urls(self):
        from wagtail.contrib.redirects.models import Redirect
        rows = self._v24_rows('alpha')
        # Remove the beat row so the legacy CAUSAL triple dies entirely.
        rows = [rows[0]]
        self.cmd.import_connections_v24(rows, [self.pages['alpha']['series']])
        redirect = Redirect.objects.get(
            old_path='/connections/ger_narrativeconnection_alpha')
        # Unmatched -> points at the from-event page.
        self.assertEqual(redirect.redirect_page_id,
                         self.pages['alpha']['events'][0].pk)

    def test_surviving_identity_gets_no_redirect(self):
        from wagtail.contrib.redirects.models import Redirect
        self.cmd.import_connections_v24(
            self._v24_rows('alpha'), [self.pages['alpha']['series']])
        # The beat row kept its global_id -> same URL -> no redirect row.
        self.assertFalse(Redirect.objects.filter(
            old_path__contains='ger_narrativeconnection_alpha').exists())
