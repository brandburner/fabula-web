"""
Tests for narrative models - pages, snippets, and relationship models.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import F

from wagtail.models import Page

from narrative.models import (
    # Enums
    ConnectionType, ConnectionStrength, CharacterType, ImportanceTier, ArcType,
    # Snippets
    Theme, ConflictArc, Location,
    # Pages
    SeriesIndexPage, SeasonPage, EpisodePage, CharacterPage,
    OrganizationPage, OrganizationIndexPage, ObjectPage, ObjectIndexPage,
    EventPage, EventIndexPage, CharacterIndexPage,
    # Relationships
    EventParticipation, NarrativeConnection, CharacterEpisodeProfile,
    CharacterSeasonProfile,
    ObjectInvolvement, LocationInvolvement, OrganizationInvolvement,
    # Structure
    Act, PlotBeat, EventBeatLink,
    ArcRole, ArcEventMembership, ThemeEventMembership,
    # Index pages
    ThemeIndexPage, ConnectionIndexPage,
)


class WagtailTestMixin:
    """Mixin to create common page tree structure for tests."""

    @classmethod
    def setUpTestData(cls):
        """Create the full page hierarchy once for all tests in the class."""
        root = Page.objects.get(depth=1)

        cls.series = SeriesIndexPage(
            title='Test Series',
            slug='test-series',
            fabula_uuid='series_001',
        )
        root.add_child(instance=cls.series)

        cls.season = SeasonPage(
            title='Season 1',
            slug='season-1',
            season_number=1,
            fabula_uuid='season_001',
        )
        cls.series.add_child(instance=cls.season)

        cls.episode = EpisodePage(
            title='Pilot',
            slug='pilot',
            episode_number=1,
            logline='The first episode.',
            dominant_tone='dramatic',
            fabula_uuid='episode_001',
        )
        cls.season.add_child(instance=cls.episode)

        cls.episode2 = EpisodePage(
            title='Episode Two',
            slug='episode-two',
            episode_number=2,
            fabula_uuid='episode_002',
        )
        cls.season.add_child(instance=cls.episode2)

        # Index pages
        cls.event_index = EventIndexPage(
            title='Events',
            slug='events',
        )
        cls.series.add_child(instance=cls.event_index)

        cls.char_index = CharacterIndexPage(
            title='Characters',
            slug='characters',
        )
        cls.series.add_child(instance=cls.char_index)

        cls.org_index = OrganizationIndexPage(
            title='Organizations',
            slug='organizations',
        )
        cls.series.add_child(instance=cls.org_index)

        cls.obj_index = ObjectIndexPage(
            title='Objects',
            slug='objects',
        )
        cls.series.add_child(instance=cls.obj_index)

        # Snippets
        cls.theme = Theme.objects.create(
            fabula_uuid='theme_001',
            name='Power',
            description='The nature of political power',
            series=cls.series,
        )

        cls.arc = ConflictArc.objects.create(
            fabula_uuid='arc_001',
            title='Internal Conflict',
            description='A character struggles with themselves',
            arc_type=ArcType.INTERNAL,
            series=cls.series,
        )

        cls.location = Location.objects.create(
            fabula_uuid='loc_001',
            canonical_name='The Oval Office',
            description='The president\'s office',
            location_type='Office',
            series=cls.series,
        )

        # Organization
        cls.org = OrganizationPage(
            title='White House Staff',
            slug='white-house-staff',
            canonical_name='White House Senior Staff',
            description='<p>The senior staff</p>',
            sphere_of_influence='Politics',
            fabula_uuid='org_001',
        )
        cls.org_index.add_child(instance=cls.org)

        # Characters
        cls.character1 = CharacterPage(
            title='Josh Lyman',
            slug='josh-lyman',
            canonical_name='Joshua Lyman',
            title_role='Deputy Chief of Staff',
            description='<p>A passionate political operative</p>',
            traits=['ambitious', 'loyal'],
            nicknames=['Josh'],
            character_type=CharacterType.MAIN,
            importance_tier=ImportanceTier.ANCHOR,
            appearance_count=50,
            episode_count=10,
            fabula_uuid='char_001',
            affiliated_organization=cls.org,
        )
        cls.char_index.add_child(instance=cls.character1)

        cls.character2 = CharacterPage(
            title='Donna Moss',
            slug='donna-moss',
            canonical_name='Donna Moss',
            title_role='Senior Assistant',
            description='<p>Josh\'s assistant</p>',
            character_type=CharacterType.RECURRING,
            importance_tier=ImportanceTier.PLANET,
            appearance_count=30,
            fabula_uuid='char_002',
        )
        cls.char_index.add_child(instance=cls.character2)

        # Object
        cls.obj = ObjectPage(
            title='The President\'s Pen',
            slug='presidents-pen',
            canonical_name='The President\'s Pen',
            description='<p>A pen used for signing</p>',
            purpose='Signing legislation',
            significance='Symbol of executive power',
            fabula_uuid='obj_001',
        )
        cls.obj_index.add_child(instance=cls.obj)

        # Events
        cls.event1 = EventPage(
            title='Staff Meeting',
            slug='staff-meeting',
            episode=cls.episode,
            scene_sequence=1,
            sequence_in_scene=1,
            description='<p>The staff meets to discuss strategy</p>',
            key_dialogue=['Let\'s do this.'],
            location=cls.location,
            fabula_uuid='event_001',
        )
        cls.event_index.add_child(instance=cls.event1)

        cls.event2 = EventPage(
            title='Oval Office Confrontation',
            slug='oval-office-confrontation',
            episode=cls.episode,
            scene_sequence=2,
            sequence_in_scene=1,
            description='<p>A tense confrontation</p>',
            location=cls.location,
            fabula_uuid='event_002',
        )
        cls.event_index.add_child(instance=cls.event2)

        cls.event3 = EventPage(
            title='Late Night Discussion',
            slug='late-night-discussion',
            episode=cls.episode2,
            scene_sequence=1,
            sequence_in_scene=1,
            description='<p>A late night talk</p>',
            fabula_uuid='event_003',
        )
        cls.event_index.add_child(instance=cls.event3)

        # M2M
        cls.event1.themes.add(cls.theme)
        cls.event1.arcs.add(cls.arc)

        # Participations
        cls.participation1 = EventParticipation.objects.create(
            event=cls.event1,
            character=cls.character1,
            emotional_state='Determined',
            goals=['Win the vote'],
            what_happened='Josh argued passionately',
            observed_status='Active leader',
            importance='primary',
            sort_order=0,
        )
        cls.participation2 = EventParticipation.objects.create(
            event=cls.event1,
            character=cls.character2,
            emotional_state='Supportive',
            goals=['Help Josh'],
            what_happened='Donna took notes',
            importance='secondary',
            sort_order=1,
        )

        # Connections
        cls.connection = NarrativeConnection.objects.create(
            from_event=cls.event1,
            to_event=cls.event2,
            connection_type=ConnectionType.CAUSAL,
            strength=ConnectionStrength.STRONG,
            description='The meeting leads directly to the confrontation',
            fabula_uuid='conn_001',
        )


# =============================================================================
# ENUM TESTS
# =============================================================================

class EnumTest(TestCase):
    """Test model enum/choice classes."""

    def test_connection_type_values(self):
        self.assertEqual(ConnectionType.CAUSAL, 'CAUSAL')
        self.assertEqual(ConnectionType.FORESHADOWING, 'FORESHADOWING')
        # Full 10-type vocabulary as of contract v2.4.0 (T-025)
        self.assertEqual(ConnectionType.NARRATIVELY_FOLLOWS, 'NARRATIVELY_FOLLOWS')
        self.assertEqual(len(ConnectionType.choices), 10)

    def test_connection_strength_values(self):
        self.assertEqual(len(ConnectionStrength.choices), 3)
        self.assertIn(('strong', 'Strong'), ConnectionStrength.choices)

    def test_character_type_values(self):
        self.assertEqual(len(CharacterType.choices), 4)
        self.assertEqual(CharacterType.MAIN, 'main')

    def test_importance_tier_values(self):
        self.assertEqual(len(ImportanceTier.choices), 3)
        self.assertEqual(ImportanceTier.ANCHOR, 'anchor')

    def test_arc_type_values(self):
        self.assertEqual(len(ArcType.choices), 5)
        self.assertEqual(ArcType.INTERNAL, 'INTERNAL')


# =============================================================================
# SNIPPET TESTS
# =============================================================================

class ThemeModelTest(WagtailTestMixin, TestCase):
    """Tests for Theme snippet model."""

    def test_str(self):
        self.assertEqual(str(self.theme), 'Power')

    def test_get_absolute_url_with_fabula_uuid(self):
        url = self.theme.get_absolute_url()
        self.assertEqual(url, '/themes/theme_001/')

    def test_get_absolute_url_with_global_id(self):
        self.theme.global_id = 'ger_theme_001'
        self.theme.save()
        url = self.theme.get_absolute_url()
        self.assertEqual(url, '/themes/ger_theme_001/')

    def test_unique_fabula_uuid(self):
        with self.assertRaises(IntegrityError):
            Theme.objects.create(
                fabula_uuid='theme_001',
                name='Duplicate',
                description='Should fail',
            )


class ConflictArcModelTest(WagtailTestMixin, TestCase):
    """Tests for ConflictArc snippet model."""

    def test_str(self):
        self.assertEqual(str(self.arc), 'Internal Conflict')

    def test_get_absolute_url(self):
        url = self.arc.get_absolute_url()
        self.assertEqual(url, '/arcs/arc_001/')

    def test_get_absolute_url_with_global_id(self):
        self.arc.global_id = 'ger_arc_001'
        self.arc.save()
        self.assertEqual(self.arc.get_absolute_url(), '/arcs/ger_arc_001/')

    def test_default_arc_type(self):
        arc = ConflictArc.objects.create(
            fabula_uuid='arc_002',
            title='Test Arc',
            description='Test',
        )
        self.assertEqual(arc.arc_type, ArcType.INTERPERSONAL)


class LocationModelTest(WagtailTestMixin, TestCase):
    """Tests for Location snippet model."""

    def test_str(self):
        self.assertEqual(str(self.location), 'The Oval Office')

    def test_get_absolute_url(self):
        self.assertEqual(self.location.get_absolute_url(), '/locations/loc_001/')

    def test_get_absolute_url_with_global_id(self):
        self.location.global_id = 'ger_loc_001'
        self.location.save()
        self.assertEqual(self.location.get_absolute_url(), '/locations/ger_loc_001/')

    def test_parent_location(self):
        child = Location.objects.create(
            fabula_uuid='loc_002',
            canonical_name='Resolute Desk',
            description='The famous desk',
            parent_location=self.location,
        )
        self.assertEqual(child.parent_location, self.location)
        self.assertIn(child, self.location.child_locations.all())

    def test_megagraph_fields_default(self):
        self.assertEqual(self.location.season_appearances, [])
        self.assertEqual(self.location.local_uuids, {})
        self.assertIsNone(self.location.first_appearance_season)


# =============================================================================
# PAGE TESTS
# =============================================================================

class SeriesIndexPageTest(WagtailTestMixin, TestCase):

    def test_page_tree_structure(self):
        """Verify the page hierarchy."""
        self.assertTrue(self.season.is_child_of(self.series))
        self.assertTrue(self.episode.is_child_of(self.season))

    def test_subpage_types(self):
        self.assertIn('narrative.SeasonPage', SeriesIndexPage.subpage_types)
        self.assertIn('narrative.EventIndexPage', SeriesIndexPage.subpage_types)

    def test_get_context(self):
        from django.test import RequestFactory
        request = RequestFactory().get('/')
        context = self.series.get_context(request)
        self.assertIn('seasons', context)
        self.assertIn('events_index', context)
        self.assertIn('characters_index', context)
        self.assertIn('organizations_index', context)
        self.assertIn('objects_index', context)
        self.assertEqual(len(context['seasons']), 1)
        self.assertEqual(context['seasons'][0].season_number, 1)


class EpisodePageTest(WagtailTestMixin, TestCase):

    def test_get_events(self):
        events = self.episode.get_events()
        self.assertEqual(events.count(), 2)
        # Should be ordered by scene_sequence
        self.assertEqual(list(events), [self.event1, self.event2])

    def test_get_events_empty(self):
        """Episode with no events."""
        ep = EpisodePage(
            title='Empty Episode',
            slug='empty-episode',
            episode_number=99,
        )
        self.season.add_child(instance=ep)
        self.assertEqual(ep.get_events().count(), 0)


class CharacterPageTest(WagtailTestMixin, TestCase):

    def test_get_participations(self):
        parts = self.character1.get_participations()
        self.assertEqual(parts.count(), 1)
        self.assertEqual(parts[0].event, self.event1)

    def test_get_absolute_url_with_fabula_uuid(self):
        self.assertEqual(self.character1.get_absolute_url(), '/characters/char_001/')

    def test_get_absolute_url_with_global_id(self):
        self.character1.global_id = 'ger_char_001'
        self.character1.save()
        self.assertEqual(self.character1.get_absolute_url(), '/characters/ger_char_001/')

    def test_default_importance_tier(self):
        char = CharacterPage(
            title='Nobody',
            slug='nobody',
            canonical_name='Nobody',
            description='<p>Nobody</p>',
            fabula_uuid='char_nobody',
        )
        self.char_index.add_child(instance=char)
        self.assertEqual(char.importance_tier, ImportanceTier.ASTEROID)


class CharacterIndexPageTest(WagtailTestMixin, TestCase):

    def test_get_characters(self):
        chars = self.char_index.get_characters()
        self.assertEqual(chars.count(), 2)
        # Ordered by -appearance_count
        self.assertEqual(chars[0], self.character1)  # 50 appearances
        self.assertEqual(chars[1], self.character2)  # 30 appearances


class OrganizationPageTest(WagtailTestMixin, TestCase):

    def test_get_search_terms(self):
        terms = self.org.get_search_terms()
        self.assertIn('White House Senior Staff', terms)
        self.assertIn('White House', terms)

    def test_get_search_terms_with_parenthetical(self):
        org = OrganizationPage(
            title='Test Org',
            slug='test-org-paren',
            canonical_name='Department of Justice (DOJ)',
            description='<p>DOJ</p>',
            fabula_uuid='org_paren',
        )
        self.org_index.add_child(instance=org)
        terms = org.get_search_terms()
        self.assertIn('Department of Justice (DOJ)', terms)
        self.assertIn('Department of Justice', terms)
        self.assertIn('Department of', terms)

    def test_get_absolute_url(self):
        self.assertEqual(self.org.get_absolute_url(), '/organizations/org_001/')


class EventPageTest(WagtailTestMixin, TestCase):

    def test_get_participations_by_importance(self):
        grouped = self.event1.get_participations_by_importance()
        self.assertEqual(len(grouped['primary']), 1)
        self.assertEqual(len(grouped['secondary']), 1)
        self.assertEqual(len(grouped['mentioned']), 0)
        self.assertEqual(len(grouped['other']), 0)

    def test_get_participations_by_importance_empty_importance_defaults_to_primary(self):
        """Empty importance should be treated as primary."""
        EventParticipation.objects.filter(pk=self.participation1.pk).update(importance='')
        grouped = self.event1.get_participations_by_importance()
        self.assertEqual(len(grouped['primary']), 1)

    def test_get_participations_engagement_sorting(self):
        """Participants with richer data should appear first."""
        # Create a sparse participation
        char3 = CharacterPage(
            title='Extra',
            slug='extra',
            canonical_name='Extra',
            description='<p>Extra</p>',
            fabula_uuid='char_extra',
        )
        self.char_index.add_child(instance=char3)

        EventParticipation.objects.create(
            event=self.event1,
            character=char3,
            emotional_state='',
            goals=[],
            what_happened='',
            importance='primary',
            sort_order=2,
        )
        grouped = self.event1.get_participations_by_importance()
        primaries = grouped['primary']
        self.assertEqual(len(primaries), 2)
        # The one with rich data (character1) should be first
        self.assertEqual(primaries[0].character, self.character1)

    def test_get_primary_participants(self):
        primaries = self.event1.get_primary_participants()
        self.assertEqual(primaries.count(), 1)
        self.assertEqual(primaries[0].character, self.character1)

    def test_get_connections_from(self):
        outgoing = self.event1.get_connections_from()
        self.assertEqual(outgoing.count(), 1)
        self.assertEqual(outgoing[0].to_event, self.event2)

    def test_get_connections_to(self):
        incoming = self.event2.get_connections_to()
        self.assertEqual(incoming.count(), 1)
        self.assertEqual(incoming[0].from_event, self.event1)

    def test_get_all_connections(self):
        conns = self.event1.get_all_connections()
        self.assertEqual(conns['outgoing'].count(), 1)
        self.assertEqual(conns['incoming'].count(), 0)

    def test_primary_location_has_involvement_false(self):
        """No LocationInvolvement record exists."""
        self.assertFalse(self.event1.primary_location_has_involvement())

    def test_primary_location_has_involvement_true(self):
        LocationInvolvement.objects.create(
            event=self.event1,
            location=self.location,
            description_of_involvement='Setting the scene',
            sort_order=0,
        )
        self.assertTrue(self.event1.primary_location_has_involvement())

    def test_primary_location_has_involvement_no_location(self):
        """Event with no location FK."""
        self.assertFalse(self.event3.primary_location_has_involvement())

    def test_get_absolute_url(self):
        self.assertEqual(self.event1.get_absolute_url(), '/events/event_001/')

    def test_get_absolute_url_with_global_id(self):
        self.event1.global_id = 'ger_event_001'
        self.event1.save()
        self.assertEqual(self.event1.get_absolute_url(), '/events/ger_event_001/')


class ObjectPageTest(WagtailTestMixin, TestCase):

    def test_get_absolute_url(self):
        self.assertEqual(self.obj.get_absolute_url(), '/objects/obj_001/')

    def test_get_involvements_empty(self):
        self.assertEqual(self.obj.get_involvements().count(), 0)

    def test_get_involvements_with_data(self):
        ObjectInvolvement.objects.create(
            event=self.event1,
            object=self.obj,
            description_of_involvement='Signed the bill',
            sort_order=0,
        )
        involvements = self.obj.get_involvements()
        self.assertEqual(involvements.count(), 1)


# =============================================================================
# RELATIONSHIP MODEL TESTS
# =============================================================================

class EventParticipationTest(WagtailTestMixin, TestCase):

    def test_str(self):
        self.assertEqual(
            str(self.participation1),
            'Josh Lyman in Staff Meeting'
        )

    def test_unique_together(self):
        """Can't create duplicate event+character participation."""
        with self.assertRaises(IntegrityError):
            EventParticipation.objects.create(
                event=self.event1,
                character=self.character1,
                sort_order=99,
            )


