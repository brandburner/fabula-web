"""
Tests for narrative views - catalog, detail, index, and graph views.
"""
from django.core.cache import cache
from django.test import TestCase, Client
from django.urls import reverse

from wagtail.models import Page

from narrative.models import (
    ConnectionType, ConnectionStrength, CharacterType, ImportanceTier, ArcType,
    ConnectionLayer, ConnectionScope, ArcRole,
    Theme, ConflictArc, Location,
    SeriesIndexPage, SeasonPage, EpisodePage, CharacterPage,
    OrganizationPage, OrganizationIndexPage, ObjectPage, ObjectIndexPage,
    EventPage, EventIndexPage, CharacterIndexPage,
    EventParticipation, NarrativeConnection,
    ArcEventMembership, ThemeEventMembership,
    LocationInvolvement, ObjectInvolvement, OrganizationInvolvement,
)


class ViewTestMixin:
    """Mixin to create test data for view tests."""

    def setUp(self):
        # Some views (e.g. CharacterDetailView) are wrapped in cache_page;
        # LocMemCache survives across tests in-process, so a URL hit by an
        # earlier test would otherwise return a cached response with
        # response.context == None.
        cache.clear()
        super().setUp()

    @classmethod
    def setUpTestData(cls):
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
        )
        cls.series.add_child(instance=cls.season)

        cls.episode = EpisodePage(
            title='Pilot',
            slug='pilot',
            episode_number=1,
            logline='The first episode.',
            fabula_uuid='ep_001',
        )
        cls.season.add_child(instance=cls.episode)

        # Index pages
        cls.event_index = EventIndexPage(title='Events', slug='events')
        cls.series.add_child(instance=cls.event_index)

        cls.char_index = CharacterIndexPage(title='Characters', slug='characters')
        cls.series.add_child(instance=cls.char_index)

        cls.org_index = OrganizationIndexPage(title='Organizations', slug='organizations')
        cls.series.add_child(instance=cls.org_index)

        cls.obj_index = ObjectIndexPage(title='Objects', slug='objects')
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
            description='A character struggles',
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

        # Pages
        cls.org = OrganizationPage(
            title='White House Staff',
            slug='white-house-staff',
            canonical_name='White House Senior Staff',
            description='<p>The senior staff</p>',
            fabula_uuid='org_001',
        )
        cls.org_index.add_child(instance=cls.org)

        cls.character = CharacterPage(
            title='Josh Lyman',
            slug='josh-lyman',
            canonical_name='Joshua Lyman',
            title_role='Deputy Chief of Staff',
            description='<p>A passionate political operative</p>',
            character_type=CharacterType.MAIN,
            importance_tier=ImportanceTier.ANCHOR,
            appearance_count=50,
            fabula_uuid='agent_001',
            global_id='ger_agent_001',
            affiliated_organization=cls.org,
        )
        cls.char_index.add_child(instance=cls.character)

        cls.obj = ObjectPage(
            title='The Pen',
            slug='the-pen',
            canonical_name='The Pen',
            description='<p>A pen</p>',
            fabula_uuid='object_001',
        )
        cls.obj_index.add_child(instance=cls.obj)

        cls.event1 = EventPage(
            title='Staff Meeting',
            slug='staff-meeting',
            episode=cls.episode,
            scene_sequence=1,
            sequence_in_scene=1,
            description='<p>The staff meets</p>',
            location=cls.location,
            fabula_uuid='event_001',
            global_id='ger_event_001',
        )
        cls.event_index.add_child(instance=cls.event1)

        cls.event2 = EventPage(
            title='Confrontation',
            slug='confrontation',
            episode=cls.episode,
            scene_sequence=2,
            sequence_in_scene=1,
            description='<p>A confrontation</p>',
            fabula_uuid='event_002',
        )
        cls.event_index.add_child(instance=cls.event2)

        # M2M
        cls.event1.themes.add(cls.theme)
        cls.event1.arcs.add(cls.arc)

        # Participations
        cls.participation = EventParticipation.objects.create(
            event=cls.event1,
            character=cls.character,
            emotional_state='Determined',
            goals=['Win the vote'],
            what_happened='Josh argued passionately',
            importance='primary',
            sort_order=0,
        )

        # Connections
        cls.connection = NarrativeConnection.objects.create(
            from_event=cls.event1,
            to_event=cls.event2,
            connection_type=ConnectionType.CAUSAL,
            strength=ConnectionStrength.STRONG,
            description='Meeting leads to confrontation',
            fabula_uuid='conn_001',
            global_id='ger_conn_001',
        )

        # Involvements
        cls.loc_involvement = LocationInvolvement.objects.create(
            event=cls.event1,
            location=cls.location,
            description_of_involvement='Main setting',
            sort_order=0,
        )
        cls.obj_involvement = ObjectInvolvement.objects.create(
            event=cls.event1,
            object=cls.obj,
            description_of_involvement='Used in scene',
            sort_order=0,
        )
        cls.org_involvement = OrganizationInvolvement.objects.create(
            event=cls.event1,
            organization=cls.org,
            description_of_involvement='Staff coordinating',
            sort_order=0,
        )


