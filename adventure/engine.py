"""Finite game rules. No database, transport, clock or model calls here."""
import copy
import re
from itertools import product

from . import parser, props

from .scenario import COMMANDS, DISCOVERIES, OPENING, REVISION, SCENES, SEED, SLOTS, aliases


def normalize(command):
    command = re.sub(r'\s+', ' ', command.lower().strip().rstrip('.?!')).strip()
    for prefix in ('please ', 'can i ', 'could i ', 'i want to ', "i'd like to "):
        if command.startswith(prefix):
            command = command[len(prefix):]
    return command


def resolve(command, state=None):
    if command.strip() == '?':
        return 'help'
    clean = normalize(command)
    action = aliases().get(clean)
    if action is None and state is not None:
        action = state.get('parser_aliases', {}).get(state['scene'], {}).get(clean)
        if action not in [item['action'] for item in parser.candidates(clean, available(state))]:
            return None
    return action


def block(text, kind='narration'):
    return {'text': text, 'kind': kind}


def new_state():
    return {'scene': 'convent', 'discoveries': [], 'objects': {}, 'frozen': False,
            'props': dict(props.DEFAULTS), 'parser_aliases': {},
            'moves': 0, 'model_calls': 0, 'authored': 0, 'replays': 0,
            'transcript': [block('DRACULA\nThe things we carry · S01E01', 'title'),
                           block(OPENING), block(SCENES['convent']['text'])]}


def available(state):
    if state['scene'] == 'convent':
        result = ['mina', 'remember', 'agatha', 'blood']
    else:
        result = ['mirror', 'photograph', 'return']
    result += ['look', 'journal', 'inventory', 'map', 'help', 'evidence']
    if state['scene'] == 'convent':
        result += props.ACTIONS
    for slug, slot in SLOTS.items():
        if slot['scene'] == state['scene']:
            result.append(f'examine:{slug}')
            if slug in state['objects']:
                result.append(f'study:{slug}')
    return result


def suggestions(state):
    found = state['discoveries']
    if state['scene'] == 'castle':
        return ['examine mirror', 'examine photograph', 'return to agatha']
    physical = props.position(state)
    if 'bag' in state['objects'] and not physical['manuscript_read']:
        return ['read manuscript' if physical['bag_open'] or physical['manuscript_held'] else 'open bag', 'ask agatha about manuscript', 'remember the castle']
    if 'connection' in found:
        return ['journal', 'examine window', 'remember the castle']
    if 'private' not in found:
        return ['tell agatha about mina', 'look', 'examine window']
    if 'blood' not in found:
        return ['remember the castle', 'ask agatha about blood', 'examine bag']
    return ['ask agatha about blood', 'journal', 'remember the castle']


def state_key(state):
    return state['scene'] + ':' + ','.join(sorted(state['discoveries'])) + ':' + ''.join('1' if props.position(state)[k] else '0' for k in props.DEFAULTS)


def gap(state, action):
    if action and action.startswith(('examine:', 'read:')) and action in available(state):
        slug = action.split(':')[1]
        if slug not in SLOTS or (action.startswith('read:') and 'read' not in SLOTS[slug]):
            return None
        if SLOTS[slug].get('parent') and not props.accessible(state, slug):
            return None
        if slug == 'bag' and (not props.position(state)['bag_open'] or props.position(state)['manuscript_held']):
            return None
        if slug not in state['objects'] and not state['frozen']:
            return slug
    return None


