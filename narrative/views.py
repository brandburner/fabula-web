"""
Custom Views for Fabula Narrative Web

All entity URLs use a flexible identifier that can be:
- global_id (preferred, e.g., ger_agent_fe6eddb52e5e) - stable across seasons
- fabula_uuid (fallback, e.g., agent_256dcf4afffe) - from Neo4j
- pk (legacy support, e.g., 3176) - database primary key

This enables cross-season entity linking where the same character/location/etc.
can be addressed by a single stable URL regardless of which season's data
was imported first.

Multi-Graph Support:
Views support series scoping via SeriesScopedMixin, enabling URLs like:
- /explore/ (catalog of all graphs)
- /explore/west-wing/characters/ (characters in West Wing)
- /explore/star-trek-tng/graph/ (Star Trek TNG graph)
"""

import json

from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, TemplateView, View

from django.db import models
from django.db.models import Q, Count

from .models import (
    NarrativeConnection, Theme, ConflictArc, Location,
    EventPage, CharacterPage, EpisodePage, EventParticipation,
    ConnectionType, LocationInvolvement, OrganizationInvolvement,
    OrganizationPage, ObjectPage, ObjectInvolvement,
    CharacterIndexPage, OrganizationIndexPage, ObjectIndexPage, EventIndexPage,
    SeriesIndexPage
)


# =============================================================================
# FLEXIBLE IDENTIFIER LOOKUP MIXIN
# =============================================================================

class FlexibleIdentifierMixin:
    """
    Mixin that looks up objects by global_id, fabula_uuid, slug, or pk.

    This enables stable cross-season URLs where entities can be addressed by:
    - global_id: Cross-season identity (e.g., ger_agent_fe6eddb52e5e)
    - fabula_uuid: Season-specific Neo4j ID (e.g., agent_256dcf4afffe)
    - slug: Wagtail page slug (for Page subclasses)
    - pk: Database primary key (e.g., 3176)

    The identifier is extracted from self.kwargs['identifier'].
    """

    def get_object(self, queryset=None):
        """Look up object by global_id, fabula_uuid, slug, or pk."""
        if queryset is None:
            queryset = self.get_queryset()

        identifier = self.kwargs.get('identifier', '')

        # Try global_id first (preferred for cross-season links)
        if identifier.startswith('ger_'):
            try:
                return queryset.get(global_id=identifier)
            except self.model.DoesNotExist:
                pass

        # Try fabula_uuid (starts with entity type prefix)
        # Note: ep_ and sea_ are the actual Neo4j export prefixes for episodes/seasons
        entity_prefixes = ('agent_', 'event_', 'theme_', 'arc_', 'location_',
                          'org_', 'object_', 'conn_', 'episode_', 'season_',
                          'ep_', 'sea_', 'cand_evt_')
        if any(identifier.startswith(prefix) for prefix in entity_prefixes):
            try:
                return queryset.get(fabula_uuid=identifier)
            except self.model.DoesNotExist:
                pass

        # Try pk (numeric)
        if identifier.isdigit():
            try:
                return queryset.get(pk=int(identifier))
            except self.model.DoesNotExist:
                pass

        # Try slug (for Wagtail Page subclasses)
        if hasattr(self.model, 'slug'):
            try:
                return queryset.get(slug=identifier)
            except self.model.DoesNotExist:
                pass

        # Try fabula_uuid embedded in slug (e.g., "abbey-bartlet-agent_5347405cc1de")
        # Extract the fabula_uuid suffix if present
        for prefix in entity_prefixes:
            if prefix in identifier:
                fabula_uuid_start = identifier.find(prefix)
                if fabula_uuid_start >= 0:
                    potential_uuid = identifier[fabula_uuid_start:]
                    try:
                        return queryset.get(fabula_uuid=potential_uuid)
                    except self.model.DoesNotExist:
                        pass

        # If nothing matched, try all available fields as a last resort
        lookup = Q(global_id=identifier) | Q(fabula_uuid=identifier)
        if hasattr(self.model, 'slug'):
            lookup |= Q(slug=identifier)
        if identifier.isdigit():
            lookup |= Q(pk=int(identifier))

        try:
            return queryset.get(lookup)
        except self.model.DoesNotExist:
            raise Http404(f"No {self.model.__name__} found with identifier: {identifier}")


