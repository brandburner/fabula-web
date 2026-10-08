"""Deterministic exploration engine over a projected world.

Position is a moment (an event). The room is that moment's primary
location. `next`/`back` step through presentation order; `go to <place>`
jumps to that place's next recorded moment, so moving in space is also a
move in time. Passages (look, watch, examine) are written once per
moment and persisted; everything else is computed from the record.

No database, transport, clock or model calls here. The world dict comes
from projection.build_world; the narrator supplies passages.
"""
import copy
import re

from .engine import normalize

VIEWPOINT = 'Unseen witness'
FREE_ACTIONS = ('help', 'map', 'journal', 'evidence', 'where')
STOPWORDS = {'the', 'of', 'and', 'at', 'in', 'on', 'a', 'an', 'to', 'for', 'with', 'his', 'her',
             'their', 'place', 'room', 'episode', 'night', 'day', 'stormy', 'central', 'main'}
VERB_ALIASES = {
    'look': 'look', 'l': 'look', 'look around': 'look', 'describe the room': 'look', 'where am i': 'where',
    'watch': 'watch', 'what is happening': 'watch', 'what happens': 'watch', 'what happened': 'watch',
    'listen': 'watch', 'observe': 'watch', 'what do i see': 'watch',
    'who': 'who', 'who is here': 'who', "who's here": 'who', 'people': 'who', 'who is present': 'who',
    'next': 'next', 'continue': 'next', 'go on': 'next', 'onward': 'next', 'wait': 'next', 'n': 'next',
    'later': 'next', 'what next': 'next', 'next moment': 'next',
    'back': 'back', 'previous': 'back', 'go back': 'back', 'earlier': 'back', 'previous moment': 'back',
    'leave': 'leave', 'exit': 'leave', 'go out': 'leave', 'out': 'leave',
    'map': 'map', 'places': 'map', 'm': 'map', 'locations': 'map', 'where can i go': 'map',
    'where': 'where', 'journal': 'journal', 'j': 'journal', 'moments': 'journal', 'what have i seen': 'journal',
    'evidence': 'evidence', 'sources': 'evidence', 'show evidence': 'evidence', 'record': 'evidence',
    'help': 'help', 'h': 'help', '?': 'help', 'commands': 'help', 'what can i do': 'help',
}
EXAMINE = re.compile(r'^(examine|x|look at|inspect|study|look closely at|describe|what is|who is)\s+(.+)$')
MIND = re.compile(r'^(?:what does|what do)\s+(.+?)\s+(?:want|think|believe|feel|intend)\??$|^(?:mind|goals of|why|motives of|read)\s+(.+)$')
GO = re.compile(r'^(?:go to|go|enter|visit|walk to|move to|travel to|head to|return to|goto)\s+(.+)$')


def block(text, kind='narration'):
    return {'text': text, 'kind': kind}


def ensure_index(world):
    if 'index' not in world:
        world['index'] = {e['uuid']: i for i, e in enumerate(world['events'])}
    return world


def event_of(world, state):
    return world['events'][ensure_index(world)['index'][state['event']]]


def room_of(world, event):
    return world['locations'].get(event['location']) if event['location'] else None


def label(world, event):
    n = len(world['events'])
    time = f"Moment {event['ordinal'] + 1} of {n} · Scene {event['scene']}"
    return time + (' · a recollection' if event['flashback'] else '')


def header(world, event):
    room = room_of(world, event)
    lines = [(room['name'] if room else 'AN UNRECORDED PLACE').upper(), label(world, event) + ' · ' + event['title']]
    if event['participants']:
        lines.append('Present: ' + ', '.join(p['name'] for p in event['participants']) + '.')
    if event['objects']:
        lines.append('Here: ' + ', '.join(o['name'] for o in event['objects']) + '.')
    return '\n'.join(lines)


def opening(world):
    ep = world['episode']
    text = (ep['logline'] + '\n\n' if ep['logline'] else '')
    return text + ('You are an unseen witness inside a recorded episode. Nothing here was written by hand: '
                   'every place, person and object comes from Fabula’s narrative graph, and each passage is '
                   'written from that record the first time you ask for it.\n\n'
                   'Walk its places, step through its moments, and look closely. Type look to begin.')


