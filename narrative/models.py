"""
Fabula Narrative Web - Wagtail Models

This module defines the content models for rendering a Fabula narrative graph
as a navigable website. The models are designed to:

1. Preserve the rich relationship data from Neo4j edges
2. Make narrative connections first-class navigable content
3. Support graph-native navigation patterns (not just hierarchical)
4. Be populated from YAML intermediary files

Architecture:
- Page types for navigable entities (Event, Character, Theme, etc.)
- Snippet types for reusable referenced content
- Orderable inline models for edge data (participations, connections)
- StreamField for flexible content composition
"""

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator

from wagtail.models import Page, Orderable
from wagtail.fields import RichTextField, StreamField
from wagtail.admin.panels import (
    FieldPanel, InlinePanel, MultiFieldPanel, FieldRowPanel
)
from wagtail.snippets.models import register_snippet
from wagtail.search import index

from modelcluster.fields import ParentalKey, ParentalManyToManyField
from modelcluster.models import ClusterableModel


# =============================================================================
# ENUMS / CHOICES
# =============================================================================

class ConnectionType(models.TextChoices):
    """Narrative connection types from Fabula's PlotBeat relationships."""
    CAUSAL = 'CAUSAL', 'Causal'
    FORESHADOWING = 'FORESHADOWING', 'Foreshadowing'
    THEMATIC_PARALLEL = 'THEMATIC_PARALLEL', 'Thematic Parallel'
    CHARACTER_CONTINUITY = 'CHARACTER_CONTINUITY', 'Character Continuity'
    ESCALATION = 'ESCALATION', 'Escalation'
    CALLBACK = 'CALLBACK', 'Callback'
    EMOTIONAL_ECHO = 'EMOTIONAL_ECHO', 'Emotional Echo'
    SYMBOLIC_PARALLEL = 'SYMBOLIC_PARALLEL', 'Symbolic Parallel'
    TEMPORAL = 'TEMPORAL', 'Temporal'


class ConnectionStrength(models.TextChoices):
    """Strength indicator for narrative connections."""
    STRONG = 'strong', 'Strong'
    MEDIUM = 'medium', 'Medium'
    WEAK = 'weak', 'Weak'


class CharacterType(models.TextChoices):
    """Character classification from Fabula."""
    MAIN = 'main', 'Main Character'
    RECURRING = 'recurring', 'Recurring Character'
    GUEST = 'guest', 'Guest Character'
    MENTIONED = 'mentioned', 'Mentioned Only'


class ImportanceTier(models.TextChoices):
    """
    Graph Gravity-inspired narrative importance tier.

    Computed from episode appearances and relationship density:
    - ANCHOR: Main cast, appears in 5+ episodes or 20+ relationships
    - PLANET: Recurring characters, 2-4 episodes or 5-19 relationships
    - ASTEROID: One-off characters, single episode appearance
    """
    ANCHOR = 'anchor', 'Anchor (Main Cast)'
    PLANET = 'planet', 'Planet (Recurring)'
    ASTEROID = 'asteroid', 'Asteroid (One-off)'


class ArcType(models.TextChoices):
    """Conflict arc types from Fabula."""
    INTERNAL = 'INTERNAL', 'Internal'
    INTERPERSONAL = 'INTERPERSONAL', 'Interpersonal'
    SOCIETAL = 'SOCIETAL', 'Societal'
    ENVIRONMENTAL = 'ENVIRONMENTAL', 'Environmental'
    TECHNOLOGICAL = 'TECHNOLOGICAL', 'Technological'


# =============================================================================
# SNIPPETS - Reusable referenced content
# =============================================================================