class NarrativeConnectionTest(WagtailTestMixin, TestCase):

    def test_str(self):
        expected = 'Staff Meeting \u2192 [CAUSAL] \u2192 Oval Office Confrontation'
        self.assertEqual(str(self.connection), expected)

    def test_get_absolute_url(self):
        self.assertEqual(self.connection.get_absolute_url(), '/connections/conn_001/')

    def test_get_absolute_url_with_global_id(self):
        self.connection.global_id = 'ger_conn_001'
        self.connection.save()
        self.assertEqual(self.connection.get_absolute_url(), '/connections/ger_conn_001/')

    def test_unique_together(self):
        """Can't create duplicate from_event+to_event+type."""
        with self.assertRaises(IntegrityError):
            NarrativeConnection.objects.create(
                from_event=self.event1,
                to_event=self.event2,
                connection_type=ConnectionType.CAUSAL,
                description='Duplicate',
            )

    def test_different_type_allowed(self):
        """Same events with different connection type is fine."""
        conn = NarrativeConnection.objects.create(
            from_event=self.event1,
            to_event=self.event2,
            connection_type=ConnectionType.THEMATIC_PARALLEL,
            description='They share a theme',
        )
        self.assertIsNotNone(conn.pk)


class CharacterEpisodeProfileTest(WagtailTestMixin, TestCase):

    def test_str(self):
        profile = CharacterEpisodeProfile.objects.create(
            character=self.character1,
            episode=self.episode,
            description_in_episode='Josh is conflicted',
            traits_in_episode=['conflicted', 'driven'],
            fabula_uuid='profile_001',
        )
        self.assertEqual(str(profile), 'Josh Lyman in Pilot')

    def test_unique_together(self):
        CharacterEpisodeProfile.objects.create(
            character=self.character1,
            episode=self.episode,
            fabula_uuid='profile_001',
        )
        with self.assertRaises(IntegrityError):
            CharacterEpisodeProfile.objects.create(
                character=self.character1,
                episode=self.episode,
                fabula_uuid='profile_002',
            )