def new_state(world):
    first = world['events'][0]
    ep = world['episode']
    return {'event': first['uuid'], 'visited': [first['uuid']], 'seen': [], 'frozen': False,
            'parser_aliases': {}, 'moves': 0, 'model_calls': 0, 'authored': 0, 'replays': 0,
            'transcript': [block(f"{world['series']['title'].upper()}\n{ep['title']} · S{ep['season']:02d}E{ep['number']:02d}", 'title'),
                           block(opening(world)), block(header(world, first))]}


def moments_of(world, uuid):
    loc = world['locations'][uuid]
    return sorted(set(loc['moments']) | set(loc['mentions']))


def go_targets(world, event):
    return [u for u, loc in world['locations'].items()
            if loc['in_episode'] and u != event['location'] and (loc['moments'] or loc['mentions'])]


def available(world, state):
    event = event_of(world, state)
    acts = ['look', 'watch', 'who', 'where', 'map', 'journal', 'evidence', 'help']
    if event['ordinal'] < len(world['events']) - 1:
        acts.append('next')
    if event['ordinal'] > 0:
        acts.append('back')
    for part in event['participants']:
        acts += [f"char:{part['uuid']}", f"mind:{part['uuid']}"]
    acts += [f"obj:{o['uuid']}" for o in event['objects']]
    acts += [f'go:{u}' for u in go_targets(world, event)]
    room = room_of(world, event)
    if room and room['parent'] and f"go:{room['parent']}" in acts:
        acts.append('leave')
    return acts


def passage_key(state, action):
    if action in ('look', 'watch'):
        return f"{action}:{state['event']}"
    if action.startswith(('char:', 'obj:')):
        return f"{action}@{state['event']}"
    return None


def passage_label(world, key):
    kind, _, rest = key.partition(':')
    target, _, event_uuid = rest.partition('@')
    event = world['events'][ensure_index(world)['index'][event_uuid or target]]
    if kind == 'look':
        return 'the view · ' + event['title']
    if kind == 'watch':
        return 'what happens · ' + event['title']
    pool = world['characters'] if kind == 'char' else world['objects']
    return pool[target]['name'] + ' · ' + event['title']


def needs_passage(world, state, action):
    """The passage key an action reads, if it reads one. Passages belong to
    the world (see store.py); a visitor's state only records which it has seen."""
    key = passage_key(state, action)
    return key if key and action in available(world, state) else None


def seen(state):
    # Saves from before shared passages kept text per visitor under 'passages'.
    return set(state.get('seen') or ()) | set(state.get('passages') or ())


def destination(world, event, loc_uuid):
    """Next moment recorded *at* that place after the current one, else its
    first; only a place with no moments of its own falls back to mentions."""
    loc = world['locations'][loc_uuid]
    ords = sorted(loc['moments']) or sorted(set(loc['mentions']))
    if not ords:
        return None
    later = [o for o in ords if o > event['ordinal']]
    return world['events'][later[0] if later else ords[0]]


def suggestions(world, state):
    event = event_of(world, state)
    passages = seen(state)
    if f"look:{event['uuid']}" not in passages:
        return ['look', 'who is here', 'map']
    if f"watch:{event['uuid']}" not in passages:
        return ['watch', 'next', 'map']
    for part in event['participants']:
        if f"char:{part['uuid']}@{event['uuid']}" not in passages:
            return ['examine ' + stem_of(part['name']), 'next', 'map']
    for obj in event['objects']:
        if f"obj:{obj['uuid']}@{event['uuid']}" not in passages:
            return ['examine ' + stem_of(obj['name']), 'next', 'map']
    return ['next', 'map', 'journal']


def stem_of(name):
    return re.sub(r'\s*\([^)]*\)', '', name).strip(' -–')


def map_text(world, state):
    event = event_of(world, state)
    locations = world['locations']
    visited_rooms = {world['events'][ensure_index(world)['index'][u]]['location'] for u in state['visited']}
    lines = ['PLACES IN THIS EPISODE', 'Containment is recorded; it is not a walkable route. '
             '“Go to” a place jumps to its next recorded moment.', '']

    def walk(uuid, depth):
        loc = locations[uuid]
        count = len(moments_of(world, uuid))
        if loc['in_episode'] or any(locations[c]['in_episode'] for c in loc['children']):
            mark = '▶' if uuid == event['location'] else ('·' if uuid in visited_rooms else ' ')
            kind = '' if loc['room'] else (' (feature)' if loc['in_episode'] else ' (beyond this episode)')
            lines.append(f"{mark} {'  ' * depth}{loc['name']}{kind} · {count} moment{'s' if count != 1 else ''}")
            for child in loc['children']:
                walk(child, depth + 1)

    roots = sorted((u for u, l in locations.items() if not l['parent']), key=lambda u: -len(moments_of(world, u)))
    for root in roots:
        walk(root, 0)
    return '\n'.join(lines)


