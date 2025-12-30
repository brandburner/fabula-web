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

from django.db.models import Q

from .models import (
    NarrativeConnection, Theme, ConflictArc, Location,
    EventPage, CharacterPage, EpisodePage, EventParticipation,
    ConnectionType, LocationInvolvement
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
# LOCATIONS
# =============================================================================

class LocationIndexView(ListView):
    """
    Browse all locations, organized by type.
    """
    model = Location
    template_name = 'narrative/location_index.html'
    context_object_name = 'locations'

    def get_queryset(self):
        from django.db.models import Count
        # Count events via LocationInvolvement (rich involvement data)
        return Location.objects.annotate(
            event_count=Count('event_involvements')
        ).order_by('-event_count')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Group locations by type
        locations_by_type = {}
        for location in self.get_queryset():
            loc_type = location.location_type or 'Other'
            if loc_type not in locations_by_type:
                locations_by_type[loc_type] = []
            locations_by_type[loc_type].append(location)

        context['locations_by_type'] = locations_by_type
        context['total_count'] = Location.objects.count()
        return context


class LocationDetailView(DetailView):
    """
    View a single location with all events that occur there.
    Shows both simple FK events and rich involvement events.
    """
    model = Location
    template_name = 'narrative/location_detail.html'
    context_object_name = 'location'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get rich location involvements
        involvements = LocationInvolvement.objects.filter(
            location=self.object
        ).select_related('event', 'event__episode').order_by(
            'event__episode__episode_number',
            'event__scene_sequence'
        )
        context['involvements'] = involvements

        # Get ALL events at this location (from both FK and involvements)
        involvement_event_ids = involvements.values_list('event_id', flat=True)
        context['events'] = EventPage.objects.live().filter(
            Q(location=self.object) | Q(pk__in=involvement_event_ids)
        ).distinct().select_related('episode').order_by(
            'episode__episode_number', 'scene_sequence'
        )

        # Get child locations
        context['child_locations'] = Location.objects.filter(
            parent_location=self.object
        )

        return context


# =============================================================================
# GRAPH VIEW (Interactive visualization)
# =============================================================================

class ScopedGraphMixin:
    """
    Mixin for scoped graph views that limits nodes/edges to a manageable set.
    Provides common graph data formatting logic.
    """
    template_name = 'narrative/graph_view.html'

    def get_graph_title(self):
        """Override in subclasses to provide a descriptive title."""
        return "Narrative Graph"

    def get_back_url(self):
        """Override to provide a back link to the source page."""
        return None

    def get_events_queryset(self):
        """Override to return the filtered events for this scope."""
        raise NotImplementedError

    def build_graph_data(self, events):
        """Build graph nodes and edges from a queryset of events."""
        event_ids = set(events.values_list('pk', flat=True))

        nodes = []
        for event in events.select_related('episode'):
            try:
                season = event.episode.get_parent().specific
                ep_label = f"S{season.season_number}E{event.episode.episode_number}"
            except (AttributeError, TypeError):
                ep_label = f"E{event.episode.episode_number}"

            nodes.append({
                'id': str(event.pk),
                'label': event.title[:30] + '...' if len(event.title) > 30 else event.title,
                'url': event.url,
                'episode': ep_label,
            })

        # Only include connections where BOTH events are in scope
        connections = NarrativeConnection.objects.filter(
            from_event_id__in=event_ids,
            to_event_id__in=event_ids
        ).select_related('from_event', 'to_event')

        edges = []
        for conn in connections:
            edges.append({
                'from': str(conn.from_event_id),
                'to': str(conn.to_event_id),
                'type': conn.connection_type,
                'label': conn.get_connection_type_display(),
                'strength': conn.strength,
            })

        return {'nodes': nodes, 'edges': edges}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        events = self.get_events_queryset()
        context['graph_data'] = self.build_graph_data(events)
        context['graph_title'] = self.get_graph_title()
        context['back_url'] = self.get_back_url()
        return context


class EpisodeGraphView(ScopedGraphMixin, DetailView):
    """
    Graph of events within a single episode.
    Typically ~20-40 nodes, very fast.
    """
    model = EpisodePage

    def get_graph_title(self):
        episode = self.get_object()
        try:
            season = episode.get_parent().specific
            return f"S{season.season_number}E{episode.episode_number}: {episode.title}"
        except (AttributeError, TypeError):
            return f"Episode: {episode.title}"

    def get_back_url(self):
        return self.get_object().url

    def get_events_queryset(self):
        episode = self.get_object()
        return EventPage.objects.live().filter(episode=episode)


class CharacterGraphView(ScopedGraphMixin, DetailView):
    """
    Graph of events a character participates in.
    Shows the character's journey through the narrative.
    """
    model = CharacterPage

    def get_graph_title(self):
        return f"{self.get_object().title}'s Journey"

    def get_back_url(self):
        return self.get_object().url

    def get_events_queryset(self):
        character = self.get_object()
        event_ids = EventParticipation.objects.filter(
            character=character
        ).values_list('event_id', flat=True)
        return EventPage.objects.live().filter(pk__in=event_ids)


class ThemeGraphView(ScopedGraphMixin, DetailView):
    """
    Graph of events tagged with a specific theme.
    """
    model = Theme

    def get_graph_title(self):
        return f"Theme: {self.get_object().name}"

    def get_back_url(self):
        return f"/themes/{self.get_object().pk}/"

    def get_events_queryset(self):
        theme = self.get_object()
        return EventPage.objects.live().filter(themes=theme)


class ArcGraphView(ScopedGraphMixin, DetailView):
    """
    Graph of events in a conflict arc.
    """
    model = ConflictArc

    def get_graph_title(self):
        return f"Arc: {self.get_object().title}"

    def get_back_url(self):
        return f"/arcs/{self.get_object().pk}/"

    def get_events_queryset(self):
        arc = self.get_object()
        return EventPage.objects.live().filter(arcs=arc)


class GraphView(ListView):
    """
    Graph landing page with links to scoped graph views.
    Shows sample items from each category for direct graph access.
    """
    model = EventPage
    template_name = 'narrative/graph_landing.html'

    def get_context_data(self, **kwargs):
        from django.db.models import Count

        context = super().get_context_data(**kwargs)
        # Provide stats for the landing page
        context['event_count'] = EventPage.objects.live().count()
        context['connection_count'] = NarrativeConnection.objects.count()

        # Sample episodes (most recent with events)
        context['sample_episodes'] = EpisodePage.objects.live().annotate(
            event_count=Count('events')
        ).filter(event_count__gt=0).order_by('-event_count')[:5]

        # Sample characters (most connected)
        context['sample_characters'] = CharacterPage.objects.live().annotate(
            event_count=Count('participations')
        ).filter(event_count__gt=0).order_by('-event_count')[:5]

        # Sample themes (most events)
        context['sample_themes'] = Theme.objects.annotate(
            event_count=Count('events')
        ).filter(event_count__gt=0).order_by('-event_count')[:5]

        # Sample arcs (most events)
        context['sample_arcs'] = ConflictArc.objects.annotate(
            event_count=Count('events')
        ).filter(event_count__gt=0).order_by('-event_count')[:5]

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
