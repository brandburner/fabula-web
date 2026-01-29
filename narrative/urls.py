"""
URL Configuration for Fabula Narrative Web

Multi-Graph URL Structure:
- /explore/                          - Catalog of all narrative graphs
- /explore/<series-slug>/            - Series landing page
- /explore/<series-slug>/characters/ - Characters in that series
- /explore/<series-slug>/graph/      - Full graph visualization

Legacy URLs (global, non-scoped) are preserved for backwards compatibility
and cross-series entity linking via global_id.

URL Strategy:
All entity URLs use a flexible identifier that can be:
- global_id (preferred, e.g., ger_agent_fe6eddb52e5e)
- fabula_uuid (fallback, e.g., agent_256dcf4afffe)
- pk (legacy support, e.g., 3176)

Add to your project's urls.py:
    path('', include('narrative.urls')),
"""

from django.urls import path, include
from . import views


# =============================================================================
# SERIES-SCOPED URL PATTERNS
# =============================================================================
# These patterns are included under /explore/<series_slug>/
# They scope all queries to the specified series.

series_patterns = [
    # Characters
    path('characters/',
         views.CharacterIndexView.as_view(),
         name='series_character_index'),
    path('characters/<str:identifier>/',
         views.CharacterDetailView.as_view(),
         name='series_character_detail'),

    # Organizations
    path('organizations/',
         views.OrganizationIndexView.as_view(),
         name='series_organization_index'),
    path('organizations/<str:identifier>/',
         views.OrganizationDetailView.as_view(),
         name='series_organization_detail'),

    # Objects
    path('objects/',
         views.ObjectIndexView.as_view(),
         name='series_object_index'),
    path('objects/<str:identifier>/',
         views.ObjectDetailView.as_view(),
         name='series_object_detail'),

    # Events
    path('events/',
         views.EventIndexView.as_view(),
         name='series_event_index'),
    path('events/<str:identifier>/',
         views.EventDetailView.as_view(),
         name='series_event_detail'),

    # Connections
    path('connections/',
         views.ConnectionIndexView.as_view(),
         name='series_connection_index'),
    path('connections/<str:identifier>/',
         views.ConnectionDetailView.as_view(),
         name='series_connection_detail'),
    path('connections/type/<str:connection_type>/',
         views.ConnectionTypeView.as_view(),
         name='series_connection_type_list'),

    # Themes
    path('themes/',
         views.ThemeIndexView.as_view(),
         name='series_theme_index'),
    path('themes/<str:identifier>/',
         views.ThemeDetailView.as_view(),
         name='series_theme_detail'),

    # Conflict Arcs
    path('arcs/',
         views.ArcIndexView.as_view(),
         name='series_arc_index'),
    path('arcs/<str:identifier>/',
         views.ArcDetailView.as_view(),
         name='series_arc_detail'),

    # Locations
    path('locations/',
         views.LocationIndexView.as_view(),
         name='series_location_index'),
    path('locations/<str:identifier>/',
         views.LocationDetailView.as_view(),
         name='series_location_detail'),

    # Graph Views (scoped)
    path('graph/',
         views.GraphView.as_view(),
         name='series_graph_view'),
    path('graph/episode/<str:identifier>/',
         views.EpisodeGraphView.as_view(),
         name='series_episode_graph'),
    path('graph/character/<str:identifier>/',
         views.CharacterGraphView.as_view(),
         name='series_character_graph'),
    path('graph/theme/<str:identifier>/',
         views.ThemeGraphView.as_view(),
         name='series_theme_graph'),
    path('graph/arc/<str:identifier>/',
         views.ArcGraphView.as_view(),
         name='series_arc_graph'),
    path('graph/location/<str:identifier>/',
         views.LocationGraphView.as_view(),
         name='series_location_graph'),
    path('graph/organization/<str:identifier>/',
         views.OrganizationGraphView.as_view(),
         name='series_organization_graph'),
    path('graph/object/<str:identifier>/',
         views.ObjectGraphView.as_view(),
         name='series_object_graph'),
    path('graph/event/<str:identifier>/',
         views.EventGraphView.as_view(),
         name='series_event_graph'),

    # Search (scoped to series)
    path('search/',
         views.NarrativeSearchView.as_view(),
         name='series_search'),
]