def transition(world, state, action, passage=None, fresh=False):
    """passage: the world's passage for this action, if it reads one (None if
    unwritten). fresh: this visitor's turn is the one that wrote it."""
    state = copy.deepcopy(state)
    if 'passages' in state:
        state['seen'] = sorted(seen(state))
        del state['passages']
    state.setdefault('seen', [])
    out = []
    event = event_of(world, state)

    def say(text, kind='narration'):
        out.append(block(text, kind))

    def move(target):
        nonlocal event
        previous_room = event['location']
        event = target
        state['event'] = target['uuid']
        if target['uuid'] not in state['visited']:
            state['visited'].append(target['uuid'])
            say('New moment · ' + target['title'], 'discovery')
        if target['location'] != previous_room and previous_room is not None:
            say('You are somewhere else now.', 'hint')
        say(header(world, target))

    if action not in available(world, state):
        say('That action is not available here. Try ' + ', '.join(suggestions(world, state)) + '.', 'system')
        return state, out
    if action not in FREE_ACTIONS:
        state['moves'] += 1
    key = passage_key(state, action)
    if key:
        if passage is None:
            if state['frozen']:
                say('This passage has not been written yet. The world is frozen; written passages and the record still work. Enable the author to write it.', 'system')
                state['moves'] -= 1
                return state, out
            raise ValueError('A passage must be written before committing this action.')
        if fresh:
            state['authored'] += 1
            say('A passage becomes part of this world · ' + passage_label(world, key), 'written')
        else:
            state['replays'] += 1
        if key not in state['seen']:
            state['seen'].append(key)
        say(passage['text'])
        if action == 'look':
            names = [stem_of(p['name']) for p in event['participants'][:2]] + [stem_of(o['name']) for o in event['objects'][:1]]
            say('You can watch what happens here' + (', or examine ' + ' / '.join(names) if names else '') + '.', 'hint')
        elif action == 'watch':
            say('Continue to the next moment, go to another place, or examine someone here.', 'hint')
    elif action == 'who':
        if event['participants']:
            say('PRESENT\n' + '\n'.join(f"{p['name']}" + (f" · {p['importance']}" if p['importance'] else '') for p in event['participants']))
        else:
            say('The record names no one present at this moment.')
        if event['objects']:
            say('HERE\n' + '\n'.join(o['name'] for o in event['objects']))
    elif action.startswith('mind:'):
        part = next(p for p in event['participants'] if p['uuid'] == action[5:])
        lines = ["THE RECORD’S READING OF " + part['name'].upper(), '(interpretation in the source analysis, not observation)']
        if part['emotional_state']:
            lines.append('State: ' + part['emotional_state'])
        if part['goals']:
            lines.append('Goals: ' + ' / '.join(part['goals']))
        if part['beliefs']:
            lines.append('Beliefs: ' + ' / '.join(part['beliefs']))
        say('\n'.join(lines))
    elif action == 'next':
        say('You follow the story onward.')
        move(world['events'][event['ordinal'] + 1])
    elif action == 'back':
        say('You step back to the previous moment.')
        move(world['events'][event['ordinal'] - 1])
    elif action.startswith('go:') or action == 'leave':
        target_uuid = room_of(world, event)['parent'] if action == 'leave' else action[3:]
        target = destination(world, event, target_uuid)
        loc = world['locations'][target_uuid]
        if target is None:
            say('That place has no recorded moment in this episode.', 'system')
            state['moves'] -= 1
            return state, out
        if target['ordinal'] < event['ordinal']:
            say(f"You go to {loc['name']}. The story has no later moment there, so you return to its first.")
        else:
            say(f"You go to {loc['name']}.")
        if target['location'] != target_uuid:
            say(f"{loc['name']} is part of this moment, recorded within {room_of(world, target)['name']}.", 'hint')
        move(target)
    elif action == 'where':
        say(header(world, event))
    elif action == 'map':
        say(map_text(world, state))
    elif action == 'journal':
        index = ensure_index(world)['index']
        rows = [world['events'][index[u]] for u in state['visited']]
        say('YOUR JOURNAL · moments reached\n' + '\n'.join(
            f"{e['ordinal'] + 1}. {e['title']} — {room_of(world, e)['name'] if room_of(world, e) else 'unplaced'}" for e in rows))
    elif action == 'evidence':
        say('SOURCE RECORD\nEvent ' + event['uuid'] + (f"\n{event['url']}" if event['url'] else '') +
            '\nLocation ' + (event['location'] or '—') +
            '\nParticipants ' + ', '.join(p['uuid'] for p in event['participants']) +
            '\nObjects ' + (', '.join(o['uuid'] for o in event['objects']) or '—') +
            '\n\nRecorded analysis (retrospective; not shown to the narrator):\n' + (event['description'] or '—') +
            (('\n\nLocation record (series-wide; not shown to the narrator):\n' + room_of(world, event)['description'])
             if room_of(world, event) and room_of(world, event)['description'] else ''))
    elif action == 'help':
        say('Look at the place. Watch what happens. Examine someone or something present. '
            'Ask what a person wants. Continue or go back through the moments. Go to a place from the map; leave a room for the one that contains it.\n\n'
            'Try: ' + ' / '.join(suggestions(world, state)) +
            '\n\nJournal lists moments reached. Evidence shows the graph records behind this moment. Passages are written from the record the first time you ask and kept for this playthrough.')
    return state, out


