"""
Deterministic citation extraction (brief §2.6/§4.4): walk the turn's tool
results server-side and emit verified link cards deep-linking into the
catalog. No LLM involvement — every card's URL demonstrably came from the
graph this turn. This is what makes the chat a guide THROUGH the catalog
rather than a replacement for it.
"""

MAX_CARDS = 6

_KIND_BY_PREFIX = (
    ('/characters/', 'character'),
    ('/events/', 'event'),
    ('/connections/', 'connection'),
    ('/arcs/', 'arc'),
    ('/themes/', 'theme'),
    ('/organizations/', 'organization'),
    ('/locations/', 'location'),
    ('/explore/', 'series'),
)


def _kind_for(url):
    for prefix, kind in _KIND_BY_PREFIX:
        if url.startswith(prefix):
            return kind
    return 'page'


def _walk(node, found):
    """Collect every {url, title|name} dict in discovery order."""
    if isinstance(node, dict):
        url = node.get('url')
        if isinstance(url, str) and url.startswith('/'):
            label = node.get('title') or node.get('name')
            if label:
                found.append({
                    'url': url,
                    'title': str(label),
                    'kind': _kind_for(url),
                    'subtitle': node.get('episode') or
                    node.get('type') or node.get('role') or '',
                })
        for value in node.values():
            _walk(value, found)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _walk(item, found)


def extract_rich_links(collected):
    """collected = [{'tool', 'args', 'result'}, ...] from the loop."""
    found = []
    for call in collected:
        _walk(call.get('result'), found)

    cards, seen = [], set()
    for card in found:
        if card['url'] in seen:
            continue
        seen.add(card['url'])
        cards.append(card)
        if len(cards) >= MAX_CARDS:
            break
    return cards


def allowed_urls(collected):
    """Every internal URL that appeared in this turn's tool results —
    the allowlist for link hygiene on the model's own prose."""
    found = []
    for call in collected:
        _walk(call.get('result'), found)
    return {card['url'] for card in found}