# =============================================================================
# MAIN URL PATTERNS
# =============================================================================

urlpatterns = [
    # ==========================================================================
    # CATALOG - Graph explorer landing page
    # ==========================================================================
    path('explore/',
         views.CatalogView.as_view(),
         name='catalog'),

    # ==========================================================================
    # SERIES-SCOPED URLS
    # ==========================================================================
    # Series landing page redirects to Wagtail page
    path('explore/<slug:series_slug>/',
         views.SeriesLandingView.as_view(),
         name='series_landing'),
    # Series sub-pages (characters, graph, etc.)
    path('explore/<slug:series_slug>/',
         include(series_patterns)),

    # ==========================================================================
    # LEGACY/GLOBAL URLS (kept for backwards compatibility)
    # These allow cross-series linking via global_id
    # ==========================================================================

    # Characters
    path('characters/',
         views.CharacterIndexView.as_view(),
         name='character_index'),
    path('characters/<str:identifier>/',
         views.CharacterDetailView.as_view(),
         name='character_detail'),

    # Organizations
    path('organizations/',
         views.OrganizationIndexView.as_view(),
         name='organization_index'),
    path('organizations/<str:identifier>/',
         views.OrganizationDetailView.as_view(),
         name='organization_detail'),

    # Objects
    path('objects/',
         views.ObjectIndexView.as_view(),
         name='object_index'),
    path('objects/<str:identifier>/',
         views.ObjectDetailView.as_view(),
         name='object_detail'),

    # Events
    path('events/',
         views.EventIndexView.as_view(),
         name='event_index'),
    path('events/<str:identifier>/',
         views.EventDetailView.as_view(),
         name='event_detail'),

    # Connections
    path('connections/',
         views.ConnectionIndexView.as_view(),
         name='connection_index'),
    path('connections/<str:identifier>/',
         views.ConnectionDetailView.as_view(),
         name='connection_detail'),
    path('connections/type/<str:connection_type>/',
         views.ConnectionTypeView.as_view(),
         name='connection_type_list'),

    # Themes
    path('themes/',
         views.ThemeIndexView.as_view(),
         name='theme_index'),
    path('themes/<str:identifier>/',
         views.ThemeDetailView.as_view(),
         name='theme_detail'),

    # Conflict Arcs
    path('arcs/',
         views.ArcIndexView.as_view(),
         name='arc_index'),
    path('arcs/<str:identifier>/',
         views.ArcDetailView.as_view(),
         name='arc_detail'),

    # Locations
    path('locations/',
         views.LocationIndexView.as_view(),
         name='location_index'),
    path('locations/<str:identifier>/',
         views.LocationDetailView.as_view(),
         name='location_detail'),

    # Graph Views (global)
    path('graph/',
         views.GraphView.as_view(),
         name='graph_view'),
    path('graph/episode/<str:identifier>/',
         views.EpisodeGraphView.as_view(),
         name='episode_graph'),
    path('graph/character/<str:identifier>/',
         views.CharacterGraphView.as_view(),
         name='character_graph'),
    path('graph/theme/<str:identifier>/',
         views.ThemeGraphView.as_view(),
         name='theme_graph'),
    path('graph/arc/<str:identifier>/',
         views.ArcGraphView.as_view(),
         name='arc_graph'),
    path('graph/location/<str:identifier>/',
         views.LocationGraphView.as_view(),
         name='location_graph'),
    path('graph/organization/<str:identifier>/',
         views.OrganizationGraphView.as_view(),
         name='organization_graph'),
    path('graph/object/<str:identifier>/',
         views.ObjectGraphView.as_view(),
         name='object_graph'),
    path('graph/event/<str:identifier>/',
         views.EventGraphView.as_view(),
         name='event_graph'),

    # Search (global)
    path('search/',
         views.NarrativeSearchView.as_view(),
         name='narrative_search'),
]