@register_snippet
class Theme(index.Indexed, ClusterableModel):
    """
    Thematic element that events can exemplify.

    From Fabula: Theme nodes connected to Events via EXEMPLIFIES_THEME.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        unique=True,
        help_text="UUID from Fabula graph (theme_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_theme_...)"
    )
    name = models.CharField(max_length=255)
    description = models.TextField(
        help_text="Thematic description explaining how this theme manifests"
    )

    # Series scoping for multi-graph support
    series = models.ForeignKey(
        'narrative.SeriesIndexPage',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='themes',
        help_text="Series this theme belongs to (for multi-graph scoping)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel('name'),
        FieldPanel('description'),
        FieldPanel('series'),
        FieldPanel('fabula_uuid'),
    ]

    search_fields = [
        index.SearchField('name', boost=10),
        index.SearchField('description'),
    ]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        """Return URL using global_id for stable cross-season links."""
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/themes/{identifier}/"

    class Meta:
        verbose_name_plural = "Themes"


@register_snippet
class ConflictArc(index.Indexed, ClusterableModel):
    """
    A narrative arc tracking a conflict across multiple events.

    From Fabula: ConflictArc nodes connected to Events via PART_OF_ARC.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        unique=True,
        help_text="UUID from Fabula graph (arc_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_arc_...)"
    )
    title = models.CharField(
        max_length=255,
        help_text="Short title for the arc"
    )
    description = models.TextField(
        help_text="Description of the conflict and its stakes"
    )
    arc_type = models.CharField(
        max_length=50,
        choices=ArcType.choices,
        default=ArcType.INTERPERSONAL
    )

    # Series scoping for multi-graph support
    series = models.ForeignKey(
        'narrative.SeriesIndexPage',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='conflict_arcs',
        help_text="Series this arc belongs to (for multi-graph scoping)"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel('title'),
        FieldPanel('description'),
        FieldPanel('arc_type'),
        FieldPanel('series'),
        FieldPanel('fabula_uuid'),
    ]

    search_fields = [
        index.SearchField('title', boost=10),
        index.SearchField('description'),
    ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        """Return URL using global_id for stable cross-season links."""
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/arcs/{identifier}/"

    class Meta:
        verbose_name = "Conflict Arc"
        verbose_name_plural = "Conflict Arcs"


@register_snippet
class Location(index.Indexed, ClusterableModel):
    """
    A place where events occur.

    From Fabula: Location nodes with foundational_description and foundational_type.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        unique=True,
        help_text="UUID from Fabula graph (location_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_location_...)"
    )
    canonical_name = models.CharField(max_length=255)
    description = models.TextField(
        help_text="Physical and atmospheric description of the location"
    )
    location_type = models.CharField(
        max_length=100,
        blank=True,
        help_text="Categorical type (e.g., 'West Wing Executive Office')"
    )
    parent_location = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='child_locations',
        help_text="Parent location for hierarchical relationships"
    )

    # Series scoping for multi-graph support
    series = models.ForeignKey(
        'narrative.SeriesIndexPage',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='locations',
        help_text="Series this location belongs to (for multi-graph scoping)"
    )

    # Megagraph cross-season tracking fields
    season_appearances = models.JSONField(
        default=list,
        blank=True,
        help_text="Seasons this entity appears in, e.g., [1, 2, 3]"
    )
    local_uuids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"
    )
    first_appearance_season = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="First season this entity appears"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    panels = [
        FieldPanel('canonical_name'),
        FieldPanel('description'),
        FieldPanel('location_type'),
        FieldPanel('parent_location'),
        FieldPanel('series'),
        MultiFieldPanel([
            FieldPanel('fabula_uuid'),
            FieldPanel('global_id'),
            FieldPanel('season_appearances'),
            FieldPanel('local_uuids'),
            FieldPanel('first_appearance_season'),
        ], heading="Megagraph Metadata", classname="collapsible collapsed"),
    ]

    search_fields = [
        index.SearchField('canonical_name', boost=10),
        index.SearchField('description'),
    ]

    def __str__(self):
        return self.canonical_name

    def get_absolute_url(self):
        """Return URL using global_id for stable cross-season links."""
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/locations/{identifier}/"

    class Meta:
        verbose_name_plural = "Locations"


# =============================================================================
# PAGE TYPES - Navigable entities
# =============================================================================

class SeriesIndexPage(Page):
    """
    Root page for a series (e.g., "The West Wing").
    Contains seasons as children, plus index pages for events, characters, organizations.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (series_uuid)"
    )
    description = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('description'),
        FieldPanel('fabula_uuid'),
    ]

    subpage_types = [
        'narrative.SeasonPage',
        'narrative.EventIndexPage',
        'narrative.CharacterIndexPage',
        'narrative.OrganizationIndexPage',
        'narrative.ObjectIndexPage',
    ]
    parent_page_types = ['wagtailcore.Page']

    def get_context(self, request):
        context = super().get_context(request)

        # Find child index pages by type
        children = self.get_children().specific()
        context['events_index'] = None
        context['characters_index'] = None
        context['organizations_index'] = None
        context['objects_index'] = None
        context['seasons'] = []

        for child in children:
            if isinstance(child, EventIndexPage):
                context['events_index'] = child
            elif isinstance(child, CharacterIndexPage):
                context['characters_index'] = child
            elif isinstance(child, OrganizationIndexPage):
                context['organizations_index'] = child
            elif isinstance(child, ObjectIndexPage):
                context['objects_index'] = child
            elif isinstance(child, SeasonPage):
                context['seasons'].append(child)

        # Sort seasons by number
        context['seasons'].sort(key=lambda s: s.season_number)

        return context


