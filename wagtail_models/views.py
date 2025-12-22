"""
Custom Views for Fabula Narrative Web

These views handle display of models that are not Wagtail Pages:
- NarrativeConnection (Django model)
- Theme (Wagtail snippet)
- ConflictArc (Wagtail snippet)

URL patterns should be added to urls.py.
"""

from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView, DetailView

from .models import (
    NarrativeConnection, Theme, ConflictArc, 
    EventPage, CharacterPage,
    ConnectionType
)


# =============================================================================
# NARRATIVE CONNECTIONS
# =============================================================================

class ConnectionIndexView(ListView):
    """
    Browse all narrative connections, grouped by type.
    """
    model = NarrativeConnection
    template_name = 'narrative/connection_index.html'
    context_object_name = 'connections'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Group connections by type
        connections_by_type = {}
        for conn_type in ConnectionType.choices:
            connections = NarrativeConnection.objects.filter(
                connection_type=conn_type[0]
            ).select_related('from_event', 'to_event')[:10]
            
            if connections.exists():
                connections_by_type[conn_type] = connections
        
        context['connections_by_type'] = connections_by_type
        context['total_count'] = NarrativeConnection.objects.count()
        return context


class ConnectionDetailView(DetailView):
    """
    View a single narrative connection as first-class content.
    """
    model = NarrativeConnection
    template_name = 'narrative/connection_detail.html'
    context_object_name = 'connection'


class ConnectionTypeView(ListView):
    """
    View all connections of a specific type.
    """
    model = NarrativeConnection
    template_name = 'narrative/connection_type_list.html'
    context_object_name = 'connections'
    paginate_by = 20
    
    def get_queryset(self):
        conn_type = self.kwargs['connection_type'].upper()
        return NarrativeConnection.objects.filter(
            connection_type=conn_type
        ).select_related('from_event', 'to_event', 
                        'from_event__episode', 'to_event__episode')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conn_type = self.kwargs['connection_type'].upper()
        context['connection_type'] = conn_type
        context['connection_type_display'] = conn_type.replace('_', ' ').title()
        return context


# =============================================================================
# THEMES
# =============================================================================

class ThemeIndexView(ListView):
    """
    Browse all themes, ordered by event count.
    """
    model = Theme
    template_name = 'narrative/theme_index.html'
    context_object_name = 'themes'
    
    def get_queryset(self):
        from django.db.models import Count
        return Theme.objects.annotate(
            event_count=Count('events')
        ).order_by('-event_count')


class ThemeDetailView(DetailView):
    """
    View a single theme with all events that exemplify it.
    """
    model = Theme
    template_name = 'narrative/theme_detail.html'
    context_object_name = 'theme'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get events for this theme
        context['events'] = self.object.events.all().select_related(
            'episode', 'location'
        ).order_by('episode__episode_number', 'scene_sequence')
        
        # Get other themes for exploration
        context['other_themes'] = Theme.objects.exclude(
            pk=self.object.pk
        ).annotate(
            event_count=Count('events')
        ).order_by('-event_count')[:8]
        
        return context


# =============================================================================
# CONFLICT ARCS
# =============================================================================

class ArcIndexView(ListView):
    """
    Browse all conflict arcs.
    """
    model = ConflictArc
    template_name = 'narrative/arc_index.html'
    context_object_name = 'arcs'
    
    def get_queryset(self):
        from django.db.models import Count
        return ConflictArc.objects.annotate(
            event_count=Count('events')
        ).order_by('-event_count')


class ArcDetailView(DetailView):
    """
    View a single conflict arc with all related events.
    """
    model = ConflictArc
    template_name = 'narrative/arc_detail.html'
    context_object_name = 'arc'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['events'] = self.object.events.all().select_related(
            'episode', 'location'
        ).order_by('episode__episode_number', 'scene_sequence')
        
        return context


# =============================================================================
# GRAPH VIEW (Interactive visualization)
# =============================================================================

class GraphView(ListView):
    """
    Interactive graph visualization of narrative connections.
    Returns JSON data for the graph when requested via AJAX.
    """
    model = EventPage
    template_name = 'narrative/graph_view.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get all events and connections for the graph
        events = EventPage.objects.live().select_related('episode')
        connections = NarrativeConnection.objects.all().select_related(
            'from_event', 'to_event'
        )
        
        # Prepare graph data
        nodes = []
        for event in events:
            nodes.append({
                'id': str(event.pk),
                'label': event.title[:30] + '...' if len(event.title) > 30 else event.title,
                'url': event.url,
                'episode': f"S{event.episode.get_parent().specific.season_number}E{event.episode.episode_number}",
            })
        
        edges = []
        for conn in connections:
            edges.append({
                'from': str(conn.from_event_id),
                'to': str(conn.to_event_id),
                'type': conn.connection_type,
                'label': conn.get_connection_type_display(),
                'strength': conn.strength,
            })
        
        context['graph_data'] = {
            'nodes': nodes,
            'edges': edges,
        }
        
        return context


# =============================================================================
# SEARCH VIEW
# =============================================================================

class NarrativeSearchView(ListView):
    """
    Search across events, characters, and themes.
    """
    template_name = 'narrative/search_results.html'
    context_object_name = 'results'
    paginate_by = 20
    
    def get_queryset(self):
        query = self.request.GET.get('q', '')
        
        if not query:
            return EventPage.objects.none()
        
        # Search events
        return EventPage.objects.live().search(query)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        query = self.request.GET.get('q', '')
        context['query'] = query
        
        if query:
            # Also search characters
            context['character_results'] = CharacterPage.objects.live().search(query)[:5]
            
            # And themes
            context['theme_results'] = Theme.objects.filter(
                name__icontains=query
            ) | Theme.objects.filter(
                description__icontains=query
            )
        
        return context