def state_key(state):
    return state['event']


def scene_of(world, event):
    room = room_of(world, event)
    return {'name': room['name'] if room else 'An unrecorded place',
            'place': ' › '.join(reversed([world['locations'][u]['name'] for u in _chain(world, room['uuid'])])) if room else '',
            'time': label(world, event)}


def _chain(world, uuid):
    out, seen = [], set()
    while uuid and uuid in world['locations'] and uuid not in seen:
        seen.add(uuid)
        out.append(uuid)
        uuid = world['locations'][uuid]['parent']
    return out


NO_STATS = {'written': 0, 'llm': 0, 'recent': []}


def public_state(world, state, version, run_id, author_backend, stats=None):
    """stats: the world's shared passage counts (store.stats); the writing
    room reports the world, not one visitor."""
    stats = stats or NO_STATS
    event = event_of(world, state)
    index = ensure_index(world)['index']
    return {'version': version, 'run_id': str(run_id), 'revision': world['revision'],
            'scene': scene_of(world, event), 'viewpoint': VIEWPOINT, 'state_key': state_key(state), 'props': {},
            'moves': state['moves'],
            'discoveries': [{'title': world['events'][index[u]]['title'],
                             'text': (room_of(world, world['events'][index[u]]) or {'name': ''})['name']} for u in state['visited']],
            'transcript': state['transcript'], 'suggestions': suggestions(world, state),
            'frozen': state['frozen'], 'author_backend': author_backend,
            'authored': stats['written'], 'slot_count': world['report']['passage_slots'], 'replays': state['replays'],
            'model_calls': stats['llm'], 'seen': len(seen(state)),
            'objects': [{'id': key, 'name': passage_label(world, key), 'backend': backend}
                        for key, backend in stats['recent']]}


def restart(world, state):
    fresh = new_state(world)
    fresh.update({k: state[k] for k in ('authored', 'model_calls', 'frozen', 'parser_aliases') if k in state})
    return fresh


# ---------------------------------------------------------------- parsing

def variants(name):
    """Phrases a player might type for an entity name."""
    base = name.lower().replace('’', "'")
    stem = stem_of(base)
    out = {base, stem}
    out.update(p.strip() for p in re.findall(r'\(([^)]*)\)', base))
    for phrase in list(out):
        out.add(re.sub(r'^(the|a|an)\s+', '', phrase))
        out.add(re.sub(r"^[^']+'s\s+", '', phrase))        # "cromwell's dark cloak" -> "dark cloak"
        # "york place - upper chamber": the part before the dash is the container,
        # like an owner, so only the part after it names the thing.
        out.add(re.sub(r'^.*\s+-\s+', '', phrase))          # -> "upper chamber"
    # Shortcut words come from the thing itself, never its owner:
    # "catherine cawood's terrace house" offers "terrace house", not "catherine".
    words = [w for w in re.findall(r"[a-z0-9']+", thing_part(stem)) if w not in STOPWORDS]
    if words:
        out.add(words[-1])
        if len(words) > 1:
            out.add(' '.join(words[-2:]))
            out.add(' '.join(words[:2]))
            out.add(words[0])
    return {v.strip() for v in out if len(v.strip()) >= 3}