class SeasonPage(Page):
    """
    A season within a series.
    Contains episodes as children.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (season_uuid)"
    )
    season_number = models.PositiveIntegerField()
    description = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('season_number'),
        FieldPanel('description'),
        FieldPanel('fabula_uuid'),
    ]

    subpage_types = ['narrative.EpisodePage']
    parent_page_types = ['narrative.SeriesIndexPage']

    class Meta:
        ordering = ['season_number']


class EpisodePage(Page):
    """
    An episode within a season.
    
    From Fabula: Episode nodes with high_level_summary, logline, etc.
    Events are NOT children - they're linked via EventPage.episode foreign key.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (episode_uuid)"
    )
    episode_number = models.PositiveIntegerField()
    logline = models.TextField(
        blank=True,
        help_text="One-sentence summary of the episode"
    )
    high_level_summary = RichTextField(
        blank=True,
        help_text="Detailed episode summary"
    )
    dominant_tone = models.CharField(
        max_length=100,
        blank=True,
        help_text="The prevailing emotional/atmospheric tone"
    )

    content_panels = Page.content_panels + [
        FieldPanel('episode_number'),
        FieldPanel('logline'),
        FieldPanel('high_level_summary'),
        FieldPanel('dominant_tone'),
        FieldPanel('fabula_uuid'),
    ]

    subpage_types = []
    parent_page_types = ['narrative.SeasonPage']

    class Meta:
        ordering = ['episode_number']

    def get_events(self):
        """Get all events in this episode, ordered by sequence."""
        return EventPage.objects.live().filter(
            episode=self
        ).order_by('scene_sequence', 'sequence_in_scene')


