"""
Narrative Template Tags

Custom template tags and filters for the Fabula narrative web.

Usage in templates:
    {% load narrative_tags %}
"""

import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


# =============================================================================
# FILTERS
# =============================================================================

def _strip_md_cruft(value):
    """Strip LLM formatting cruft: wrapping ** bold markers and quotes."""
    if not value:
        return ''
    text = str(value).strip()
    # First pass: peel matched wrapping ** pairs.
    if text.startswith('**') and text.endswith('**') and len(text) > 4:
        text = text[2:-2].strip()
    # Second pass: strip orphaned leading/trailing ** (unmatched bold markers).
    if text.startswith('**') and '**' not in text[2:]:
        text = text[2:].strip()
    if text.endswith('**') and '**' not in text[:-2]:
        text = text[:-2].strip()
    # Strip wrapping quotes (including doubled quotes like "Title"").
    text = re.sub(r'^["\u201c]+', '', text)
    text = re.sub(r'["\u201d]+$', '', text)
    return text.strip()


@register.filter
def md(value):
    """
    Convert inline markdown formatting to HTML.
    Handles **bold**, *italic*, and strips wrapping quotes from LLM output.
    Escapes HTML for safety.
    Usage: {{ event.title|md }}
    """
    text = _strip_md_cruft(value)
    if not text:
        return ''
    text = escape(text)
    # **bold** → <strong>bold</strong>  (handles remaining inline bold)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text, flags=re.DOTALL)
    # *italic* → <em>italic</em>
    text = re.sub(r'(?<!\*)\*([^*]+?)\*(?!\*)', r'<em>\1</em>', text)
    return mark_safe(text)


@register.filter
def md_plain(value):
    """
    Strip markdown formatting to plain text (no HTML).
    Removes wrapping cruft, then strips all remaining ** and * markers.
    Safe for use in <title>, alt text, etc.
    Usage: {{ event.title|md_plain }}
    """
    text = _strip_md_cruft(value)
    if not text:
        return ''
    text = text.replace('**', '').replace('*', '')
    return text


@register.filter
def replace(value, args):
    """
    Replace occurrences in a string.
    Usage: {{ value|replace:"old:new" }}
    """
    if not value:
        return value
    
    try:
        old, new = args.split(':')
        return value.replace(old, new)
    except ValueError:
        return value


@register.filter
def connection_class(connection_type):
    """
    Get CSS class for a connection type.
    Usage: {{ connection.connection_type|connection_class }}
    """
    return f"conn-{connection_type.lower().replace('_', '-')}"


@register.filter
def connection_color(connection_type):
    """
    Get color value for a connection type.
    """
    colors = {
        'CAUSAL': '#22d3ee',
        'FORESHADOWING': '#a855f7',
        'THEMATIC_PARALLEL': '#f59e0b',
        'CHARACTER_CONTINUITY': '#10b981',
        'ESCALATION': '#ef4444',
        'CALLBACK': '#3b82f6',
        'EMOTIONAL_ECHO': '#ec4899',
        'SYMBOLIC_PARALLEL': '#8b5cf6',
        'TEMPORAL': '#6366f1',
    }
    return colors.get(connection_type, '#64748b')


@register.filter
def truncate_title(title, length=30):
    """
    Truncate a title with ellipsis.
    Usage: {{ event.title|truncate_title:25 }}
    """
    if len(title) <= length:
        return title
    return title[:length].rsplit(' ', 1)[0] + '...'


@register.filter
def tier_icon(tier):
    """
    Get emoji icon for a character importance tier.
    Usage: {{ character.importance_tier|tier_icon }}
    """
    icons = {
        'anchor': '☀️',
        'planet': '🪐',
        'asteroid': '☄️',
    }
    return icons.get(tier, '☄️')


@register.filter
def tier_class(tier):
    """
    Get CSS class for a character importance tier.
    Usage: <span class="{{ character.importance_tier|tier_class }}">
    """
    return f"tier-{tier}" if tier else "tier-asteroid"


@register.filter
def tier_label(tier):
    """
    Get human-readable label for a character importance tier.
    Usage: {{ character.importance_tier|tier_label }}
    """
    labels = {
        'anchor': 'Main Cast',
        'planet': 'Recurring',
        'asteroid': 'One-off',
    }
    return labels.get(tier, 'One-off')