OWNER = re.compile(r"[a-z0-9 .\-]+'s\s+")


def thing_part(text):
    """Drop possessive owner phrases: "clare's mug (from catherine's pot)" -> "mug (pot)"."""
    return re.sub(r'\s+', ' ', OWNER.sub(' ', text)).strip()


def core_names(name):
    lowered = name.lower().replace('’', "'")
    return {lowered, stem_of(lowered), re.sub(r'^(the|a|an)\s+', '', stem_of(lowered))}


def match(noun, entities, owner_ok=False):
    """entities: list of (id, name). Exact name beats a variant beats a word
    inside the name; ties are ambiguous. A noun that only names an owner
    ("catherine" in "catherine's sunglasses") never identifies the thing,
    except for places when owner_ok: "go to catherine" can mean her house."""
    scored = []
    word = r'(?<![a-z0-9])' + re.escape(noun) + r"(?![a-z0-9])"
    for ident, name in entities:
        lowered = name.lower().replace('’', "'")
        if noun in core_names(name):
            scored.append((3, ident, name))
        elif noun in variants(name):
            scored.append((2, ident, name))
        elif re.search(word, thing_part(lowered)):
            scored.append((1, ident, name))
        elif owner_ok and re.search(word, lowered):
            scored.append((1, ident, name))
    if not scored:
        return []
    best = max(s for s, _, _ in scored)
    return [(ident, name) for s, ident, name in scored if s == best]


def clean_noun(noun):
    noun = noun.strip().replace('’', "'")
    noun = re.sub(r'^(the|a|an|at|to|into|towards|my)\s+', '', noun)
    return re.sub(r'\s+', ' ', noun).strip(' .?!')


def parse(world, state, command):
    """Return (status, payload): ('action', id) | ('ambiguous', [names]) |
    ('absent', name) | ('unknown', None). Never substitutes a target."""
    clean = normalize(command)
    if clean in VERB_ALIASES:
        return 'action', VERB_ALIASES[clean]
    event = event_of(world, state)
    acts = available(world, state)
    learned = state.get('parser_aliases', {}).get(clean)
    if learned in acts:
        return 'action', learned
    present = [(f"char:{p['uuid']}", p['name']) for p in event['participants']] + \
              [(f"obj:{o['uuid']}", o['name']) for o in event['objects']]
    places = [(f'go:{u}', world['locations'][u]['name']) for u in go_targets(world, event)]
    here = [(None, world['locations'][event['location']]['name'])] if event['location'] else []

    m = MIND.match(clean)
    if m:
        noun = clean_noun(m.group(1) or m.group(2))
        found = match(noun, [(f"mind:{p['uuid']}", p['name']) for p in event['participants']])
        if len(found) == 1:
            return 'action', found[0][0]
        if found:
            return 'ambiguous', [n for _, n in found]
        if match(noun, [(c['uuid'], c['name']) for c in world['characters'].values()]):
            return 'absent', noun
        return 'unknown', None
    m = EXAMINE.match(clean)
    if m:
        noun = clean_noun(m.group(2))
        if noun in ('room', 'around', 'here', 'place', 'this place'):
            return 'action', 'look'
        found = match(noun, present)
        if len(found) == 1:
            return 'action', found[0][0]
        if found:
            return 'ambiguous', [n for _, n in found]
        if match(noun, here):
            return 'action', 'look'
        if match(noun, [(c['uuid'], c['name']) for c in world['characters'].values()] +
                       [(o['uuid'], o['name']) for o in world['objects'].values()]):
            return 'absent', noun
        found = [f for f in match(noun, places) if noun in variants(f[1])]
        if len(found) == 1:
            return 'action', found[0][0]
        if found:
            return 'ambiguous', [n for _, n in found]
        return 'unknown', None
    m = GO.match(clean)
    noun = clean_noun(m.group(1) if m else clean)
    if here and noun in core_names(here[0][1]):
        return 'action', 'where'                                   # already in that room
    found = container_of(world, match(noun, places, owner_ok=True))
    if len(found) == 1:
        return 'action', found[0][0]
    if found:
        return 'ambiguous', [n for _, n in found]
    if match(noun, here):
        return 'action', 'where'
    if m and match(noun, [(u, l['name']) for u, l in world['locations'].items()]):
        return 'absent', noun
    return 'unknown', None