class CharacterPage(Page):
    """
    A character/agent in the narrative.

    From Fabula: Agent nodes with foundational_description, foundational_traits, etc.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (agent_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_agent_...)"
    )
    canonical_name = models.CharField(
        max_length=255,
        help_text="Primary name (e.g., 'Joshua Lyman')"
    )
    title_role = models.CharField(
        max_length=255,
        blank=True,
        help_text="Official title or role (e.g., 'Deputy Chief of Staff')"
    )
    description = RichTextField(
        help_text="Foundational character description"
    )
    traits = models.JSONField(
        default=list,
        blank=True,
        help_text="List of foundational character traits"
    )
    nicknames = models.JSONField(
        default=list,
        blank=True,
        help_text="Alternative names and nicknames"
    )
    character_type = models.CharField(
        max_length=50,
        choices=CharacterType.choices,
        default=CharacterType.RECURRING
    )
    sphere_of_influence = models.CharField(
        max_length=255,
        blank=True,
        help_text="Primary domain of authority or expertise"
    )
    appearance_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of event appearances"
    )

    # Graph Gravity tiering fields
    episode_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of distinct episodes appeared in (computed)"
    )
    importance_tier = models.CharField(
        max_length=20,
        choices=ImportanceTier.choices,
        default=ImportanceTier.ASTEROID,
        help_text="Narrative importance tier (computed from episode/relationship counts)"
    )
    relationship_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of unique characters co-participated with (computed)"
    )

    # Pre-computed 3D graph positions (from co-occurrence analysis)
    graph_x = models.FloatField(
        default=0.0,
        help_text="Pre-computed X position for graph visualization"
    )
    graph_y = models.FloatField(
        default=0.0,
        help_text="Pre-computed Y position for graph visualization"
    )
    graph_z = models.FloatField(
        default=0.0,
        help_text="Pre-computed Z position for graph visualization"
    )
    graph_community = models.PositiveIntegerField(
        default=0,
        help_text="Community cluster ID from Louvain detection"
    )

    # Megagraph cross-season tracking fields
    season_appearances = models.JSONField(
        default=list,
        blank=True,
        help_text="Seasons this character appears in, e.g., [1, 2, 3]"
    )
    local_uuids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"
    )
    first_appearance_season = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="First season this character appears"
    )

    # Relationships
    affiliated_organization = models.ForeignKey(
        'narrative.OrganizationPage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='affiliated_characters'
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('canonical_name'),
            FieldPanel('title_role'),
            FieldPanel('character_type'),
        ], heading="Identity"),
        FieldPanel('description'),
        MultiFieldPanel([
            FieldPanel('traits'),
            FieldPanel('nicknames'),
            FieldPanel('sphere_of_influence'),
        ], heading="Attributes"),
        FieldPanel('affiliated_organization'),
        MultiFieldPanel([
            FieldPanel('appearance_count'),
            FieldPanel('episode_count'),
            FieldPanel('relationship_count'),
            FieldPanel('importance_tier'),
        ], heading="Graph Gravity Metrics"),
        MultiFieldPanel([
            FieldPanel('fabula_uuid'),
            FieldPanel('global_id'),
            FieldPanel('season_appearances'),
            FieldPanel('local_uuids'),
            FieldPanel('first_appearance_season'),
        ], heading="Megagraph Metadata", classname="collapsible collapsed"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('canonical_name', boost=10),
        index.SearchField('description'),
        index.SearchField('title_role'),
    ]

    parent_page_types = ['narrative.CharacterIndexPage']
    subpage_types = []

    def get_participations(self):
        """Get all event participations for this character, ordered chronologically."""
        return EventParticipation.objects.filter(
            character=self
        ).select_related(
            'event', 'event__episode'
        ).order_by(
            'event__episode__path',  # Season ordering via page tree path
            'event__episode__episode_number',
            'event__scene_sequence'
        )

    def get_emotional_journey(self):
        """Get participations with emotional state for journey view."""
        return self.get_participations().exclude(
            emotional_state=''
        )

    def get_absolute_url(self):
        """Return URL using global_id for stable cross-season links."""
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/characters/{identifier}/"


class CharacterIndexPage(Page):
    """Index page listing all characters."""
    introduction = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    subpage_types = ['narrative.CharacterPage']

    def get_characters(self):
        return CharacterPage.objects.live().child_of(self).order_by(
            '-appearance_count'
        )

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context['characters'] = self.get_characters()
        return context


class OrganizationPage(Page):
    """
    An organization in the narrative.

    From Fabula: Organization nodes.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (org_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_org_...)"
    )
    canonical_name = models.CharField(max_length=255)
    description = RichTextField()
    sphere_of_influence = models.CharField(
        max_length=255,
        blank=True,
        help_text="Primary domain of operation"
    )

    # Megagraph cross-season tracking fields
    season_appearances = models.JSONField(
        default=list,
        blank=True,
        help_text="Seasons this organization appears in, e.g., [1, 2, 3]"
    )
    local_uuids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"
    )
    first_appearance_season = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="First season this organization appears"
    )

    content_panels = Page.content_panels + [
        FieldPanel('canonical_name'),
        FieldPanel('description'),
        FieldPanel('sphere_of_influence'),
        MultiFieldPanel([
            FieldPanel('fabula_uuid'),
            FieldPanel('global_id'),
            FieldPanel('season_appearances'),
            FieldPanel('local_uuids'),
            FieldPanel('first_appearance_season'),
        ], heading="Megagraph Metadata", classname="collapsible collapsed"),
    ]

    parent_page_types = ['narrative.OrganizationIndexPage']
    subpage_types = []

    def get_search_terms(self):
        """Get search terms for finding related content."""
        terms = []
        name = self.canonical_name

        # Add full name
        terms.append(name)

        # Extract base name before parenthetical
        if '(' in name:
            base_name = name.split('(')[0].strip()
            if len(base_name) > 3:
                terms.append(base_name)

        # Extract key words for common organization types
        # e.g., "White House Senior Staff..." -> also search "White House"
        key_phrases = ['White House', 'Congress', 'Senate', 'House of Representatives',
                       'State Department', 'Pentagon', 'FBI', 'CIA', 'NSA', 'NSC',
                       'Supreme Court', 'Department of', 'Office of', 'Committee']
        for phrase in key_phrases:
            if phrase in name and phrase not in terms:
                terms.append(phrase)

        return terms

    def get_related_characters(self, limit=20):
        """Find characters whose description or sphere mentions this organization."""
        from django.db.models import Q
        terms = self.get_search_terms()
        q = Q()
        for term in terms:
            q |= Q(description__icontains=term) | Q(sphere_of_influence__icontains=term)
        return CharacterPage.objects.live().filter(q).distinct()[:limit]

    def get_related_events(self, limit=30):
        """Find events whose description mentions this organization."""
        from django.db.models import Q
        terms = self.get_search_terms()
        q = Q()
        for term in terms:
            q |= Q(description__icontains=term)
        return EventPage.objects.live().filter(q).select_related('episode').distinct()[:limit]

    def get_absolute_url(self):
        """Return URL using global_id for stable cross-season links."""
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/organizations/{identifier}/"


class OrganizationIndexPage(Page):
    """Index page listing all organizations."""
    introduction = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    subpage_types = ['narrative.OrganizationPage']

    def get_organizations(self):
        """Get organizations ordered alphabetically.

        Note: Related event counts are computed on-demand in the template
        for display purposes, but sorting by count is disabled for performance
        (would require N queries where N = number of orgs).
        """
        return OrganizationPage.objects.live().child_of(self).order_by('canonical_name')

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context['organizations'] = self.get_organizations()
        return context


class ObjectIndexPage(Page):
    """Index page listing all objects."""
    introduction = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    subpage_types = ['narrative.ObjectPage']
    parent_page_types = ['narrative.SeriesIndexPage']

    def get_objects(self):
        from django.db.models import Count
        return ObjectPage.objects.live().child_of(self).annotate(
            involvement_count=Count('event_involvements')
        ).order_by('-involvement_count', 'canonical_name')

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context['objects'] = self.get_objects()
        return context


