"""
Tool registry: OpenAI-style schemas + dispatch for the chat loop.

Tool descriptions carry the routing intelligence (which tool for which
question shape) — per the prior-art lesson that prompt engineering lives in
the tool docstrings as much as the system prompt.
"""

import json
import logging

from . import tools
from .tools import ToolError, get_series

logger = logging.getLogger(__name__)

_SERIES_PARAM = {
    'type': 'string',
    'description': 'Series slug. REQUIRED on every call — all archive data '
                   'is series-scoped.',
}


def _tool(name, description, params, required):
    return {
        'type': 'function',
        'function': {
            'name': name,
            'description': description,
            'parameters': {
                'type': 'object',
                'properties': params,
                'required': required,
            },
        },
    }


TOOL_SCHEMAS = [
    _tool(
        'resolve_entity',
        "Fuzzy search for any entity (character, organization, location, arc, "
        "theme, event) by name, alias, or role. THE ENTRY POINT whenever the "
        "user names someone or something you have not yet resolved this "
        "conversation, or describes them indirectly ('the king's secretary'). "
        "If several candidates return, ask the user which they mean or pick "
        "the obvious one and say so.",
        {
            'series': _SERIES_PARAM,
            'query': {'type': 'string',
                      'description': 'Name, alias, role, or description '
                                     'fragment to search for.'},
            'entity_type': {
                'type': 'string',
                'enum': ['character', 'organization', 'location', 'arc',
                         'theme', 'event'],
                'description': 'Optional: restrict to one entity type.'},
        },
        ['series', 'query'],
    ),
    _tool(
        'get_character',
        "Full profile of one character: description, traits, role, "
        "affiliations, importance tier, arcs and themes they belong to, most "
        "frequent co-participants, appearance counts. Use for 'who is X?' "
        "and as grounding before deeper character questions.",
        {
            'series': _SERIES_PARAM,
            'character': {'type': 'string',
                          'description': 'Character name or uuid.'},
        },
        ['series', 'character'],
    ),
    _tool(
        'character_timeline',
        "A character's journey event by event, in story order, with what they "
        "did, felt, and wanted at each moment (the participation edge data). "
        "Use for 'what happens to X?', 'how does X change?', 'walk me "
        "through X's story'. Filter by season for long journeys.",
        {
            'series': _SERIES_PARAM,
            'character': {'type': 'string'},
            'season': {'type': 'integer',
                       'description': 'Optional season filter.'},
            'limit': {'type': 'integer',
                      'description': 'Max events (default 20, max 40).'},
        },
        ['series', 'character'],
    ),
    _tool(
        'relationship_history',
        "Every event two characters share, in story order, with EACH side's "
        "actions and emotional state at each event. THE tool for 'how did X "
        "and Y's relationship evolve?', 'when do X and Y first meet?', "
        "'what is between X and Y?'.",
        {
            'series': _SERIES_PARAM,
            'character_a': {'type': 'string'},
            'character_b': {'type': 'string'},
            'limit': {'type': 'integer',
                      'description': 'Max shared events (default 15).'},
        },
        ['series', 'character_a', 'character_b'],
    ),
    _tool(
        'get_episode',
        "One episode: logline, summary, tone, writing credits, and its full "
        "event list in scene order. Use for 'what happens in S2E3?' and to "
        "anchor episode-level questions before drilling into events.",
        {
            'series': _SERIES_PARAM,
            'season': {'type': 'integer'},
            'episode': {'type': 'integer'},
        },
        ['series', 'season', 'episode'],
    ),
    _tool(
        'list_storylines',
        "All conflict arcs and themes in a series with event counts. Use for "
        "'what are the big storylines?', 'what themes run through this?', "
        "and to discover what arc names exist before calling get_arc.",
        {'series': _SERIES_PARAM},
        ['series'],
    ),
    _tool(
        'get_arc',
        "One conflict arc: description, type, involved characters, and its "
        "member events in story order with structural roles (START / CLIMAX "
        "/ RESOLUTION). Use for 'trace the X storyline', 'how does the "
        "conflict between X and Y build?'.",
        {
            'series': _SERIES_PARAM,
            'arc': {'type': 'string', 'description': 'Arc title or uuid.'},
        },
        ['series', 'arc'],
    ),
    _tool(
        'connections_for_event',
        "The narrative-connection edges into and out of one event: what "
        "caused it, what it causes, what it foreshadows or echoes — each "
        "edge with type, strength, and the analytical claim explaining WHY "
        "the events connect. Use for 'what led to this?', 'what does this "
        "set up?', 'why does this moment matter?'.",
        {
            'series': _SERIES_PARAM,
            'event': {'type': 'string',
                      'description': 'Event title or uuid.'},
        },
        ['series', 'event'],
    ),
    _tool(
        'connection_path',
        "Shortest chain of narrative connections linking two events, hop by "
        "hop with each edge's type and reasoning. THE showcase tool for "
        "'what links A to B?', 'how do we get from X to Y?' across "
        "episodes or seasons.",
        {
            'series': _SERIES_PARAM,
            'from_event': {'type': 'string'},
            'to_event': {'type': 'string'},
            'max_hops': {'type': 'integer',
                         'description': 'Max path length (default 4, max 6).'},
        },
        ['series', 'from_event', 'to_event'],
    ),
    _tool(
        'search_events',
        "Keyword search over event titles, descriptions, and key dialogue. "
        "Use to find WHERE something happens when the user quotes dialogue, "
        "describes a scene, or asks about a topic ('events about the "
        "annulment'). Then follow up with connections_for_event on hits.",
        {
            'series': _SERIES_PARAM,
            'query': {'type': 'string'},
            'season': {'type': 'integer',
                       'description': 'Optional season filter.'},
            'limit': {'type': 'integer',
                      'description': 'Max results (default 10, max 20).'},
        },
        ['series', 'query'],
    ),
    _tool(
        'graph_stats',
        "Counts for one series: seasons covered, episodes, events, "
        "characters, connections by type, cross-episode and season-bridging "
        "totals. Use to answer 'what does the archive hold?', to state "
        "coverage honestly, and to ground proud-provenance claims about the "
        "graph itself.",
        {'series': _SERIES_PARAM},
        ['series'],
    ),
]