class ObjectInvolvementTest(WagtailTestMixin, TestCase):

    def test_str(self):
        involvement = ObjectInvolvement.objects.create(
            event=self.event1,
            object=self.obj,
            description_of_involvement='Used for signing',
            sort_order=0,
        )
        self.assertEqual(str(involvement), "The President's Pen in Staff Meeting")

    def test_unique_together(self):
        ObjectInvolvement.objects.create(
            event=self.event1,
            object=self.obj,
            sort_order=0,
        )
        with self.assertRaises(IntegrityError):
            ObjectInvolvement.objects.create(
                event=self.event1,
                object=self.obj,
                sort_order=1,
            )


class LocationInvolvementTest(WagtailTestMixin, TestCase):

    def test_str(self):
        involvement = LocationInvolvement.objects.create(
            event=self.event1,
            location=self.location,
            description_of_involvement='The main setting',
            observed_atmosphere='Tense',
            sort_order=0,
        )
        self.assertEqual(str(involvement), 'The Oval Office in Staff Meeting')


class OrganizationInvolvementTest(WagtailTestMixin, TestCase):

    def test_str(self):
        involvement = OrganizationInvolvement.objects.create(
            event=self.event1,
            organization=self.org,
            description_of_involvement='Staff coordinating',
            sort_order=0,
        )
        self.assertEqual(str(involvement), 'White House Staff in Staff Meeting')


