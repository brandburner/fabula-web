"""
Inbound payload validation and cross-turn tool_context handling.

The server is stateless: the client resends history and the previous turn's
tool_context each request. Both are client-controlled, so both get
sanitized on the way in — whitelisted tool names, whitelisted digest keys,
hard size caps (the transplant of the prior art's tool_context discipline).
"""

import json

from .registry import TOOL_NAMES

MAX_BODY_BYTES = 32 * 1024
MAX_MESSAGE_CHARS = 2000
MAX_HISTORY_ITEMS = 8
MAX_HISTORY_CHARS = 4000
MAX_TOOL_CONTEXT_ITEMS = 6
MAX_DIGEST_CHARS = 1500

DIGEST_KEYS = {
    'name', 'title', 'uuid', 'url', 'episode', 'series', 'slug',
    'type', 'query',
    # Nested single-entity anchors emitted by build_tool_context.
    'character_uuid', 'character_name', 'event_uuid', 'event_name',
    'from_event_uuid', 'from_event_name', 'to_event_uuid', 'to_event_name',
}
PAGE_CONTEXT_KEYS = {
    'page_type', 'title', 'entity_name', 'entity_uuid', 'entity_url',
    'series',
}


class BadPayload(Exception):
    pass


def parse_chat_payload(request):
    if len(request.body) > MAX_BODY_BYTES:
        raise BadPayload('Request too large.')
    try:
        data = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise BadPayload('Invalid JSON.')
    if not isinstance(data, dict):
        raise BadPayload('Payload must be an object.')

    message = str(data.get('message', '')).strip()[:MAX_MESSAGE_CHARS]
    if not message:
        raise BadPayload('Empty message.')

    history = []
    for item in (data.get('history') or [])[-MAX_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue
        role = item.get('role')
        if role not in ('user', 'assistant'):
            continue
        content = str(item.get('content', ''))[:MAX_HISTORY_CHARS]
        if content:
            history.append({'role': role, 'content': content})

    series = str(data.get('series', '') or '')[:100]

    page_context = None
    raw_page = data.get('page_context')
    if isinstance(raw_page, dict):
        page_context = {
            k: str(v)[:300]
            for k, v in raw_page.items()
            if k in PAGE_CONTEXT_KEYS and isinstance(v, (str, int))
        } or None

    return {
        'message': message,
        'history': history,
        'series': series,
        'page_context': page_context,
        'tool_context': sanitize_tool_context(data.get('tool_context')),
    }


def sanitize_tool_context(raw):
    """Client-echoed cross-turn grounding: whitelist and cap everything."""
    if not isinstance(raw, list):
        return []
    cleaned = []
    for item in raw[:MAX_TOOL_CONTEXT_ITEMS]:
        if not isinstance(item, dict):
            continue
        tool = item.get('tool')
        digest = item.get('digest')
        if tool not in TOOL_NAMES or not isinstance(digest, dict):
            continue
        slim = {}
        for key, value in digest.items():
            if key in DIGEST_KEYS and isinstance(value, (str, int, float)):
                slim[key] = str(value)[:200]
        if slim and len(json.dumps(slim)) <= MAX_DIGEST_CHARS:
            cleaned.append({'tool': tool, 'digest': slim})
    return cleaned


def build_tool_context(collected):
    """Compress this turn's tool results into next turn's grounding echo —
    just enough to keep entities resolved across turns."""
    context = []
    for call in collected[-MAX_TOOL_CONTEXT_ITEMS:]:
        result = call.get('result')
        if not isinstance(result, dict) or 'error' in result:
            continue
        digest = {}
        for key in DIGEST_KEYS:
            value = result.get(key)
            if isinstance(value, (str, int, float)) and value:
                digest[key] = str(value)[:200]
        # Nested single-entity refs (character/event blocks) are the most
        # valuable cross-turn anchors.
        for nested_key in ('character', 'event', 'from_event', 'to_event'):
            nested = result.get(nested_key)
            if isinstance(nested, dict) and nested.get('uuid'):
                digest[f'{nested_key}_uuid'] = str(nested['uuid'])[:200]
                label = nested.get('name') or nested.get('title', '')
                digest[f'{nested_key}_name'] = str(label)[:200]
        if digest:
            context.append({'tool': call['tool'], 'digest': digest})
    return context
