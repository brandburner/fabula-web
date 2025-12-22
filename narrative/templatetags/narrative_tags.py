"""
Narrative Template Tags

Custom template tags and filters for the Fabula narrative web.

Usage in templates:
    {% load narrative_tags %}
"""

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


# =============================================================================
# FILTERS
# =============================================================================

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
