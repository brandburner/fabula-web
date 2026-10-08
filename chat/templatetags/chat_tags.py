"""
Template tag mounting the Ask the Archive widget with page context.

The widget is context-aware (brief §4.4 entry points): a character page
opens the chat with that character pre-resolved; an event page with the
event pre-loaded. This tag inspects the template context and derives the
{page_type, entity, series} JSON the widget sends with every request.
"""

from django import template

from narrative.models import (
    CharacterPage,
    ConflictArc,
    EpisodePage,
    EventPage,
    Location,
    NarrativeConnection,
    OrganizationPage,
    SeriesIndexPage,
    Theme,
)

register = template.Library()


def _derive_entity(obj):
    """(page_type, entity_name, entity_uuid, entity_url, title) for the
    object under the cursor, or a generic fallback."""
    if isinstance(obj, CharacterPage):
        return ('character', obj.canonical_name,
                obj.fabula_uuid or str(obj.pk), obj.get_absolute_url(),
                obj.canonical_name)
    if isinstance(obj, EventPage):
        return ('event', obj.title, obj.fabula_uuid or str(obj.pk),
                obj.get_absolute_url(), obj.title)
    if isinstance(obj, EpisodePage):
        label = f'S{obj.season_number}E{obj.episode_number} — {obj.title}'
        return ('episode', label, obj.fabula_uuid or str(obj.pk), '', label)
    if isinstance(obj, NarrativeConnection):
        label = (f'{obj.from_event.title} → [{obj.connection_type}] → '
                 f'{obj.to_event.title}')
        return ('connection', label, obj.fabula_uuid or str(obj.pk),
                obj.get_absolute_url(), label)
    if isinstance(obj, ConflictArc):
        return ('arc', obj.title, obj.fabula_uuid or str(obj.pk),
                obj.get_absolute_url(), obj.title)
    if isinstance(obj, Theme):
        return ('theme', obj.name, obj.fabula_uuid or str(obj.pk),
                obj.get_absolute_url(), obj.name)
    if isinstance(obj, OrganizationPage):
        return ('organization', obj.canonical_name,
                obj.fabula_uuid or str(obj.pk), obj.get_absolute_url(),
                obj.canonical_name)
    if isinstance(obj, Location):
        return ('location', obj.canonical_name,
                obj.fabula_uuid or str(obj.pk), obj.get_absolute_url(),
                obj.canonical_name)
    if isinstance(obj, SeriesIndexPage):
        return ('series', None, None, f'/explore/{obj.slug}/', obj.title)
    return (None, None, None, None, None)


def _derive_series(obj, current_series):
    if isinstance(current_series, SeriesIndexPage):
        return current_series
    if isinstance(obj, SeriesIndexPage):
        return obj
    # Snippets carry a series FK; connections reach it via an endpoint.
    if isinstance(obj, (Theme, ConflictArc, Location)) and obj.series_id:
        return obj.series
    if isinstance(obj, NarrativeConnection):
        obj = obj.from_event
    if isinstance(obj, (CharacterPage, EventPage, EpisodePage,
                        OrganizationPage)):
        return obj.get_ancestors().type(SeriesIndexPage).specific().first()
    return None


@register.inclusion_tag('chat/widget.html', takes_context=True)
def chat_widget(context):
    if not context.get('chat_enabled'):
        return {'chat_enabled': False}

    obj = context.get('object') or context.get('page')
    page_type, entity_name, entity_uuid, entity_url, title = \
        _derive_entity(obj)
    series = _derive_series(obj, context.get('current_series'))

    if page_type is None:
        page_type = 'series' if series else 'catalog'
    if title is None:
        title = series.title if series else 'the catalog'

    return {
        'chat_enabled': True,
        'chat_context': {
            'page_type': page_type,
            'title': title,
            'entity_name': entity_name,
            'entity_uuid': entity_uuid,
            'entity_url': entity_url,
            'series': series.slug if series else '',
            'series_title': series.title if series else '',
        },
    }