TOOL_NAMES = {t['function']['name'] for t in TOOL_SCHEMAS}

_IMPLEMENTATIONS = {
    'resolve_entity': tools.resolve_entity,
    'get_character': tools.get_character,
    'character_timeline': tools.character_timeline,
    'relationship_history': tools.relationship_history,
    'get_episode': tools.get_episode,
    'list_storylines': tools.list_storylines,
    'get_arc': tools.get_arc,
    'connections_for_event': tools.connections_for_event,
    'connection_path': tools.connection_path,
    'search_events': tools.search_events,
    'graph_stats': tools.graph_stats,
}


def execute_tool(name, args):
    """Run one tool call. Always returns a JSON-serializable dict —
    failures become {'error': ...} payloads the model can react to."""
    if name not in _IMPLEMENTATIONS:
        return {'error': f'Unknown tool: {name}'}
    if not isinstance(args, dict):
        return {'error': 'Tool arguments must be an object.'}

    try:
        series = get_series(args.pop('series', None) or '')
        result = _IMPLEMENTATIONS[name](series, **args)
        return result if isinstance(result, dict) else {'result': result}
    except ToolError as exc:
        return {'error': str(exc)}
    except TypeError as exc:
        # Bad/missing parameters from the model — reflect back for retry.
        return {'error': f'Invalid arguments for {name}: {exc}'}
    except (ValueError, KeyError) as exc:
        return {'error': f'{name} failed on these arguments: {exc}'}
    except Exception:
        logger.exception('Tool %s crashed (args=%s)', name, args)
        return {'error': f'{name} hit an internal error. Try a different '
                         f'tool or different arguments.'}


def serialize_result(result):
    """Compact JSON for the tool message (drop null noise at top level)."""
    if isinstance(result, dict):
        result = {k: v for k, v in result.items() if v is not None}
    return json.dumps(result, ensure_ascii=False, default=str)