# =============================================================================
# CATALOG & SERIES VIEWS
# =============================================================================

class CatalogViewTest(ViewTestMixin, TestCase):

    def test_site_root_home(self):
        # The site root is the marketing home ('v2_home'); the narrative
        # catalog lives at the 'catalog' route (see test_catalog_has_series).
        response = self.client.get(reverse('v2_home'))
        self.assertEqual(response.status_code, 200)

    def test_catalog_explore(self):
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.status_code, 200)

    def test_catalog_has_series(self):
        response = self.client.get(reverse('catalog'))
        self.assertEqual(response.context['total_series'], 1)
        stats = response.context['series_list'][0]
        self.assertEqual(stats['series'], self.series)
        self.assertGreaterEqual(stats['event_count'], 0)


class SeriesLandingViewTest(ViewTestMixin, TestCase):

    def test_series_landing(self):
        response = self.client.get(reverse('series_landing', kwargs={'series_slug': 'test-series'}))
        self.assertEqual(response.status_code, 200)

    def test_series_landing_404(self):
        response = self.client.get(reverse('series_landing', kwargs={'series_slug': 'nonexistent'}))
        self.assertEqual(response.status_code, 404)


# =============================================================================
# CONNECTION VIEWS
# =============================================================================

class ConnectionIndexViewTest(ViewTestMixin, TestCase):

    def test_global_index(self):
        response = self.client.get(reverse('connection_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('connections_by_type', response.context)
        self.assertIn('total_count', response.context)
        self.assertEqual(response.context['total_count'], 1)


class ConnectionDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('connection_detail', kwargs={'identifier': 'conn_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['connection'], self.connection)

    def test_by_global_id(self):
        response = self.client.get(reverse('connection_detail', kwargs={'identifier': 'ger_conn_001'}))
        self.assertEqual(response.status_code, 200)

    def test_by_pk(self):
        response = self.client.get(reverse('connection_detail', kwargs={'identifier': str(self.connection.pk)}))
        self.assertEqual(response.status_code, 200)

    def test_not_found(self):
        response = self.client.get(reverse('connection_detail', kwargs={'identifier': 'nonexistent'}))
        self.assertEqual(response.status_code, 404)


class ConnectionTypeViewTest(ViewTestMixin, TestCase):

    def test_valid_type(self):
        response = self.client.get(reverse('connection_type_list', kwargs={'connection_type': 'causal'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['connection_type'], 'CAUSAL')
        self.assertEqual(len(response.context['connections']), 1)

    def test_empty_type(self):
        response = self.client.get(reverse('connection_type_list', kwargs={'connection_type': 'foreshadowing'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['connections']), 0)


# =============================================================================
# THEME VIEWS
# =============================================================================

class ThemeIndexViewTest(ViewTestMixin, TestCase):

    def test_index(self):
        response = self.client.get(reverse('theme_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('themes', response.context)


class ThemeDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('theme_detail', kwargs={'identifier': 'theme_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['theme'], self.theme)
        self.assertIn('events', response.context)
        self.assertIn('other_themes', response.context)

    def test_by_pk(self):
        response = self.client.get(reverse('theme_detail', kwargs={'identifier': str(self.theme.pk)}))
        self.assertEqual(response.status_code, 200)

    def test_not_found(self):
        response = self.client.get(reverse('theme_detail', kwargs={'identifier': 'nonexistent'}))
        self.assertEqual(response.status_code, 404)


# =============================================================================
# ARC VIEWS
# =============================================================================

class ArcIndexViewTest(ViewTestMixin, TestCase):

    def test_index(self):
        response = self.client.get(reverse('arc_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('arcs', response.context)


class ArcDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('arc_detail', kwargs={'identifier': 'arc_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['arc'], self.arc)
        self.assertIn('events', response.context)


# =============================================================================
# STORYLINE TIMELINES (T-030)
# =============================================================================

class StorylineTimelineFixtureMixin(ViewTestMixin):
    """Second season + junction rows for arc/theme timeline tests."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()

        cls.season2 = SeasonPage(
            title='Season 2', slug='season-2', season_number=2,
        )
        cls.series.add_child(instance=cls.season2)

        cls.episode2 = EpisodePage(
            title='Return', slug='return',
            episode_number=1, season_number=2,
            logline='Season two opens.', fabula_uuid='ep_002',
        )
        cls.season2.add_child(instance=cls.episode2)

        cls.event3 = EventPage(
            title='Reckoning', slug='reckoning',
            episode=cls.episode2, scene_sequence=1, sequence_in_scene=1,
            description='<p>The reckoning</p>', fabula_uuid='event_003',
        )
        cls.event_index.add_child(instance=cls.event3)

        # Arc memberships: two S1 events, one S2 event, roles on the ends
        ArcEventMembership.objects.create(
            event=cls.event1, arc=cls.arc, role=ArcRole.START, episode_ordinal=101)
        ArcEventMembership.objects.create(
            event=cls.event2, arc=cls.arc, episode_ordinal=101)
        ArcEventMembership.objects.create(
            event=cls.event3, arc=cls.arc, role=ArcRole.CLIMAX, episode_ordinal=201)

        ThemeEventMembership.objects.create(
            event=cls.event1, theme=cls.theme, episode_ordinal=101)
        ThemeEventMembership.objects.create(
            event=cls.event3, theme=cls.theme, episode_ordinal=201)

        # A real season bridge: S1 event → S2 event, episode FKs present
        cls.bridge = NarrativeConnection.objects.create(
            from_event=cls.event2, to_event=cls.event3,
            connection_type=ConnectionType.ESCALATION,
            strength=ConnectionStrength.STRONG,
            description='The confrontation escalates into the reckoning',
            layer=ConnectionLayer.EVENT, scope=ConnectionScope.CROSS_EPISODE,
            from_episode=cls.episode, to_episode=cls.episode2,
            fabula_uuid='conn_bridge_001',
        )
        # Cross-episode row missing an episode FK (SET_NULL after an
        # episode deletion) — excluded from bridges without raising
        cls.null_fk_conn = NarrativeConnection.objects.create(
            from_event=cls.event1, to_event=cls.event3,
            connection_type=ConnectionType.FORESHADOWING,
            strength=ConnectionStrength.MEDIUM,
            description='The meeting foreshadows the reckoning',
            layer=ConnectionLayer.EVENT, scope=ConnectionScope.CROSS_EPISODE,
            from_episode=None, to_episode=cls.episode2,
            fabula_uuid='conn_bridge_002',
        )


class ArcTimelineViewTest(StorylineTimelineFixtureMixin, TestCase):

    def _get(self):
        return self.client.get(reverse('arc_detail', kwargs={'identifier': 'arc_001'}))

    def test_timeline_groups_and_orders_across_seasons(self):
        response = self._get()
        self.assertEqual(response.status_code, 200)
        seasons = response.context['timeline_seasons']
        self.assertEqual([s['number'] for s in seasons], [1, 2])
        s1_episodes = seasons[0]['episodes']
        self.assertEqual([g['episode'].pk for g in s1_episodes], [self.episode.pk])
        # Events within an episode keep scene order
        self.assertEqual(
            [m.event_id for m in s1_episodes[0]['memberships']],
            [self.event1.pk, self.event2.pk],
        )
        self.assertEqual(seasons[0]['count'], 2)
        self.assertEqual(seasons[1]['count'], 1)
        self.assertEqual(response.context['membership_total'], 3)

    def test_role_badges_have_aria_labels(self):
        response = self._get()
        self.assertContains(response, 'aria-label="Arc role: Start"')
        self.assertContains(response, 'aria-label="Arc role: Climax"')

    def test_season_bridges_single_row_null_fk_excluded(self):
        response = self._get()
        bridges = response.context['season_bridges']
        self.assertEqual([b.pk for b in bridges], [self.bridge.pk])
        self.assertContains(response, 'Season Bridges')

    def test_single_season_arc_gates_bridges_off(self):
        arc2 = ConflictArc.objects.create(
            fabula_uuid='arc_002', title='Solo-season arc',
            description='One season only', arc_type=ArcType.INTERNAL,
            series=self.series,
        )
        ArcEventMembership.objects.create(
            event=self.event1, arc=arc2, episode_ordinal=101)
        response = self.client.get(
            reverse('arc_detail', kwargs={'identifier': 'arc_002'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['season_bridges'], [])
        self.assertNotContains(response, 'Season Bridges')

    def test_involved_characters_rail(self):
        self.arc.involved_characters.add(self.character)
        response = self._get()
        characters = list(response.context['storyline_characters'])
        self.assertEqual([c.pk for c in characters], [self.character.pk])
        self.assertContains(response, 'Involved Characters')


class SeriesScopedStorylineTestMixin(ViewTestMixin):
    """A second series with its own theme/arc, to prove scoping (T-031)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        root = Page.objects.get(depth=1)
        cls.series2 = SeriesIndexPage(
            title='Other Series', slug='other-series', fabula_uuid='series_002',
        )
        root.add_child(instance=cls.series2)
        cls.other_theme = Theme.objects.create(
            fabula_uuid='theme_other', name='Loyalty',
            description='Loyalty under pressure', series=cls.series2,
        )
        cls.other_arc = ConflictArc.objects.create(
            fabula_uuid='arc_other', title='Border Dispute',
            description='A territorial conflict',
            arc_type=ArcType.INTERPERSONAL, series=cls.series2,
        )
        # Junction rows so counts/spans have data in the first series
        ArcEventMembership.objects.create(
            event=cls.event1, arc=cls.arc, episode_ordinal=101)
        ThemeEventMembership.objects.create(
            event=cls.event1, theme=cls.theme, episode_ordinal=101)
        ThemeEventMembership.objects.create(
            event=cls.event2, theme=cls.theme, episode_ordinal=101)


class SeriesScopedIndexViewTest(SeriesScopedStorylineTestMixin, TestCase):
    """T-031: /explore/<series>/themes|arcs/ filter by series FK
    (the routes existed but rendered global data)."""

    def test_series_theme_index_scopes(self):
        response = self.client.get(
            reverse('series_theme_index', kwargs={'series_slug': 'test-series'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [t.pk for t in response.context['themes']], [self.theme.pk])

        response = self.client.get(
            reverse('series_theme_index', kwargs={'series_slug': 'other-series'}))
        self.assertEqual(
            [t.pk for t in response.context['themes']], [self.other_theme.pk])

    def test_series_arc_index_scopes(self):
        response = self.client.get(
            reverse('series_arc_index', kwargs={'series_slug': 'test-series'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [a.pk for a in response.context['arcs']], [self.arc.pk])

        response = self.client.get(
            reverse('series_arc_index', kwargs={'series_slug': 'other-series'}))
        self.assertEqual(
            [a.pk for a in response.context['arcs']], [self.other_arc.pk])

    def test_unknown_series_404s(self):
        response = self.client.get(
            reverse('series_theme_index', kwargs={'series_slug': 'no-such-series'}))
        self.assertEqual(response.status_code, 404)


class StorylineIndexViewTest(SeriesScopedStorylineTestMixin, TestCase):
    """T-031: /explore/<series>/storylines/ interleaves arcs + themes."""

    def test_interleaves_by_event_count(self):
        response = self.client.get(
            reverse('series_storyline_index', kwargs={'series_slug': 'test-series'}))
        self.assertEqual(response.status_code, 200)
        storylines = response.context['storylines']
        # theme has 2 memberships, arc has 1 — count-descending interleave
        self.assertEqual(
            [(s['kind'], s['event_count']) for s in storylines],
            [('theme', 2), ('arc', 1)],
        )
        self.assertEqual(response.context['arc_count'], 1)
        self.assertEqual(response.context['theme_count'], 1)
        # Single-season span computed from episode_ordinal
        self.assertEqual(storylines[0]['season_lo'], 1)
        self.assertEqual(storylines[0]['season_hi'], 1)

    def test_scopes_to_series(self):
        response = self.client.get(
            reverse('series_storyline_index', kwargs={'series_slug': 'other-series'}))
        self.assertEqual(response.status_code, 200)
        pks = {(s['kind'], s['obj'].pk) for s in response.context['storylines']}
        self.assertEqual(
            pks, {('theme', self.other_theme.pk), ('arc', self.other_arc.pk)})

    def test_renders_cards_as_links(self):
        response = self.client.get(
            reverse('series_storyline_index', kwargs={'series_slug': 'test-series'}))
        self.assertContains(response, self.theme.get_absolute_url())
        self.assertContains(response, self.arc.get_absolute_url())
        self.assertContains(response, 'Conflict Arc')
        self.assertContains(response, 'Theme')


class ThemeTimelineViewTest(StorylineTimelineFixtureMixin, TestCase):

    def test_timeline_groups_across_seasons(self):
        response = self.client.get(
            reverse('theme_detail', kwargs={'identifier': 'theme_001'}))
        self.assertEqual(response.status_code, 200)
        seasons = response.context['timeline_seasons']
        self.assertEqual([s['number'] for s in seasons], [1, 2])
        self.assertEqual(response.context['membership_total'], 2)

    def test_theme_bridges_require_both_endpoints_in_theme(self):
        # Theme members are {event1, event3}: the only intact bridge runs
        # event2→event3 (from-endpoint outside the theme) and the
        # event1→event3 row has a null episode FK — so no bridges render.
        response = self.client.get(
            reverse('theme_detail', kwargs={'identifier': 'theme_001'}))
        self.assertEqual(list(response.context['season_bridges']), [])
        self.assertNotContains(response, 'Season Bridges')


# =============================================================================
# LOCATION VIEWS
# =============================================================================

class LocationIndexViewTest(ViewTestMixin, TestCase):

    def test_global_index(self):
        response = self.client.get(reverse('location_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('locations_by_type', response.context)
        self.assertIn('total_count', response.context)

    def test_series_scoped_index(self):
        response = self.client.get(
            reverse('series_location_index', kwargs={'series_slug': 'test-series'})
        )
        self.assertEqual(response.status_code, 200)


class LocationDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('location_detail', kwargs={'identifier': 'loc_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('involvements', response.context)
        self.assertIn('events', response.context)
        self.assertIn('child_locations', response.context)


# =============================================================================
# CHARACTER VIEWS
# =============================================================================

class CharacterIndexViewTest(ViewTestMixin, TestCase):

    def test_global_index(self):
        response = self.client.get(reverse('character_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('characters', response.context)

    def test_series_scoped_index(self):
        response = self.client.get(
            reverse('series_character_index', kwargs={'series_slug': 'test-series'})
        )
        self.assertEqual(response.status_code, 200)


class CharacterDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'agent_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['character'], self.character)
        # Season-paginated participation contract (replaced the old
        # participations_by_importance / emotional_journey context).
        self.assertIn('participations', response.context)
        self.assertIn('available_seasons', response.context)
        self.assertIn('selected_season', response.context)

    def test_by_global_id(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'ger_agent_001'}))
        self.assertEqual(response.status_code, 200)

    def test_by_pk(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': str(self.character.pk)}))
        self.assertEqual(response.status_code, 200)

    def test_by_slug(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'josh-lyman'}))
        self.assertEqual(response.status_code, 200)

    def test_template_aliases(self):
        """page and self should be aliased in context."""
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'agent_001'}))
        self.assertEqual(response.context['page'], self.character)

    def test_not_found(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'nonexistent_xyz'}))
        self.assertEqual(response.status_code, 404)


# =============================================================================
# ORGANIZATION VIEWS
# =============================================================================

class OrganizationIndexViewTest(ViewTestMixin, TestCase):

    def test_global_index(self):
        response = self.client.get(reverse('organization_index'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('organizations', response.context)
        self.assertIn('total_count', response.context)

    def test_series_scoped(self):
        response = self.client.get(
            reverse('series_organization_index', kwargs={'series_slug': 'test-series'})
        )
        self.assertEqual(response.status_code, 200)

    def test_tiered_context(self):
        response = self.client.get(reverse('organization_index'))
        self.assertIn('key_orgs', response.context)
        self.assertIn('active_orgs', response.context)
        self.assertIn('connected_orgs', response.context)
        self.assertIn('minor_orgs', response.context)


class OrganizationDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('organization_detail', kwargs={'identifier': 'org_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('related_characters', response.context)
        self.assertIn('related_events', response.context)

    def test_page_alias(self):
        response = self.client.get(reverse('organization_detail', kwargs={'identifier': 'org_001'}))
        self.assertEqual(response.context['page'], self.org)


# =============================================================================
# OBJECT VIEWS
# =============================================================================

class ObjectIndexViewTest(ViewTestMixin, TestCase):

    def test_global_index(self):
        response = self.client.get(reverse('object_index'))
        self.assertEqual(response.status_code, 200)

    def test_series_scoped(self):
        response = self.client.get(
            reverse('series_object_index', kwargs={'series_slug': 'test-series'})
        )
        self.assertEqual(response.status_code, 200)


class ObjectDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('object_detail', kwargs={'identifier': 'object_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('involvements', response.context)


# =============================================================================
# EVENT VIEWS
# =============================================================================

class EventIndexViewTest(ViewTestMixin, TestCase):

    def test_global_index(self):
        response = self.client.get(reverse('event_index'))
        self.assertEqual(response.status_code, 200)

    def test_series_scoped(self):
        response = self.client.get(
            reverse('series_event_index', kwargs={'series_slug': 'test-series'})
        )
        self.assertEqual(response.status_code, 200)


class EventDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(reverse('event_detail', kwargs={'identifier': 'event_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertIn('participations', response.context)
        self.assertIn('connections', response.context)

    def test_by_global_id(self):
        response = self.client.get(reverse('event_detail', kwargs={'identifier': 'ger_event_001'}))
        self.assertEqual(response.status_code, 200)

    def test_page_alias(self):
        response = self.client.get(reverse('event_detail', kwargs={'identifier': 'event_001'}))
        self.assertEqual(response.context['page'], self.event1)


# =============================================================================
# EPISODE VIEWS
# =============================================================================

class EpisodeDetailViewTest(ViewTestMixin, TestCase):

    def test_by_fabula_uuid(self):
        response = self.client.get(
            reverse('series_episode_detail', kwargs={
                'series_slug': 'test-series',
                'identifier': 'ep_001',
            })
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('events', response.context)
        self.assertEqual(response.context['page'], self.episode)


# =============================================================================
# GRAPH VIEWS
# =============================================================================

class GraphViewTest(ViewTestMixin, TestCase):

    def test_global_graph(self):
        response = self.client.get(reverse('graph_view'))
        self.assertEqual(response.status_code, 200)

    def test_series_graph(self):
        response = self.client.get(
            reverse('series_graph_view', kwargs={'series_slug': 'test-series'})
        )
        self.assertEqual(response.status_code, 200)

    def test_episode_graph(self):
        response = self.client.get(
            reverse('episode_graph', kwargs={'identifier': str(self.episode.pk)})
        )
        self.assertEqual(response.status_code, 200)

    def test_character_graph(self):
        response = self.client.get(
            reverse('character_graph', kwargs={'identifier': str(self.character.pk)})
        )
        self.assertEqual(response.status_code, 200)

    def test_theme_graph(self):
        response = self.client.get(
            reverse('theme_graph', kwargs={'identifier': str(self.theme.pk)})
        )
        self.assertEqual(response.status_code, 200)

    def test_arc_graph(self):
        response = self.client.get(
            reverse('arc_graph', kwargs={'identifier': str(self.arc.pk)})
        )
        self.assertEqual(response.status_code, 200)

    def test_location_graph(self):
        response = self.client.get(
            reverse('location_graph', kwargs={'identifier': str(self.location.pk)})
        )
        self.assertEqual(response.status_code, 200)

    def test_organization_graph(self):
        response = self.client.get(
            reverse('organization_graph', kwargs={'identifier': str(self.org.pk)})
        )
        self.assertEqual(response.status_code, 200)

    def test_object_graph(self):
        response = self.client.get(
            reverse('object_graph', kwargs={'identifier': str(self.obj.pk)})
        )
        self.assertEqual(response.status_code, 200)

    def test_event_graph(self):
        response = self.client.get(
            reverse('event_graph', kwargs={'identifier': str(self.event1.pk)})
        )
        self.assertEqual(response.status_code, 200)


# =============================================================================
# FLEXIBLE IDENTIFIER MIXIN TESTS
# =============================================================================

class FlexibleIdentifierTest(ViewTestMixin, TestCase):
    """Test the FlexibleIdentifierMixin via CharacterDetailView."""

    def test_lookup_by_global_id(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'ger_agent_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['character'], self.character)

    def test_lookup_by_fabula_uuid(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'agent_001'}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['character'], self.character)

    def test_lookup_by_pk(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': str(self.character.pk)}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['character'], self.character)

    def test_lookup_by_slug(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'josh-lyman'}))
        self.assertEqual(response.status_code, 200)

    def test_lookup_embedded_uuid_in_slug(self):
        """Test slug like 'josh-lyman-agent_001' with embedded fabula_uuid."""
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'josh-lyman-agent_001'}))
        self.assertEqual(response.status_code, 200)

    def test_404_for_nonexistent(self):
        response = self.client.get(reverse('character_detail', kwargs={'identifier': 'totally_bogus_xyz'}))
        self.assertEqual(response.status_code, 404)


# =============================================================================
# SEARCH VIEW
# =============================================================================

class SearchViewTest(ViewTestMixin, TestCase):

    def test_search_page_loads(self):
        response = self.client.get(reverse('narrative_search'))
        self.assertEqual(response.status_code, 200)

    def test_search_with_query(self):
        response = self.client.get(reverse('narrative_search'), {'q': 'Josh'})
        self.assertEqual(response.status_code, 200)

    def test_series_scoped_search(self):
        response = self.client.get(
            reverse('series_search', kwargs={'series_slug': 'test-series'}),
            {'q': 'meeting'}
        )
        self.assertEqual(response.status_code, 200)

    def test_search_covers_arcs(self):
        response = self.client.get(reverse('narrative_search'), {'q': 'struggles'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.arc, response.context['arc_results'])

    def test_search_covers_connections(self):
        response = self.client.get(reverse('narrative_search'), {'q': 'confrontation'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.connection, response.context['connection_results'])
