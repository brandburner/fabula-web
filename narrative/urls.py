"""
URL Configuration for Fabula Narrative Web

These URLs handle non-Page views:
- Narrative connections (first-class content)
- Themes (snippet detail views)
- Conflict arcs (snippet detail views)
- Graph visualization
- Search

Add to your project's urls.py:
    path('', include('narrative.urls')),
"""

from django.urls import path
from . import views


urlpatterns = [
    # Connections
    path('connections/', 
         views.ConnectionIndexView.as_view(), 
         name='connection_index'),
    path('connections/<int:pk>/', 
         views.ConnectionDetailView.as_view(), 
         name='connection_detail'),
    path('connections/type/<str:connection_type>/', 
         views.ConnectionTypeView.as_view(), 
         name='connection_type_list'),
    
    # Themes
    path('themes/', 
         views.ThemeIndexView.as_view(), 
         name='theme_index'),
    path('themes/<int:pk>/', 
         views.ThemeDetailView.as_view(), 
         name='theme_detail'),
    
    # Conflict Arcs
    path('arcs/',
         views.ArcIndexView.as_view(),
         name='arc_index'),
    path('arcs/<int:pk>/',
         views.ArcDetailView.as_view(),
         name='arc_detail'),

    # Locations
    path('locations/',
         views.LocationIndexView.as_view(),
         name='location_index'),
    path('locations/<int:pk>/',
         views.LocationDetailView.as_view(),
         name='location_detail'),

    # Graph visualization - scoped views (fast, focused)
    path('graph/episode/<int:pk>/',
         views.EpisodeGraphView.as_view(),
         name='episode_graph'),
    path('graph/character/<int:pk>/',
         views.CharacterGraphView.as_view(),
         name='character_graph'),
    path('graph/theme/<int:pk>/',
         views.ThemeGraphView.as_view(),
         name='theme_graph'),
    path('graph/arc/<int:pk>/',
         views.ArcGraphView.as_view(),
         name='arc_graph'),

    # Graph landing page (replaces broken full graph)
    path('graph/',
         views.GraphView.as_view(),
         name='graph_view'),
    
    # Search
    path('search/', 
         views.NarrativeSearchView.as_view(), 
         name='narrative_search'),
]


# =============================================================================
# WAGTAIL HOOKS
# =============================================================================

"""
Add these hooks to wagtail_hooks.py to integrate with Wagtail admin:

from wagtail import hooks
from wagtail.admin.menu import MenuItem

@hooks.register('register_admin_menu_item')
def register_connections_menu():
    return MenuItem(
        'Connections', 
        '/admin/narrative/narrativeconnection/',
        icon_name='link',
        order=500
    )
"""