class ObjectPage(Page):
    """
    A significant object in the narrative.

    From Fabula: Object nodes with foundational_description, purpose, etc.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (object_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_object_...)"
    )
    canonical_name = models.CharField(max_length=255)
    description = RichTextField(
        help_text="Description of the object and its appearance"
    )
    purpose = models.TextField(
        blank=True,
        help_text="The foundational purpose of this object in the narrative"
    )
    significance = models.TextField(
        blank=True,
        help_text="The narrative significance of this object"
    )
    potential_owner = models.ForeignKey(
        'narrative.CharacterPage',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='owned_objects',
        help_text="Character who typically owns or possesses this object"
    )

    # Megagraph cross-season tracking fields
    season_appearances = models.JSONField(
        default=list,
        blank=True,
        help_text="Seasons this object appears in, e.g., [1, 2, 3]"
    )
    local_uuids = models.JSONField(
        default=dict,
        blank=True,
        help_text="Mapping of season number to local fabula_uuid, e.g., {1: 'uuid_abc', 2: 'uuid_def'}"
    )
    first_appearance_season = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="First season this object appears"
    )

    content_panels = Page.content_panels + [
        FieldPanel('canonical_name'),
        FieldPanel('description'),
        FieldPanel('purpose'),
        FieldPanel('significance'),
        FieldPanel('potential_owner'),
        MultiFieldPanel([
            FieldPanel('fabula_uuid'),
            FieldPanel('global_id'),
            FieldPanel('season_appearances'),
            FieldPanel('local_uuids'),
            FieldPanel('first_appearance_season'),
        ], heading="Megagraph Metadata", classname="collapsible collapsed"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('canonical_name', boost=10),
        index.SearchField('description'),
        index.SearchField('purpose'),
    ]

    parent_page_types = ['narrative.ObjectIndexPage']
    subpage_types = []

    def get_involvements(self):
        """Get all event involvements for this object."""
        return ObjectInvolvement.objects.filter(
            object=self
        ).select_related('event', 'event__episode').order_by(
            'event__episode__episode_number',
            'event__scene_sequence'
        )

    def get_absolute_url(self):
        """Return URL using global_id for stable cross-season links."""
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/objects/{identifier}/"


class EventPage(Page):
    """
    A narrative event - the atomic unit of the story.
    
    From Fabula: Event nodes with description, key_dialogue, etc.
    This is the primary "hub" page in the narrative web.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (event_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_event_...)"
    )

    # Episode context
    episode = models.ForeignKey(
        EpisodePage,
        on_delete=models.PROTECT,
        related_name='events',
        help_text="The episode this event belongs to"
    )
    scene_sequence = models.PositiveIntegerField(
        default=0,
        help_text="Scene number within episode"
    )
    sequence_in_scene = models.PositiveIntegerField(
        default=0,
        help_text="Event sequence within scene"
    )
    
    # Content
    description = RichTextField(
        help_text="Full description of what happens in this event"
    )
    key_dialogue = models.JSONField(
        default=list,
        blank=True,
        help_text="Notable dialogue from this event"
    )
    is_flashback = models.BooleanField(
        default=False,
        help_text="Whether this event is a flashback"
    )
    
    # Location
    location = models.ForeignKey(
        Location,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='events'
    )
    
    # Thematic connections
    themes = ParentalManyToManyField(
        Theme,
        blank=True,
        related_name='events'
    )
    arcs = ParentalManyToManyField(
        ConflictArc,
        blank=True,
        related_name='events'
    )

    # Megagraph source tracking fields
    source_season = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Season number this event came from (for megagraph imports)"
    )
    source_database = models.CharField(
        max_length=100,
        blank=True,
        help_text="Source database name, e.g., westwing.s01"
    )

    content_panels = Page.content_panels + [
        MultiFieldPanel([
            FieldPanel('episode'),
            FieldRowPanel([
                FieldPanel('scene_sequence'),
                FieldPanel('sequence_in_scene'),
            ]),
            FieldPanel('is_flashback'),
        ], heading="Episode Context"),
        FieldPanel('description'),
        FieldPanel('key_dialogue'),
        FieldPanel('location'),
        MultiFieldPanel([
            FieldPanel('themes'),
            FieldPanel('arcs'),
        ], heading="Thematic Connections"),
        MultiFieldPanel([
            InlinePanel('participations', label="Characters"),
            InlinePanel('object_involvements', label="Objects"),
            InlinePanel('location_involvements', label="Locations"),
            InlinePanel('organization_involvements', label="Organizations"),
        ], heading="Entity Involvement", classname="collapsible"),
        MultiFieldPanel([
            FieldPanel('fabula_uuid'),
            FieldPanel('global_id'),
            FieldPanel('source_season'),
            FieldPanel('source_database'),
        ], heading="Megagraph Metadata", classname="collapsible collapsed"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('description'),
        index.RelatedFields('episode', [
            index.SearchField('title'),
        ]),
    ]

    parent_page_types = ['narrative.EventIndexPage']
    subpage_types = []

    class Meta:
        ordering = ['episode__episode_number', 'scene_sequence', 'sequence_in_scene']

    def get_participations_by_importance(self):
        """
        Return participations grouped by importance level, sorted by engagement.

        Returns dict with keys: 'primary', 'secondary', 'mentioned', 'other'
        Each containing a list of participations sorted by richness of data.
        """
        all_parts = self.participations.select_related('character')

        grouped = {
            'primary': [],
            'secondary': [],
            'mentioned': [],
            'other': [],
        }

        for p in all_parts:
            importance = (p.importance or '').lower().strip()
            if importance in grouped:
                grouped[importance].append(p)
            elif importance:
                grouped['other'].append(p)
            else:
                # Empty importance defaults to primary (active participant)
                grouped['primary'].append(p)

        # Sort within each group by engagement richness
        def engagement_score(p):
            """Higher score = more engaged/richer data = should appear first."""
            score = 0
            if p.what_happened:
                score += 3  # Active action described
            if p.emotional_state:
                score += 2  # Emotional engagement captured
            if p.goals:
                score += 1  # Goals documented
            return -score  # Negative for descending sort

        for key in grouped:
            grouped[key].sort(key=engagement_score)

        return grouped

    def get_primary_participants(self):
        """Get only primary (active) participants."""
        return self.participations.filter(
            importance__in=['primary', '']
        ).select_related('character')

    def get_connections_from(self):
        """Get narrative connections where this event is the source."""
        return NarrativeConnection.objects.filter(
            from_event=self
        ).select_related('to_event', 'to_event__episode')

    def get_connections_to(self):
        """Get narrative connections where this event is the target."""
        return NarrativeConnection.objects.filter(
            to_event=self
        ).select_related('from_event', 'from_event__episode')

    def get_all_connections(self):
        """Get all connections involving this event."""
        return {
            'outgoing': self.get_connections_from(),
            'incoming': self.get_connections_to(),
        }

    def primary_location_has_involvement(self):
        """
        Check if the primary location FK also has a LocationInvolvement record.

        Used by templates to avoid showing the same location twice:
        - If True: show rich involvement data, skip simple location card
        - If False: show simple location card (no rich data available)
        """
        if not self.location_id:
            return False
        return self.location_involvements.filter(location_id=self.location_id).exists()

    def get_absolute_url(self):
        """Return URL using global_id for stable cross-season links."""
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/events/{identifier}/"


class EventIndexPage(Page):
    """
    Index page for events.
    Supports multiple navigation modes: by episode, by theme, by character.
    """
    introduction = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    subpage_types = ['narrative.EventPage']

    def get_context(self, request):
        context = super().get_context(request)

        # Get all live events (not just descendants - events may not be direct children)
        events = EventPage.objects.live().select_related(
            'episode'
        ).order_by('episode__episode_number', 'scene_sequence', 'sequence_in_scene')

        # Sort by series/season/episode/scene (requires Python for page tree traversal)
        def sort_key(event):
            if not event.episode:
                return ('', 0, 0, 0, 0)
            season = event.episode.get_parent().specific if event.episode else None
            series = season.get_parent() if season else None
            series_title = series.title if series else ''
            season_num = getattr(season, 'season_number', 0) if season else 0
            episode_num = event.episode.episode_number if event.episode else 0
            return (series_title, season_num, episode_num, event.scene_sequence, event.sequence_in_scene)

        sorted_events = sorted(events, key=sort_key)

        # Group events by episode for template rendering
        from itertools import groupby
        episodes_with_events = []
        for episode, episode_events in groupby(sorted_events, key=lambda e: e.episode):
            season = episode.get_parent().specific if episode else None
            series = season.get_parent().specific if season else None
            episodes_with_events.append({
                'episode': episode,
                'season': season,
                'series': series,
                'events': list(episode_events)
            })

        context['episodes_with_events'] = episodes_with_events
        context['events'] = sorted_events  # Keep flat list for backwards compatibility
        return context


# =============================================================================
# INLINE MODELS - Edge data from relationships
# =============================================================================

class EventParticipation(Orderable):
    """
    How a character participates in an event.
    
    From Fabula: PARTICIPATED_AS relationship properties including
    emotional_state_at_event, goals_at_event, observed_status, etc.
    
    This preserves the rich edge data that makes the narrative web meaningful.
    """
    event = ParentalKey(
        EventPage,
        on_delete=models.CASCADE,
        related_name='participations'
    )
    character = models.ForeignKey(
        CharacterPage,
        on_delete=models.CASCADE,
        related_name='event_participations'
    )
    
    # The rich participation data from Fabula's PARTICIPATED_AS edge
    emotional_state = models.TextField(
        blank=True,
        help_text="Character's emotional state during this event"
    )
    goals = models.JSONField(
        default=list,
        help_text="Character's goals in this moment"
    )
    what_happened = models.TextField(
        blank=True,
        help_text="Description of what the character did"
    )
    observed_status = models.TextField(
        blank=True,
        help_text="Observable status or role in the event"
    )
    beliefs = models.JSONField(
        default=list,
        blank=True,
        help_text="Character's beliefs active in this moment"
    )
    observed_traits = models.JSONField(
        default=list,
        blank=True,
        help_text="Character traits observable in this event"
    )
    importance = models.CharField(
        max_length=50,
        blank=True,
        help_text="primary, secondary, background, etc."
    )

    panels = [
        FieldPanel('character'),
        FieldPanel('emotional_state'),
        FieldPanel('goals'),
        FieldPanel('what_happened'),
        FieldPanel('observed_status'),
        FieldPanel('beliefs'),
        FieldPanel('observed_traits'),
        FieldPanel('importance'),
    ]

    class Meta:
        unique_together = ['event', 'character']
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.character} in {self.event}"