def transition(state, action, authored=None):
    """Return new state + response; all discoveries are idempotent set additions."""
    state = copy.deepcopy(state)
    out = []

    def say(text, kind='narration'):
        out.append(block(text, kind))

    def discover(key):
        if key not in state['discoveries']:
            state['discoveries'].append(key)
            item = DISCOVERIES[key]
            say('Connection discovered · ' + item['title'] + '\n' + item['text'], 'discovery')

    if action not in available(state):
        say('That action is not available here. Try ' + ', '.join(suggestions(state)) + '.', 'system')
        return state, out
    if action not in ('help', 'map', 'journal', 'inventory', 'evidence'):
        state['moves'] += 1
    if props.handle(state, action, say):
        return state, out
    if action == 'look':
        say(SCENES[state['scene']]['text'])
        names = [SLOTS[k]['name'] for k in state['objects'] if SLOTS[k]['scene'] == state['scene']]
        if names:
            say('You have already examined: ' + ', '.join(names) + '.')
        if state['scene'] == 'convent':
            physical = props.position(state)
            say('Agatha’s bag is ' + ('open.' if physical['bag_open'] else 'closed.') + (' You are holding the manuscript.' if physical['manuscript_held'] else ''))
        if state['scene'] == 'convent' and 'connection' in state['discoveries']:
            say('The room has not changed. Your account has: you understand now why the Count knew Mina.')
    elif action == 'mina':
        say('You tell Agatha that Dracula described Mina’s hair in sunlight. It was a thought you had kept to yourself, even from Mina.\n\nAgatha asks you to return to the encounter. What else happened in that room?')
        discover('private')
    elif action == 'remember':
        state['scene'] = 'castle'
        say('You follow the memory back.\n\n' + SCENES['castle']['text'])
    elif action == 'return':
        state['scene'] = 'convent'
        say('The bedroom recedes. You are back in the convent, with Agatha waiting for the rest of your account.\n\n' + ('You can now tell her about the mirror and the blood.' if 'blood' in state['discoveries'] else 'The memory remains there when you need it.'))
    elif action == 'mirror':
        say('The shaving mirror is broken. You remember your cut thumb—and the Count speaking of blood as lives. The injury and those words belong to the same encounter.')
        discover('blood')
    elif action == 'photograph':
        say('Mina’s photograph stands on the dresser. A photograph could show her face. It could not tell him how you remembered her hair in sunlight.')
        discover('private')
    elif action == 'agatha':
        say('Agatha is attending closely to your account. Tell her what the Count knew about Mina, or ask about blood once you have recalled the encounter.')
    elif action == 'blood':
        if 'private' not in state['discoveries']:
            say('Agatha needs something specific to work with. Tell her what Dracula knew about Mina.')
        elif 'blood' not in state['discoveries']:
            say('You have given her the impossible knowledge. Now recall its circumstances: return to the castle bedroom and examine the mirror.')
        else:
            say('You put the private memory beside the blood drawn at the mirror. Agatha suggests that blood can carry a life’s stories. The Count had another way to learn what you had never spoken.')
            discover('connection')
            say('Investigation complete. You understand what connected the encounter to the private memory.\n\nYou can revisit the rooms, examine their remaining details, or read your journal.', 'closure')
    elif action == 'journal':
        say('YOUR JOURNAL\n' + '\n\n'.join(DISCOVERIES[k]['title'] + '\n' + DISCOVERIES[k]['text'] for k in DISCOVERIES if k in state['discoveries']) if state['discoveries'] else 'YOUR JOURNAL\nHow did Dracula know your private memory of Mina? Begin with what you can tell Agatha.')
    elif action == 'map':
        say('Convent\n  └ Jonathan’s room · the interview\n\nCastle Dracula\n  └ Jonathan’s bedroom · a recollection\n\n“Remember the castle” enters the recollection. “Return to Agatha” leaves it. These are two moments, not neighbouring rooms.')
    elif action == 'help':
        say('Look. Examine something. Ask Agatha about a subject. Tell her what you remember.\n\nTry: ' + ' / '.join(suggestions(state)) + '\n\nJournal keeps discoveries; inventory lists what you carry. Open or close Agatha’s bag, read the manuscript, then return it. Ask Agatha about the manuscript after reading. Map shows the two places. Evidence identifies the graph records.\n\nExamine a window, bag, fireplace or dresser in its room to write an unfinished detail. The Workshop below shows what has been saved.')
    elif action == 'evidence':
        keys = {'interview'}
        if state['scene'] == 'castle' or 'blood' in state['discoveries']:
            keys.add('bedroom')
        if 'connection' in state['discoveries']:
            keys.add('blood')
        say('SOURCE NOTES\nAn authored game adaptation of Fabula’s Dracula S1E1 graph export. Narration is paraphrased.\n\n' + '\n'.join(SEED['events'][k]['label'] + '\n' + SEED['events'][k]['uuid'] for k in sorted(keys)) + '\n\nGenerated object descriptions belong to this playthrough. They do not change the source graph.')
    elif action.startswith(('examine:', 'study:', 'read:')):
        slug = action.split(':')[1]
        if SLOTS[slug].get('parent') and not props.accessible(state, slug):
            say('The ' + slug + ' is inside Agatha’s closed bag. Open the bag first.', 'system')
            state['moves'] -= 1
            return state, out
        physical = props.position(state)
        if slug == 'bag' and (not physical['bag_open'] or physical['manuscript_held']):
            say('Agatha’s bag is closed.' if not physical['bag_open'] else 'The open bag contains the wooden stake and hammer. You are holding the manuscript.')
            return state, out
        if slug not in state['objects']:
            if state['frozen']:
                say('This detail has not been written. The world is frozen; its existing passages and investigation still work. Enable the author in the Workshop to fill this gap.', 'system')
                state['moves'] -= 1
                return state, out
            if authored is None:
                raise ValueError('An expansion must be authored before committing this action.')
            state['objects'][slug] = authored
            state['authored'] += 1
            say('A detail becomes part of this playthrough · ' + SLOTS[slug]['name'], 'written')
        else:
            state['replays'] += 1
        obj = state['objects'][slug]
        if action == 'read:manuscript':
            if not physical['manuscript_held']:
                say('Agatha lets you take the manuscript to consult it.', 'system')
            physical.update(manuscript_held=True, manuscript_read=True)
            state['props'] = physical
            say(obj['read'])
            say('You can ask Agatha about the manuscript, or return to the castle in memory.', 'hint')
        else:
            say(obj['detail'] if action.startswith('study:') else obj['description'])
        if action.startswith('examine:'):
            say('You can study ' + slug + ' more closely.', 'hint')
    return state, out