def container_of(world, found):
    """If one candidate place contains all the others, it is the one meant:
    "go to the farm" means the farm, not its yard."""
    if len(found) < 2:
        return found
    for ident, name in found:
        uuid = ident[3:]
        if all(uuid in _chain(world, other[3:])[1:] for other, _ in found if other != ident):
            return [(ident, name)]
    return found


def descriptor(world, action):
    verb, _, target = action.partition(':')
    if verb in ('char', 'obj', 'mind'):
        pool = world['characters'] if verb != 'obj' else world['objects']
        return {'action': action, 'verb': 'examine' if verb != 'mind' else 'mind', 'target': pool[target]['name']}
    if verb == 'go':
        return {'action': action, 'verb': 'go', 'target': world['locations'][target]['name']}
    return {'action': action, 'verb': verb, 'target': verb}


def candidates(world, state, command):
    """Available actions whose target shares a meaningful word with the command.
    The model may only choose among these; it cannot invent a referent."""
    if re.search(r'\b(and|then|or|not|never)\b|[;.]|don.t', command):
        return []
    words = {w for w in re.findall(r"[a-z0-9']+", command.lower().replace('’', "'")) if len(w) >= 4 and w not in STOPWORDS}
    if not words:
        return []
    out = []
    for action in available(world, state):
        item = descriptor(world, action)
        if item['verb'] in ('examine', 'mind', 'go'):
            target_words = {w for w in re.findall(r"[a-z0-9']+", item['target'].lower().replace('’', "'")) if w not in STOPWORDS}
            if words & target_words:
                out.append(item)
    return out


def refusal(world, state, status, payload):
    if status == 'ambiguous':
        shown = payload[:5] + ([f'{len(payload) - 5} more'] if len(payload) > 5 else [])
        return [block('Which do you mean: ' + ' or '.join(shown) + '?', 'system')]
    if status == 'absent':
        return [block(f'“{payload}” is in the record, but not at this moment. Try the map, or continue.', 'system')]
    return [block('I cannot identify that here. Try naming someone or something present, a place from the map, or type look.', 'system'),
            block('Try ' + ', '.join(suggestions(world, state)) + '.', 'hint')]


def aliases(world):
    """Verbatim phrase table for the offline edition: verbs plus one canonical phrase per entity per moment."""
    table = dict(VERB_ALIASES)
    for loc_uuid, loc in world['locations'].items():
        if loc['in_episode'] and (loc['moments'] or loc['mentions']):
            for v in variants(loc['name']):
                table.setdefault('go to ' + v, f'go:{loc_uuid}')
    return table


def compile_world(world, state, passages=None, stats=None):
    """Finite transition table: one state per moment, with the world's
    shared passages as written so far (passages: key -> passage)."""
    passages = passages or {}
    states = {}
    for event in world['events']:
        sample = copy.deepcopy(state)
        sample.update(event=event['uuid'], visited=[event['uuid']], frozen=True, moves=0, replays=0)
        acts = available(world, sample)
        actions = {}
        for action in acts:
            after, response = transition(world, sample, action, passages.get(passage_key(sample, action) or ''))
            actions[action] = {'next': state_key(after), 'blocks': response, 'move': after['moves'], 'replay': after['replays']}
        local = {}
        for part in event['participants']:
            for v in variants(part['name']):
                local.setdefault('examine ' + v, f"char:{part['uuid']}")
                local.setdefault('what does ' + v + ' want', f"mind:{part['uuid']}")
        for obj in event['objects']:
            for v in variants(obj['name']):
                local.setdefault('examine ' + v, f"obj:{obj['uuid']}")
        local.update({phrase: action for phrase, action in sample.get('parser_aliases', {}).items() if action in acts})
        states[event['uuid']] = {'scene': scene_of(world, event), 'discoveries': [], 'props': {},
                                 'aliases': local, 'suggestions': suggestions(world, sample), 'actions': actions}
    return {'states': states, 'aliases': aliases(world),
            'initial': public_state(world, new_state(world), 0, 'offline', 'disabled', stats),
            'saved': public_state(world, state, 0, 'offline', 'disabled', stats), 'revision': world['revision']}