class ObjectInvolvement(Orderable):
    """
    How an object is involved in an event.

    From Fabula: Object INVOLVED_WITH Event relationship properties.
    """
    event = ParentalKey(
        EventPage,
        on_delete=models.CASCADE,
        related_name='object_involvements'
    )
    object = models.ForeignKey(
        ObjectPage,
        on_delete=models.CASCADE,
        related_name='event_involvements'
    )

    description_of_involvement = models.TextField(
        blank=True,
        help_text="How this object is used or relevant in this event"
    )
    status_before_event = models.TextField(
        blank=True,
        help_text="State of the object before this event"
    )
    status_after_event = models.TextField(
        blank=True,
        help_text="State of the object after this event"
    )

    panels = [
        FieldPanel('object'),
        FieldPanel('description_of_involvement'),
        FieldPanel('status_before_event'),
        FieldPanel('status_after_event'),
    ]

    class Meta:
        unique_together = ['event', 'object']
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.object} in {self.event}"


class LocationInvolvement(Orderable):
    """
    Rich involvement data for a location in an event.

    From Fabula: Location IN_EVENT relationship with atmosphere, role, etc.
    Note: EventPage retains simple location FK for primary location.
    This model adds rich atmospheric/contextual data.
    """
    event = ParentalKey(
        EventPage,
        on_delete=models.CASCADE,
        related_name='location_involvements'
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name='event_involvements'
    )

    description_of_involvement = models.TextField(
        blank=True,
        help_text="How this location features in this event"
    )
    observed_atmosphere = models.TextField(
        blank=True,
        help_text="The mood and atmosphere of the location during this event"
    )
    functional_role = models.TextField(
        blank=True,
        help_text="The functional role the location plays (meeting place, sanctuary, etc.)"
    )
    symbolic_significance = models.TextField(
        blank=True,
        help_text="Any symbolic meaning the location carries in this context"
    )
    access_restrictions = models.TextField(
        blank=True,
        help_text="Who can access this location during the event"
    )
    key_environmental_details = models.JSONField(
        default=list,
        help_text="Notable environmental details (lighting, sounds, etc.)"
    )

    panels = [
        FieldPanel('location'),
        FieldPanel('description_of_involvement'),
        FieldPanel('observed_atmosphere'),
        FieldPanel('functional_role'),
        FieldPanel('symbolic_significance'),
        FieldPanel('access_restrictions'),
        FieldPanel('key_environmental_details'),
    ]

    class Meta:
        unique_together = ['event', 'location']
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.location} in {self.event}"