def public_state(state, version, run_id, author_backend):
    return {'version': version, 'run_id': str(run_id), 'revision': REVISION,
            'scene': SCENES[state['scene']], 'state_key': state_key(state), 'props': props.position(state),
            'moves': state['moves'], 'discoveries': [DISCOVERIES[k] for k in DISCOVERIES if k in state['discoveries']],
            'transcript': state['transcript'], 'suggestions': suggestions(state),
            'frozen': state['frozen'], 'author_backend': author_backend,
            'authored': state['authored'], 'slot_count': len(SLOTS), 'replays': state['replays'],
            'model_calls': state['model_calls'],
            'objects': [{'id': key, 'name': SLOTS[key]['name'], 'backend': value['backend']}
                        for key, value in state['objects'].items()]}


def compile_world(state):
    """Compile the finite rules, including containment and possession, to HTML."""
    states = {}
    for scene, discoveries, physical in product(
            SCENES, ([], ['private'], ['blood'], ['private', 'blood'], ['private', 'blood', 'connection']),
            product((False, True), repeat=len(props.DEFAULTS))):
        sample = copy.deepcopy(state)
        sample.update(scene=scene, discoveries=discoveries, frozen=True, moves=0, replays=0,
                      props=dict(zip(props.DEFAULTS, physical)))
        actions = {}
        for action in available(sample):
            after, response = transition(sample, action)
            actions[action] = {'next': state_key(after), 'blocks': response,
                               'move': after['moves'], 'replay': after['replays']}
        learned = sample.get('parser_aliases', {}).get(scene, {})
        scoped_aliases = {phrase: action for phrase, action in learned.items()
                          if action in [item['action'] for item in parser.candidates(phrase, available(sample))]}
        states[state_key(sample)] = {
            'scene': SCENES[scene], 'discoveries': [DISCOVERIES[k] for k in discoveries],
            'props': props.position(sample), 'aliases': scoped_aliases,
            'suggestions': suggestions(sample), 'actions': actions}
    return {'states': states, 'aliases': aliases(), 'initial': public_state(new_state(), 0, 'offline', 'disabled'),
            'saved': public_state(state, 0, 'offline', 'disabled'), 'revision': REVISION}
