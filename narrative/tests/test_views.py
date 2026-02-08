"""
Tests for narrative views - catalog, detail, index, and graph views.
"""
from django.test import TestCase, Client
from django.urls import reverse

from wagtail.models import Page

from narrative.models import (
    ConnectionType, ConnectionStrength, CharacterType, ImportanceTier, ArcType,
    Theme, ConflictArc, Location,
    SeriesIndexPage, SeasonPage, EpisodePage, CharacterPage,
    OrganizationPage, OrganizationIndexPage, ObjectPage, ObjectIndexPage,
    EventPage, EventIndexPage, CharacterIndexPage,
    EventParticipation, NarrativeConnection,
    LocationInvolvement, ObjectInvolvement, OrganizationInvolvement,
)


class ViewTestMixin:
    """Mixin to create test data for view tests."""

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

    def test_catalog_home(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('series_list', response.context)

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
        self.assertIn('participations_by_importance', response.context)
        self.assertIn('emotional_journey', response.context)

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