class OrganizationInvolvement(Orderable):
    """
    How an organization is involved in an event.

    From Fabula: Organization INVOLVED_WITH Event relationship properties.
    """
    event = ParentalKey(
        EventPage,
        on_delete=models.CASCADE,
        related_name='organization_involvements'
    )
    organization = models.ForeignKey(
        OrganizationPage,
        on_delete=models.CASCADE,
        related_name='event_involvements'
    )

    description_of_involvement = models.TextField(
        blank=True,
        help_text="How this organization is involved in this event"
    )
    active_representation = models.TextField(
        blank=True,
        help_text="Who or what represents the organization in this event"
    )
    power_dynamics = models.TextField(
        blank=True,
        help_text="The power dynamics the organization displays"
    )
    organizational_goals = models.JSONField(
        default=list,
        help_text="Goals the organization pursues in this event"
    )
    influence_mechanisms = models.JSONField(
        default=list,
        help_text="How the organization exerts influence"
    )
    institutional_impact = models.TextField(
        blank=True,
        help_text="Impact on the institution/organization"
    )
    internal_dynamics = models.TextField(
        blank=True,
        help_text="Internal organizational dynamics revealed"
    )

    panels = [
        FieldPanel('organization'),
        FieldPanel('description_of_involvement'),
        FieldPanel('active_representation'),
        FieldPanel('power_dynamics'),
        FieldPanel('organizational_goals'),
        FieldPanel('influence_mechanisms'),
        FieldPanel('institutional_impact'),
        FieldPanel('internal_dynamics'),
    ]

    class Meta:
        unique_together = ['event', 'organization']
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.organization} in {self.event}"