# =============================================================================
# ACT / PLOTBEAT / EVENTBEATLINK TESTS
# =============================================================================

class ActModelTest(WagtailTestMixin, TestCase):

    def test_str(self):
        act = Act.objects.create(
            fabula_uuid='act_001',
            episode=self.episode,
            number=1,
            summary='The opening act',
            scene_numbers=[1, 2],
        )
        self.assertEqual(str(act), 'Act 1 \u2014 Pilot')

    def test_get_events(self):
        act = Act.objects.create(
            fabula_uuid='act_001',
            episode=self.episode,
            number=1,
            scene_numbers=[1],
        )
        events = act.get_events()
        self.assertEqual(events.count(), 1)
        self.assertEqual(events[0], self.event1)

    def test_get_events_multiple_scenes(self):
        act = Act.objects.create(
            fabula_uuid='act_001',
            episode=self.episode,
            number=1,
            scene_numbers=[1, 2],
        )
        events = act.get_events()
        self.assertEqual(events.count(), 2)

    def test_get_events_no_matching_scenes(self):
        act = Act.objects.create(
            fabula_uuid='act_001',
            episode=self.episode,
            number=1,
            scene_numbers=[99],
        )
        self.assertEqual(act.get_events().count(), 0)

    def test_unique_together(self):
        Act.objects.create(
            fabula_uuid='act_001',
            episode=self.episode,
            number=1,
        )
        with self.assertRaises(IntegrityError):
            Act.objects.create(
                fabula_uuid='act_002',
                episode=self.episode,
                number=1,
            )