@register.filter
def tier_color(tier):
    """
    Get hex color for a character importance tier.
    Usage: style="color: {{ character.importance_tier|tier_color }}"
    """
    colors = {
        'anchor': '#fbbf24',  # Amber/gold for main cast
        'planet': '#14b8a6',  # Teal for recurring
        'asteroid': '#6b7280',  # Gray for one-offs
    }
    return colors.get(tier, '#6b7280')


# =============================================================================
# SIMPLE TAGS
# =============================================================================

@register.simple_tag
def connection_icon(connection_type):
    """
    Return the Lucide icon name for a connection type.
    Usage: {% connection_icon connection.connection_type %}
    """
    icons = {
        'CAUSAL': 'arrow-right',
        'FORESHADOWING': 'sparkles',
        'THEMATIC_PARALLEL': 'git-merge',
        'CHARACTER_CONTINUITY': 'rotate-ccw',
        'ESCALATION': 'trending-up',
        'CALLBACK': 'arrow-left',
        'EMOTIONAL_ECHO': 'heart',
        'SYMBOLIC_PARALLEL': 'equal',
        'TEMPORAL': 'clock',
    }
    return icons.get(connection_type, 'link')


@register.simple_tag
def page_type_icon(page):
    """
    Return the Lucide icon name for a page type.
    Usage: {% page_type_icon page %}
    """
    class_name = page.specific_class_name if hasattr(page, 'specific_class_name') else page.__class__.__name__
    
    icons = {
        'EventPage': 'zap',
        'CharacterPage': 'user',
        'EpisodePage': 'film',
        'SeasonPage': 'folder',
        'SeriesIndexPage': 'tv',
        'OrganizationPage': 'building-2',
        'CharacterIndexPage': 'users',
        'EventIndexPage': 'list',
    }
    return icons.get(class_name, 'file-text')


@register.simple_tag
def page_type_color(page):
    """
    Return the Tailwind color class for a page type.
    Usage: {% page_type_color page %}
    """
    class_name = page.specific_class_name if hasattr(page, 'specific_class_name') else page.__class__.__name__
    
    colors = {
        'EventPage': 'amber',
        'CharacterPage': 'emerald',
        'EpisodePage': 'blue',
        'SeasonPage': 'blue',
        'SeriesIndexPage': 'amber',
        'OrganizationPage': 'cyan',
    }
    return colors.get(class_name, 'slate')


# =============================================================================
# INCLUSION TAGS
# =============================================================================

@register.inclusion_tag('includes/event_card.html')
def event_card(event, show_episode=True, show_connections=False):
    """
    Render an event card.
    Usage: {% event_card event show_episode=True %}
    """
    return {
        'event': event,
        'show_episode': show_episode,
        'show_connections': show_connections,
    }


@register.inclusion_tag('includes/character_badge.html')
def character_badge(character, size='md'):
    """
    Render a character badge/chip.
    Usage: {% character_badge character size='sm' %}
    """
    return {
        'character': character,
        'size': size,
    }


@register.inclusion_tag('includes/connection_summary.html')
def connection_summary(event, direction='both', limit=3):
    """
    Render a summary of connections for an event.
    Usage: {% connection_summary event direction='outgoing' limit=5 %}
    """
    incoming = []
    outgoing = []
    
    if direction in ('both', 'incoming'):
        incoming = event.incoming_connections.all()[:limit]
    if direction in ('both', 'outgoing'):
        outgoing = event.outgoing_connections.all()[:limit]
    
    return {
        'event': event,
        'incoming': incoming,
        'outgoing': outgoing,
        'direction': direction,
    }


# =============================================================================
# ASSIGNMENT TAGS
# =============================================================================

@register.simple_tag(takes_context=True)
def get_related_events(context, event, limit=5):
    """
    Get events related to this one via connections.
    Usage: {% get_related_events event 5 as related_events %}
    """
    related_ids = set()
    
    # Get from outgoing connections
    for conn in event.outgoing_connections.all()[:limit]:
        related_ids.add(conn.to_event_id)
    
    # Get from incoming connections if we need more
    if len(related_ids) < limit:
        for conn in event.incoming_connections.all()[:limit - len(related_ids)]:
            related_ids.add(conn.from_event_id)
    
    # Remove self if present
    related_ids.discard(event.pk)
    
    from narrative.models import EventPage
    return EventPage.objects.filter(pk__in=related_ids).select_related('episode')


