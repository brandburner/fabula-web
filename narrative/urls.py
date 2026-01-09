"""
URL Configuration for Fabula Narrative Web

These URLs handle non-Page views using global_id-based stable URLs:
- Narrative connections (first-class content)
- Themes (snippet detail views)
- Conflict arcs (snippet detail views)
- Locations (snippet detail views)
- Characters, Organizations, Objects, Events (Wagtail pages via global_id)
- Graph visualization
- Search

URL Strategy:
All entity URLs use a flexible identifier that can be:
- global_id (preferred, e.g., ger_agent_fe6eddb52e5e)
- fabula_uuid (fallback, e.g., agent_256dcf4afffe)
- pk (legacy support, e.g., 3176)

Add to your project's urls.py:
    path('', include('narrative.urls')),
"""

from django.urls import path
from . import views


urlpatterns = [
    # ==========================================================================
    # WAGTAIL PAGE TYPES - served via global_id for stable cross-season URLs
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

    # ==========================================================================
    # SNIPPETS - served via global_id for stable cross-season URLs
    # ==========================================================================

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

    # ==========================================================================
    # GRAPH VIEWS - scoped visualizations using global_id
    # ==========================================================================

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

    # Graph landing page
    path('graph/',
         views.GraphView.as_view(),
         name='graph_view'),

    # ==========================================================================
    # SEARCH
    # ==========================================================================

    path('search/',
         views.NarrativeSearchView.as_view(),
         name='narrative_search'),
]