class PlotBeatModelTest(WagtailTestMixin, TestCase):

    def test_str(self):
        beat = PlotBeat.objects.create(
            fabula_uuid='beat_001',
            episode=self.episode,
            scene_sequence=1,
            sequence_in_scene=2,
            action_description='Character enters room',
        )
        self.assertEqual(str(beat), 'Beat 1.2 \u2014 Pilot')


class EventBeatLinkTest(WagtailTestMixin, TestCase):

    def test_str(self):
        beat = PlotBeat.objects.create(
            fabula_uuid='beat_001',
            episode=self.episode,
            scene_sequence=1,
            sequence_in_scene=1,
        )
        link = EventBeatLink.objects.create(
            event=self.event1,
            plot_beat=beat,
        )
        self.assertEqual(str(link), 'Staff Meeting \u2190 Beat beat_001')

    def test_unique_together(self):
        beat = PlotBeat.objects.create(
            fabula_uuid='beat_001',
            episode=self.episode,
            scene_sequence=1,
            sequence_in_scene=1,
        )
        EventBeatLink.objects.create(event=self.event1, plot_beat=beat)
        with self.assertRaises(IntegrityError):
            EventBeatLink.objects.create(event=self.event1, plot_beat=beat)


# =============================================================================
# INDEX PAGE TESTS
# =============================================================================