@register.simple_tag
def get_episode_context(event):
    """
    Get formatted episode context string.
    Usage: {% get_episode_context event as ep_context %}
    """
    season = event.episode.get_parent().specific
    return f"S{season.season_number}E{event.episode.episode_number}"


# =============================================================================
# STATISTICS TAGS
# =============================================================================

@register.simple_tag
def get_episode_acts(episode):
    """
    Get acts with their grouped scenes and events for an episode.
    Returns None if no acts exist (so templates can fall back to scene-only display).

    Usage: {% get_episode_acts page as acts_data %}
    """
    from narrative.models import Act, EventPage

    acts = Act.objects.filter(episode=episode).order_by('number')
    if not acts.exists():
        return None

    # Get all events for this episode, grouped by scene_sequence
    events = EventPage.objects.live().filter(episode=episode).order_by(
        'scene_sequence', 'sequence_in_scene'
    ).select_related('location')

    events_by_scene = {}
    for event in events:
        events_by_scene.setdefault(event.scene_sequence, []).append(event)

    result = []
    for act in acts:
        scenes = []
        for scene_num in sorted(act.scene_numbers):
            scene_events = events_by_scene.get(scene_num, [])
            if scene_events:
                scenes.append({'number': scene_num, 'events': scene_events})
        result.append({'act': act, 'scenes': scenes})

    return result


@register.simple_tag
def narrative_stats():
    """
    Get overall narrative statistics.
    Usage: {% narrative_stats as stats %}
    """
    from narrative.models import EventPage, CharacterPage, NarrativeConnection, Theme
    
    return {
        'event_count': EventPage.objects.live().count(),
        'character_count': CharacterPage.objects.live().count(),
        'connection_count': NarrativeConnection.objects.count(),
        'theme_count': Theme.objects.count(),
    }


@register.simple_tag
def character_stats(character):
    """
    Get statistics for a character.
    Usage: {% character_stats character as stats %}
    """
    participations = character.event_participations.all()

    return {
        'appearance_count': participations.count(),
        'episode_count': participations.values('event__episode').distinct().count(),
        'primary_count': participations.filter(importance='primary').count(),
    }


# =============================================================================
# CONTEXTUAL GRAPH URL TAG
# =============================================================================

@register.simple_tag(takes_context=True)
def contextual_graph_url(context):
    """
    Returns the appropriate graph URL based on the current page/object context.

    Usage: {% contextual_graph_url as graph_url %}

    Checks for:
    - page (Wagtail pages: EventPage, CharacterPage, EpisodePage, OrganizationPage)
    - object (Django detail views: Location, Theme, ConflictArc)

    Falls back to /graph/ landing page if no contextual graph is available.
    """
    from django.urls import reverse
    from narrative.models import (
        EventPage, CharacterPage, EpisodePage, OrganizationPage,
        Location, Theme, ConflictArc, ObjectPage
    )

    # Check for Wagtail page in context
    page = context.get('page') or context.get('self')
    if page:
        # Get the specific page type
        if hasattr(page, 'specific'):
            page = page.specific

        page_class = page.__class__.__name__

        if page_class == 'EventPage':
            return reverse('event_graph', kwargs={'identifier': page.pk})
        elif page_class == 'CharacterPage':
            return reverse('character_graph', kwargs={'identifier': page.pk})
        elif page_class == 'EpisodePage':
            return reverse('episode_graph', kwargs={'identifier': page.pk})
        elif page_class == 'OrganizationPage':
            return reverse('organization_graph', kwargs={'identifier': page.pk})
        elif page_class == 'ObjectPage':
            return reverse('object_graph', kwargs={'identifier': page.pk})
        elif page_class == 'SeasonPage':
            # For seasons, link to the first episode's graph or landing
            first_episode = page.get_children().live().first()
            if first_episode:
                return reverse('episode_graph', kwargs={'identifier': first_episode.pk})

    # Check for Django detail view object in context
    obj = context.get('object')
    if obj:
        obj_class = obj.__class__.__name__

        if obj_class == 'Location':
            return reverse('location_graph', kwargs={'identifier': obj.pk})
        elif obj_class == 'Theme':
            return reverse('theme_graph', kwargs={'identifier': obj.pk})
        elif obj_class == 'ConflictArc':
            return reverse('arc_graph', kwargs={'identifier': obj.pk})

    # Check for specific named context variables (for custom views)
    if context.get('location'):
        return reverse('location_graph', kwargs={'identifier': context['location'].pk})
    if context.get('theme'):
        return reverse('theme_graph', kwargs={'identifier': context['theme'].pk})
    if context.get('arc'):
        return reverse('arc_graph', kwargs={'identifier': context['arc'].pk})

    # Default to graph landing page
    return reverse('graph_view')