class NarrativeConnection(models.Model):
    """
    A narrative connection between two events.
    
    From Fabula: PlotBeat relationships like CAUSAL, FORESHADOWING,
    THEMATIC_PARALLEL, CHARACTER_CONTINUITY, etc.
    
    This is first-class content - connections have their own pages.
    The 'description' field contains the narrative assertion explaining
    WHY these events connect, not just THAT they connect.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (connection_uuid)"
    )
    global_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
        help_text="GER global entity ID for cross-season identity (e.g., ger_conn_...)"
    )

    from_event = models.ForeignKey(
        EventPage,
        on_delete=models.CASCADE,
        related_name='outgoing_connections'
    )
    to_event = models.ForeignKey(
        EventPage,
        on_delete=models.CASCADE,
        related_name='incoming_connections'
    )
    
    connection_type = models.CharField(
        max_length=50,
        choices=ConnectionType.choices
    )
    strength = models.CharField(
        max_length=20,
        choices=ConnectionStrength.choices,
        default=ConnectionStrength.MEDIUM
    )
    
    # THE KEY FIELD: the narrative assertion explaining the connection
    description = models.TextField(
        help_text="The narrative assertion explaining WHY these events connect. "
                  "This is the 'content' of the connection - the edge carries meaning."
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['from_event', 'to_event', 'connection_type']
        ordering = ['connection_type', '-strength']

    def __str__(self):
        return f"{self.from_event.title} → [{self.connection_type}] → {self.to_event.title}"

    def get_absolute_url(self):
        """Connections are navigable - they have their own URLs."""
        # Use global_id for stable cross-season URLs, fall back to pk
        identifier = self.global_id or self.fabula_uuid or self.pk
        return f"/connections/{identifier}/"


class CharacterEpisodeProfile(models.Model):
    """
    A character's state/profile within a specific episode.
    
    From Fabula: AgentEpisodeProfile nodes tracking per-episode character state.
    """
    fabula_uuid = models.CharField(
        max_length=100,
        blank=True,
        help_text="UUID from Fabula graph (profile_uuid)"
    )
    
    character = models.ForeignKey(
        CharacterPage,
        on_delete=models.CASCADE,
        related_name='episode_profiles'
    )
    episode = models.ForeignKey(
        EpisodePage,
        on_delete=models.CASCADE,
        related_name='character_profiles'
    )
    
    description_in_episode = models.TextField(
        blank=True,
        help_text="Character's state/role in this specific episode"
    )
    traits_in_episode = models.JSONField(
        default=list,
        help_text="Traits observed in this episode"
    )
    contradictions = models.JSONField(
        default=list,
        blank=True,
        help_text="Contradictions or tensions observed"
    )

    class Meta:
        unique_together = ['character', 'episode']
        verbose_name = "Character Episode Profile"
        verbose_name_plural = "Character Episode Profiles"

    def __str__(self):
        return f"{self.character} in {self.episode}"


# =============================================================================
# THEME AND CONNECTION INDEX PAGES
# =============================================================================

class ThemeIndexPage(Page):
    """Index page for exploring themes."""
    introduction = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    subpage_types = []

    def get_themes(self):
        return Theme.objects.annotate(
            event_count=models.Count('events')
        ).order_by('-event_count')


class ConnectionIndexPage(Page):
    """
    Index page for exploring narrative connections.
    Allows browsing by connection type.
    """
    introduction = RichTextField(blank=True)

    content_panels = Page.content_panels + [
        FieldPanel('introduction'),
    ]

    subpage_types = []

    def get_connections_by_type(self):
        """Group connections by type for navigation."""
        result = {}
        for conn_type in ConnectionType.choices:
            connections = NarrativeConnection.objects.filter(
                connection_type=conn_type[0]
            ).select_related('from_event', 'to_event')
            if connections.exists():
                result[conn_type] = connections
        return result