class ThemeIndexPageTest(WagtailTestMixin, TestCase):

    def test_get_themes(self):
        tip = ThemeIndexPage(title='Themes', slug='themes')
        self.series.add_child(instance=tip)
        themes = tip.get_themes()
        self.assertTrue(themes.exists())
        # Should be annotated with event_count
        self.assertTrue(hasattr(themes[0], 'event_count'))


class ConnectionIndexPageTest(WagtailTestMixin, TestCase):

    def test_get_connections_by_type(self):
        cip = ConnectionIndexPage(title='Connections', slug='connections')
        self.series.add_child(instance=cip)
        by_type = cip.get_connections_by_type()
        # Should have at least CAUSAL
        causal_key = None
        for key in by_type:
            if key[0] == 'CAUSAL':
                causal_key = key
                break
        self.assertIsNotNone(causal_key)
        self.assertEqual(by_type[causal_key].count(), 1)


class OrganizationIndexPageTest(WagtailTestMixin, TestCase):

    def test_get_organizations(self):
        orgs = self.org_index.get_organizations()
        self.assertEqual(orgs.count(), 1)
        self.assertEqual(orgs[0], self.org)


class ObjectIndexPageTest(WagtailTestMixin, TestCase):

    def test_get_objects(self):
        objects = self.obj_index.get_objects()
        self.assertEqual(objects.count(), 1)