# =============================================================================
# NARRATIVE URL TAG - Universal page URL generation
# =============================================================================

@register.simple_tag(takes_context=True)
def narrative_url(context, page):
    """
    Generate the correct URL for any narrative page, regardless of Site configuration.

    This is a replacement for {% pageurl %} that works for multi-series setups
    where not all pages are under the current Site root.

    Usage: {% narrative_url event %}
           {% narrative_url character %}
           {% narrative_url episode %}

    For pages within a series context, generates series-scoped URLs like:
        /explore/star-trek-tng/events/event_uuid/
        /explore/star-trek-tng/characters/character_uuid/

    For pages without series context, generates global URLs like:
        /events/event_uuid/
        /characters/character_uuid/
    """
    from django.urls import reverse
    from narrative.models import (
        EventPage, CharacterPage, EpisodePage, SeasonPage, SeriesIndexPage,
        OrganizationPage, ObjectPage
    )

    if page is None:
        return ''

    # Get the specific page type
    if hasattr(page, 'specific'):
        page = page.specific

    page_class = page.__class__.__name__

    # Get identifier - prefer global_id, then fabula_uuid, then pk
    identifier = getattr(page, 'global_id', None) or getattr(page, 'fabula_uuid', None) or str(page.pk)

    # Find series context from the page's ancestry
    series_slug = None
    if hasattr(page, 'get_ancestors'):
        for ancestor in page.get_ancestors():
            if hasattr(ancestor, 'specific') and isinstance(ancestor.specific, SeriesIndexPage):
                series_slug = ancestor.specific.slug
                break

    # If no series from ancestry, try to get from current_series in context
    if not series_slug:
        current_series = context.get('current_series')
        if current_series:
            series_slug = current_series.slug

    # Map page types to URL names
    url_map = {
        'EventPage': ('series_event_detail', 'event_detail'),
        'CharacterPage': ('series_character_detail', 'character_detail'),
        'EpisodePage': ('series_episode_detail', None),  # Episodes always need series context
        'OrganizationPage': ('series_organization_detail', 'organization_detail'),
        'ObjectPage': ('series_object_detail', 'object_detail'),
    }

    if page_class in url_map:
        series_url_name, global_url_name = url_map[page_class]

        if series_slug:
            # Series-scoped URL
            return reverse(series_url_name, kwargs={
                'series_slug': series_slug,
                'identifier': identifier
            })
        elif global_url_name:
            # Global URL fallback
            return reverse(global_url_name, kwargs={'identifier': identifier})

    # For SeriesIndexPage
    if page_class == 'SeriesIndexPage':
        return reverse('series_landing', kwargs={'series_slug': page.slug})

    # For SeasonPage - link to first episode or series landing
    if page_class == 'SeasonPage':
        if series_slug:
            return reverse('series_landing', kwargs={'series_slug': series_slug})

    # For index pages (OrganizationIndexPage, CharacterIndexPage, etc.)
    index_url_map = {
        'OrganizationIndexPage': ('series_organization_index', 'organization_index'),
        'CharacterIndexPage': ('series_character_index', 'character_index'),
        'ObjectIndexPage': ('series_object_index', 'object_index'),
        'LocationIndexPage': ('series_location_index', 'location_index'),
    }
    if page_class in index_url_map:
        series_url_name, global_url_name = index_url_map[page_class]
        if series_slug:
            return reverse(series_url_name, kwargs={'series_slug': series_slug})
        else:
            return reverse(global_url_name)

    # Fallback to Wagtail's URL if available
    if hasattr(page, 'url') and page.url:
        return page.url

    return ''