# =============================================================================
# SERIES SCOPING MIXIN
# =============================================================================

class SeriesScopedMixin:
    """
    Mixin that scopes queries to the current series from URL slug.

    For URLs like /explore/west-wing/characters/, this extracts 'west-wing'
    and filters all queries to only return content within that series.

    Works with:
    - Wagtail Pages: filters by ancestry (descendants of series)
    - Snippets with series FK: filters by series foreign key
    - Models without series: returns unfiltered (graceful fallback)
    """

    def get_series(self):
        """Get the current series from URL kwargs or return first available."""
        series_slug = self.kwargs.get('series_slug')
        if series_slug:
            return get_object_or_404(SeriesIndexPage.objects.live(), slug=series_slug)
        # Fallback to first series if no slug provided
        return SeriesIndexPage.objects.live().first()

    def get_series_queryset(self, base_queryset):
        """
        Filter a queryset to the current series.

        For Wagtail Pages, uses descendant_of() for page tree filtering.
        For snippets with series FK, uses direct filter.
        """
        series = self.get_series()
        if not series:
            return base_queryset

        model = base_queryset.model

        # For Wagtail Page subclasses, filter by ancestry
        if hasattr(model, 'get_parent'):
            return base_queryset.descendant_of(series)

        # For snippets with series FK
        if hasattr(model, 'series'):
            return base_queryset.filter(series=series)

        return base_queryset

    def get_context_data(self, **kwargs):
        """Add series context to all templates."""
        context = super().get_context_data(**kwargs)
        context['current_series'] = self.get_series()
        return context


# =============================================================================
# CATALOG VIEW (Graph Explorer Landing)
# =============================================================================

class CatalogView(TemplateView):
    """
    Catalog page showing all available narrative graphs.

    URL: /explore/

    Displays cards for each series with stats (event count, character count, etc.)
    to help users choose which graph to explore.
    """
    template_name = 'narrative/catalog.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get all live series with stats
        series_list = SeriesIndexPage.objects.live().annotate(
            # Count events via the page tree (events are under series/season/episode)
            # This requires a subquery approach for accurate counts
        ).order_by('title')

        # Compute stats for each series
        series_with_stats = []
        for series in series_list:
            # Get events under this series (via episode ancestry)
            episodes = EpisodePage.objects.live().descendant_of(series)
            event_count = EventPage.objects.live().filter(
                episode__in=episodes
            ).count()

            # Get characters under this series
            character_count = CharacterPage.objects.live().descendant_of(series).count()

            # Get connections between events in this series
            event_ids = EventPage.objects.live().filter(
                episode__in=episodes
            ).values_list('pk', flat=True)
            connection_count = NarrativeConnection.objects.filter(
                from_event_id__in=event_ids
            ).count()

            # Get season count
            season_count = series.get_children().live().count()

            series_with_stats.append({
                'series': series,
                'event_count': event_count,
                'character_count': character_count,
                'connection_count': connection_count,
                'season_count': season_count,
            })

        context['series_list'] = series_with_stats
        context['total_series'] = len(series_with_stats)
        return context


class SeriesLandingView(View):
    """
    Redirect from /explore/<series_slug>/ to the Wagtail series page.

    This bridges the Django URL structure with Wagtail's page tree,
    allowing /explore/west-wing/ to redirect to /the-west-wing/.
    """

    def get(self, request, series_slug):
        series = get_object_or_404(SeriesIndexPage.objects.live(), slug=series_slug)
        return redirect(series.url)


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


class ConnectionDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single narrative connection as first-class content.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
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


class ThemeDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single theme with all events that exemplify it.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = Theme
    template_name = 'narrative/theme_detail.html'
    context_object_name = 'theme'
    
    def get_context_data(self, **kwargs):
        from django.db.models import Count
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


class ArcDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single conflict arc with all related events.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
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


class LocationDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single location with all events that occur there.
    Shows both simple FK events and rich involvement events.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
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
# WAGTAIL PAGE VIEWS (served via global_id for stable URLs)
# =============================================================================

class CharacterIndexView(ListView):
    """Browse all characters, ordered by importance tier and appearance count."""
    model = CharacterPage
    template_name = 'narrative/character_index_page.html'
    context_object_name = 'characters'

    def get_queryset(self):
        from django.db.models import Case, When, Value, IntegerField
        # Custom ordering: anchor=0, planet=1, asteroid=2 (ascending = anchor first)
        tier_order = Case(
            When(importance_tier='anchor', then=Value(0)),
            When(importance_tier='planet', then=Value(1)),
            When(importance_tier='asteroid', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
        return CharacterPage.objects.live().annotate(
            tier_order=tier_order
        ).order_by('tier_order', '-appearance_count', 'canonical_name')


class CharacterDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single character with their event participations and journey.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = CharacterPage
    template_name = 'narrative/character_page.html'
    context_object_name = 'character'

    def get_queryset(self):
        return CharacterPage.objects.live()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        character = self.object

        # Alias 'page' for template compatibility with Wagtail conventions
        context['page'] = character
        context['self'] = character

        # Get participations grouped by importance
        context['participations_by_importance'] = self._get_participations_grouped()

        # Get emotional journey
        context['emotional_journey'] = character.get_emotional_journey()

        return context

    def _get_participations_grouped(self):
        """Group participations by importance level."""
        all_parts = EventParticipation.objects.filter(
            character=self.object
        ).select_related('event', 'event__episode')

        grouped = {'primary': [], 'secondary': [], 'mentioned': [], 'other': []}
        for p in all_parts:
            importance = (p.importance or '').lower().strip()
            if importance in grouped:
                grouped[importance].append(p)
            elif importance:
                grouped['other'].append(p)
            else:
                grouped['primary'].append(p)

        return grouped


class OrganizationIndexView(ListView):
    """Browse all organizations."""
    model = OrganizationPage
    template_name = 'narrative/organization_index_page.html'
    context_object_name = 'organizations'

    def get_queryset(self):
        return OrganizationPage.objects.live().order_by('canonical_name')


class OrganizationDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single organization with related characters and events.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = OrganizationPage
    template_name = 'narrative/organization_page.html'
    context_object_name = 'organization'

    def get_queryset(self):
        return OrganizationPage.objects.live()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        org = self.object

        # Alias 'page' for template compatibility
        context['page'] = org
        context['self'] = org

        # Get related data
        context['related_characters'] = org.get_related_characters()
        context['related_events'] = org.get_related_events()

        return context


class ObjectIndexView(ListView):
    """Browse all narrative objects."""
    model = ObjectPage
    template_name = 'narrative/object_index_page.html'
    context_object_name = 'objects'

    def get_queryset(self):
        return ObjectPage.objects.live().annotate(
            involvement_count=Count('event_involvements')
        ).order_by('-involvement_count', 'canonical_name')


class ObjectDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single object with its event involvements.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = ObjectPage
    template_name = 'narrative/object_page.html'
    context_object_name = 'object'

    def get_queryset(self):
        return ObjectPage.objects.live()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        obj = self.object

        # Alias 'page' for template compatibility
        context['page'] = obj
        context['self'] = obj

        # Get involvements
        context['involvements'] = obj.get_involvements()

        return context


class EventIndexView(ListView):
    """Browse all events, organized by episode."""
    model = EventPage
    template_name = 'narrative/event_index_page.html'
    context_object_name = 'events'

    def get_queryset(self):
        return EventPage.objects.live().select_related(
            'episode', 'location'
        ).order_by('episode__path', 'scene_sequence')


class EventDetailView(FlexibleIdentifierMixin, DetailView):
    """
    View a single event with participations and connections.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = EventPage
    template_name = 'narrative/event_page.html'
    context_object_name = 'event'

    def get_queryset(self):
        return EventPage.objects.live().select_related('episode', 'location')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event = self.object

        # Alias 'page' for template compatibility
        context['page'] = event
        context['self'] = event

        # Get participations grouped by importance
        context['participations'] = event.get_participations_by_importance()

        # Get connections
        context['connections'] = event.get_all_connections()

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
        """
        Build graph with multi-type nodes and real relationship edges.

        Node types:
        - event: Narrative events (central nodes)
        - character: Characters who participate in events
        - location: Locations where events occur
        - organization: Organizations involved in events

        Edge types (from LPG schema):
        - PARTICIPATED_AS: Character → Event
        - IN_EVENT: Location → Event
        - INVOLVED_WITH: Organization → Event
        - Narrative connections (CAUSAL, etc.): Event → Event
        """
        event_ids = set(events.values_list('pk', flat=True))
        event_list = list(events.select_related('episode', 'location'))

        nodes = []
        edges = []
        seen_nodes = set()  # Track node IDs to avoid duplicates

        # =================================================================
        # 1. EVENT NODES
        # =================================================================
        for event in event_list:
            try:
                season = event.episode.get_parent().specific
                ep_label = f"S{season.season_number}E{event.episode.episode_number}"
            except (AttributeError, TypeError):
                ep_label = f"E{event.episode.episode_number}" if event.episode else "Unknown"

            node_id = f"event_{event.pk}"
            seen_nodes.add(node_id)

            nodes.append({
                'id': node_id,
                'nodeType': 'event',
                'label': event.title[:40] + '...' if len(event.title) > 40 else event.title,
                'fullTitle': event.title,
                'url': event.get_absolute_url(),
                'episode': ep_label,
                'sceneSequence': event.scene_sequence or 0,
            })

        # =================================================================
        # 2. CHARACTER NODES + PARTICIPATED_AS EDGES
        # =================================================================
        participations = EventParticipation.objects.filter(
            event_id__in=event_ids
        ).select_related('character')

        for p in participations:
            char = p.character
            char_node_id = f"character_{char.pk}"

            # Add character node if not seen
            if char_node_id not in seen_nodes:
                seen_nodes.add(char_node_id)
                nodes.append({
                    'id': char_node_id,
                    'nodeType': 'character',
                    'label': char.title,
                    'fullTitle': char.title,
                    'url': char.get_absolute_url(),
                    # Graph Gravity tier data
                    'tier': char.importance_tier,
                    'episodeCount': char.episode_count,
                    'relationshipCount': char.relationship_count,
                    # Pre-computed 3D positions (if available)
                    'x': char.graph_x if char.graph_x != 0 else None,
                    'y': char.graph_y if char.graph_y != 0 else None,
                    'z': char.graph_z if char.graph_z != 0 else None,
                    'community': char.graph_community,
                })

            # Add PARTICIPATED_AS edge (character → event)
            event_node_id = f"event_{p.event_id}"
            edges.append({
                'from': char_node_id,
                'to': event_node_id,
                'type': 'PARTICIPATED_AS',
                'label': p.emotional_state[:30] if p.emotional_state else 'Participates',
                'description': p.emotional_state or '',
                'strength': 'strong',
                # Note: No 'pk' - this is a participation, not a clickable connection
            })

        # =================================================================
        # 3. LOCATION NODES + IN_EVENT EDGES
        # =================================================================
        # From LocationInvolvement (rich data)
        location_involvements = LocationInvolvement.objects.filter(
            event_id__in=event_ids
        ).select_related('location')

        for inv in location_involvements:
            loc = inv.location
            loc_node_id = f"location_{loc.pk}"

            if loc_node_id not in seen_nodes:
                seen_nodes.add(loc_node_id)
                nodes.append({
                    'id': loc_node_id,
                    'nodeType': 'location',
                    'label': loc.canonical_name,
                    'fullTitle': loc.canonical_name,
                    'url': loc.get_absolute_url(),  # Now served via custom view
                })

            event_node_id = f"event_{inv.event_id}"
            edges.append({
                'from': loc_node_id,
                'to': event_node_id,
                'type': 'IN_EVENT',
                'label': inv.functional_role[:30] if inv.functional_role else 'Setting',
                'description': inv.observed_atmosphere or inv.description_of_involvement or '',
                'strength': 'medium',
                # Note: No 'pk' - this is a location involvement, not a clickable connection
            })

        # Also from primary location FK (if not already covered)
        for event in event_list:
            if event.location_id:
                loc = event.location
                loc_node_id = f"location_{loc.pk}"
                event_node_id = f"event_{event.pk}"

                # Add location node if not seen
                if loc_node_id not in seen_nodes:
                    seen_nodes.add(loc_node_id)
                    nodes.append({
                        'id': loc_node_id,
                        'nodeType': 'location',
                        'label': loc.canonical_name,
                        'fullTitle': loc.canonical_name,
                        'url': loc.get_absolute_url(),
                    })

                # Check if edge already exists from LocationInvolvement
                edge_exists = any(
                    e['from'] == loc_node_id and e['to'] == event_node_id
                    for e in edges
                )
                if not edge_exists:
                    edges.append({
                        'from': loc_node_id,
                        'to': event_node_id,
                        'type': 'IN_EVENT',
                        'label': 'Primary Location',
                        'description': '',
                        'strength': 'medium',
                        'pk': None,
                    })

        # =================================================================
        # 4. ORGANIZATION NODES + INVOLVED_WITH EDGES
        # =================================================================
        org_involvements = OrganizationInvolvement.objects.filter(
            event_id__in=event_ids
        ).select_related('organization')

        for inv in org_involvements:
            org = inv.organization
            org_node_id = f"organization_{org.pk}"

            if org_node_id not in seen_nodes:
                seen_nodes.add(org_node_id)
                nodes.append({
                    'id': org_node_id,
                    'nodeType': 'organization',
                    'label': org.title,
                    'fullTitle': org.title,
                    'url': org.get_absolute_url(),
                })

            event_node_id = f"event_{inv.event_id}"
            edges.append({
                'from': org_node_id,
                'to': event_node_id,
                'type': 'INVOLVED_WITH',
                'label': inv.active_representation[:30] if inv.active_representation else 'Involved',
                'description': inv.description_of_involvement or '',
                'strength': 'medium',
                # Note: No 'pk' - this is an org involvement, not a clickable connection
            })

        # =================================================================
        # 5. NARRATIVE CONNECTIONS (Event → Event)
        # =================================================================
        connections = NarrativeConnection.objects.filter(
            from_event_id__in=event_ids,
            to_event_id__in=event_ids
        ).select_related('from_event', 'to_event')

        for conn in connections:
            from_id = f"event_{conn.from_event_id}"
            to_id = f"event_{conn.to_event_id}"
            desc = conn.description or ''
            if len(desc) > 150:
                desc = desc[:150] + '...'

            edges.append({
                'from': from_id,
                'to': to_id,
                'type': conn.connection_type,
                'label': conn.get_connection_type_display(),
                'strength': conn.strength,
                'description': desc,
                'pk': conn.pk,
            })

        return {'nodes': nodes, 'edges': edges}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        events = self.get_events_queryset()
        # Serialize to JSON string for safe JavaScript embedding
        context['graph_data'] = json.dumps(self.build_graph_data(events))
        context['graph_title'] = self.get_graph_title()
        context['back_url'] = self.get_back_url()
        return context


class EpisodeGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph of events within a single episode.
    Typically ~20-40 nodes, very fast.
    Uses flexible identifier lookup (fabula_uuid or pk - episodes don't have global_id).
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


class CharacterGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph of events a character participates in.
    Shows the character's journey through the narrative.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = CharacterPage

    def get_graph_title(self):
        return f"{self.get_object().canonical_name}'s Journey"

    def get_back_url(self):
        return self.get_object().get_absolute_url()

    def get_events_queryset(self):
        character = self.get_object()
        event_ids = EventParticipation.objects.filter(
            character=character
        ).values_list('event_id', flat=True)
        return EventPage.objects.live().filter(pk__in=event_ids)


class ThemeGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph of events tagged with a specific theme.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = Theme

    def get_graph_title(self):
        return f"Theme: {self.get_object().name}"

    def get_back_url(self):
        return self.get_object().get_absolute_url()

    def get_events_queryset(self):
        theme = self.get_object()
        return EventPage.objects.live().filter(themes=theme)


class ArcGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph of events in a conflict arc.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = ConflictArc

    def get_graph_title(self):
        return f"Arc: {self.get_object().title}"

    def get_back_url(self):
        return self.get_object().get_absolute_url()

    def get_events_queryset(self):
        arc = self.get_object()
        return EventPage.objects.live().filter(arcs=arc)


class LocationGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph of events involving a specific location.
    Shows all events that take place at this location.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = Location

    def get_graph_title(self):
        return f"Location: {self.get_object().canonical_name}"

    def get_back_url(self):
        return self.get_object().get_absolute_url()

    def get_events_queryset(self):
        location = self.get_object()
        # Get events via LocationInvolvement
        event_ids = LocationInvolvement.objects.filter(
            location=location
        ).values_list('event_id', flat=True)
        # Also include events where this is the primary location
        return EventPage.objects.live().filter(
            models.Q(pk__in=event_ids) | models.Q(location=location)
        ).distinct()


class OrganizationGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph of events involving a specific organization.
    Shows the organization's role across the narrative.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = OrganizationPage

    def get_graph_title(self):
        return f"Organization: {self.get_object().canonical_name}"

    def get_back_url(self):
        return self.get_object().get_absolute_url()

    def get_events_queryset(self):
        org = self.get_object()
        event_ids = OrganizationInvolvement.objects.filter(
            organization=org
        ).values_list('event_id', flat=True)
        return EventPage.objects.live().filter(pk__in=event_ids)


class ObjectGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph of events involving a specific object.
    Shows how an object appears across the narrative.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = ObjectPage

    def get_graph_title(self):
        return f"Object: {self.get_object().canonical_name}"

    def get_back_url(self):
        return self.get_object().get_absolute_url()

    def get_events_queryset(self):
        obj = self.get_object()
        event_ids = ObjectInvolvement.objects.filter(
            object=obj
        ).values_list('event_id', flat=True)
        return EventPage.objects.live().filter(pk__in=event_ids)


class EventGraphView(FlexibleIdentifierMixin, ScopedGraphMixin, DetailView):
    """
    Graph centered on a single event, showing its connections.
    Includes connected events up to 2 hops away.
    Uses flexible identifier lookup (global_id, fabula_uuid, or pk).
    """
    model = EventPage

    def get_graph_title(self):
        return f"Event: {self.get_object().title}"

    def get_back_url(self):
        return self.get_object().get_absolute_url()

    def get_events_queryset(self):
        event = self.get_object()
        # Get directly connected events (1 hop)
        outgoing_ids = NarrativeConnection.objects.filter(
            from_event=event
        ).values_list('to_event_id', flat=True)
        incoming_ids = NarrativeConnection.objects.filter(
            to_event=event
        ).values_list('from_event_id', flat=True)

        # Also get 2-hop connections for context
        first_hop_ids = set(outgoing_ids) | set(incoming_ids)
        second_hop_out = NarrativeConnection.objects.filter(
            from_event_id__in=first_hop_ids
        ).values_list('to_event_id', flat=True)
        second_hop_in = NarrativeConnection.objects.filter(
            to_event_id__in=first_hop_ids
        ).values_list('from_event_id', flat=True)

        all_ids = {event.pk} | first_hop_ids | set(second_hop_out) | set(second_hop_in)
        return EventPage.objects.live().filter(pk__in=all_ids)


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
            event_count=Count('event_participations')
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