class CrossSeasonOrderingTest(WagtailTestMixin, TestCase):
    """
    Regression for the episode-ordering hazard (G5 / fabula_v2 852c584):
    on multi-season data every season has an "episode 1", so any ordering
    by bare episode_number interleaves seasons. Default orderings must use
    (season_number, episode_number).
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.season2 = SeasonPage(
            title='Season 2',
            slug='season-2',
            season_number=2,
            fabula_uuid='season_002',
        )
        cls.series.add_child(instance=cls.season2)

        # Late season-1 episode: bare episode_number ordering would sort
        # S2E1 (number 1) before this (number 13).
        cls.s1e13 = EpisodePage(
            title='Season One Finale',
            slug='season-one-finale',
            episode_number=13,
            season_number=1,
            fabula_uuid='episode_s1e13',
        )
        cls.season.add_child(instance=cls.s1e13)

        cls.s2e1 = EpisodePage(
            title='Season Two Premiere',
            slug='season-two-premiere',
            episode_number=1,
            season_number=2,
            fabula_uuid='episode_s2e01',
        )
        cls.season2.add_child(instance=cls.s2e1)

        cls.event_s1e13 = EventPage(
            title='Finale Event',
            slug='finale-event',
            episode=cls.s1e13,
            scene_sequence=1,
            sequence_in_scene=1,
            description='<p>Season one closes</p>',
            fabula_uuid='event_s1e13_1',
        )
        cls.event_index.add_child(instance=cls.event_s1e13)

        cls.event_s2e1 = EventPage(
            title='Premiere Event',
            slug='premiere-event',
            episode=cls.s2e1,
            scene_sequence=1,
            sequence_in_scene=1,
            description='<p>Season two opens</p>',
            fabula_uuid='event_s2e1_1',
        )
        cls.event_index.add_child(instance=cls.event_s2e1)

    def test_episode_default_ordering_is_season_aware(self):
        ordering = list(
            EpisodePage.objects.live().values_list('season_number', 'episode_number')
        )
        self.assertEqual(ordering, sorted(ordering))
        self.assertLess(
            ordering.index((1, 13)),
            ordering.index((2, 1)),
            "S2E1 must sort after S1E13",
        )

    def test_event_default_ordering_is_season_aware(self):
        events = list(EventPage.objects.live())
        self.assertLess(
            events.index(self.event_s1e13),
            events.index(self.event_s2e1),
            "Events in S2E1 must sort after events in S1E13",
        )

    def test_theme_events_ordered_across_seasons(self):
        # Mirrors the ThemeDetailView / ArcDetailView querysets.
        self.event_s1e13.themes.add(self.theme)
        self.event_s2e1.themes.add(self.theme)
        self.event_s1e13.save()
        self.event_s2e1.save()
        events = list(
            self.theme.events.all().order_by(
                'episode__season_number', 'episode__episode_number', 'scene_sequence'
            )
        )
        self.assertEqual(events, [self.event_s1e13, self.event_s2e1])


class ConnectionStorylineFieldsTest(WagtailTestMixin, TestCase):
    """T-025: layer/scope/provenance/episode FKs on NarrativeConnection."""

    def test_legacy_defaults(self):
        # Rows created without the new fields (legacy path) default to the
        # beat layer / intra-episode scope with null episode FKs.
        conn = NarrativeConnection.objects.create(
            from_event=self.event1, to_event=self.event2,
            connection_type=ConnectionType.NARRATIVELY_FOLLOWS,
            strength=ConnectionStrength.WEAK,
            description='x', fabula_uuid='conn_nf_1',
        )
        conn.refresh_from_db()
        self.assertEqual(conn.layer, 'beat')
        self.assertEqual(conn.scope, 'intra_episode')
        self.assertEqual(conn.inferred_by, '')
        self.assertEqual(conn.cross_episode_reasoning, '')
        self.assertIsNone(conn.from_episode)
        self.assertIsNone(conn.to_episode)

    def test_season_bridge_query_via_episode_fks(self):
        season2 = SeasonPage(
            title='Season 2', slug='season-2-conn', season_number=2,
            fabula_uuid='season_conn_2',
        )
        self.series.add_child(instance=season2)
        s2e1 = EpisodePage(
            title='S2 Opener', slug='s2-opener-conn', episode_number=1,
            season_number=2, fabula_uuid='ep_conn_s2e1',
        )
        season2.add_child(instance=s2e1)

        NarrativeConnection.objects.create(
            from_event=self.event1, to_event=self.event2,
            connection_type=ConnectionType.FORESHADOWING,
            description='bridges seasons', fabula_uuid='conn_bridge',
            layer='event', scope='cross_episode',
            inferred_by='llm_cross_episode_arc',
            cross_episode_reasoning='seeded early, pays off later',
            from_episode=self.episode, to_episode=s2e1,
        )
        # The denormalized FKs make "bridges seasons" one indexed query.
        bridges = NarrativeConnection.objects.filter(
            scope='cross_episode',
        ).exclude(
            from_episode__season_number=F('to_episode__season_number'),
        )
        self.assertEqual(bridges.count(), 1)
        self.assertEqual(bridges.first().fabula_uuid, 'conn_bridge')


class MembershipJunctionTest(WagtailTestMixin, TestCase):
    """T-026: ArcEventMembership / ThemeEventMembership junctions."""

    def test_arc_membership_with_role_and_ordinal(self):
        m = ArcEventMembership.objects.create(
            event=self.event1, arc=self.arc, role=ArcRole.START,
            episode_ordinal=101,
        )
        self.assertEqual(m.role, 'START')
        self.assertEqual(self.arc.event_memberships.count(), 1)
        self.assertEqual(self.event1.arc_memberships.count(), 1)

    def test_membership_unique_per_pair(self):
        ArcEventMembership.objects.create(
            event=self.event1, arc=self.arc, episode_ordinal=101,
        )
        with self.assertRaises(IntegrityError):
            ArcEventMembership.objects.create(
                event=self.event1, arc=self.arc, role=ArcRole.CLIMAX,
            )

    def test_memberships_order_by_ordinal(self):
        ThemeEventMembership.objects.create(
            event=self.event3, theme=self.theme, episode_ordinal=102,
        )
        ThemeEventMembership.objects.create(
            event=self.event1, theme=self.theme, episode_ordinal=101,
        )
        ordinals = list(self.theme.event_memberships.values_list(
            'episode_ordinal', flat=True))
        self.assertEqual(ordinals, [101, 102])

    def test_involved_characters_m2m(self):
        self.arc.involved_characters.add(self.character1)
        self.theme.related_characters.add(self.character2)
        self.assertIn(self.arc, self.character1.involved_arcs.all())
        self.assertIn(self.theme, self.character2.related_themes.all())


class StorylineSeriesBackfillTest(WagtailTestMixin, TestCase):
    """Migration 0025 (ISS-015): legacy storylines get their series FK
    inferred from membership evidence; orphans stay NULL."""

    def _run_backfill(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module(
            'narrative.migrations.0025_backfill_storyline_series')
        migration.backfill(apps, None)

    def test_backfill_sets_series_from_memberships(self):
        Theme.objects.filter(pk=self.theme.pk).update(series=None)
        ConflictArc.objects.filter(pk=self.arc.pk).update(series=None)
        ThemeEventMembership.objects.create(
            event=self.event1, theme=self.theme, episode_ordinal=101)
        ArcEventMembership.objects.create(
            event=self.event2, arc=self.arc, episode_ordinal=101)

        self._run_backfill()

        self.theme.refresh_from_db()
        self.arc.refresh_from_db()
        self.assertEqual(self.theme.series_id, self.series.pk)
        self.assertEqual(self.arc.series_id, self.series.pk)

    def test_backfill_leaves_orphans_and_scoped_rows_alone(self):
        orphan = Theme.objects.create(
            fabula_uuid='theme_orphan', name='Orphan', description='x')

        self._run_backfill()

        orphan.refresh_from_db()
        self.theme.refresh_from_db()
        self.assertIsNone(orphan.series)
        # Already-scoped rows keep their FK untouched
        self.assertEqual(self.theme.series_id, self.series.pk)


class ConnectionEpisodeBackfillTest(WagtailTestMixin, TestCase):
    """Migration 0026 (T-032): legacy connections get episode FKs from
    their events, and scope flips to cross_episode where episodes differ."""

    def _run_backfill(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module(
            'narrative.migrations.0026_backfill_connection_episodes')
        migration.backfill(apps, None)

    def test_backfill_fills_fks_and_corrects_scope(self):
        intra = NarrativeConnection.objects.create(
            from_event=self.event1, to_event=self.event2,
            connection_type=ConnectionType.CHARACTER_CONTINUITY,
            description='same-episode legacy row',
        )
        cross = NarrativeConnection.objects.create(
            from_event=self.event1, to_event=self.event3,
            connection_type=ConnectionType.FORESHADOWING,
            description='cross-episode legacy row mislabeled intra',
        )

        self._run_backfill()

        intra.refresh_from_db()
        cross.refresh_from_db()
        self.assertEqual(intra.from_episode_id, self.episode.pk)
        self.assertEqual(intra.to_episode_id, self.episode.pk)
        self.assertEqual(intra.scope, 'intra_episode')
        self.assertEqual(cross.from_episode_id, self.episode.pk)
        self.assertEqual(cross.to_episode_id, self.episode2.pk)
        self.assertEqual(cross.scope, 'cross_episode')

    def test_backfill_leaves_populated_fks_alone(self):
        row = NarrativeConnection.objects.create(
            from_event=self.event1, to_event=self.event3,
            connection_type=ConnectionType.ESCALATION,
            description='v2.4.0 row with FKs already set',
            from_episode=self.episode2, to_episode=self.episode2,
        )

        self._run_backfill()

        row.refresh_from_db()
        # Deliberately "wrong" FKs prove the update never touches
        # rows whose from_episode is already populated
        self.assertEqual(row.from_episode_id, self.episode2.pk)


class CharacterSeasonProfileTest(WagtailTestMixin, TestCase):
    """T-027: per-season character portraits + arc_summary."""

    def test_season_profile_unique_per_season(self):
        CharacterSeasonProfile.objects.create(
            character=self.character1, season_number=1,
            description='S1 portrait', tier='anchor',
            source_database='test_s01',
        )
        with self.assertRaises(IntegrityError):
            CharacterSeasonProfile.objects.create(
                character=self.character1, season_number=1,
                description='duplicate',
            )

    def test_season_profiles_ordered_by_season(self):
        CharacterSeasonProfile.objects.create(
            character=self.character1, season_number=2, description='S2')
        CharacterSeasonProfile.objects.create(
            character=self.character1, season_number=1, description='S1')
        self.assertEqual(
            list(self.character1.season_profiles.values_list(
                'season_number', flat=True)),
            [1, 2],
        )

    def test_arc_summary_field(self):
        self.character1.arc_summary = 'Rises, falls, rises again.'
        self.character1.save()
        self.character1.refresh_from_db()
        self.assertEqual(self.character1.arc_summary, 'Rises, falls, rises again.')
