"""Preserve explicitly named entities and verbs before asking a model for help."""
import re

from .scenario import MEMORY_TARGETS, MEMORY_VERBS, SLOTS

NAMES = {k: [k, slot['name'].lower().replace('’', "'")] for k, slot in SLOTS.items()}
NAMES.update({
    'agatha': ['agatha', 'sister agatha'], 'mina': ['mina'],
    'mirror': ['mirror', 'shaving mirror'], 'photograph': ['photograph', 'photo'],
    'castle': list(MEMORY_TARGETS), 'convent': ['convent'],
    'blood': ['blood', 'count', 'dracula'], 'journal': ['journal', 'discoveries'],
    'inventory': ['inventory'], 'map': ['map'], 'help': ['help'],
    'evidence': ['evidence', 'sources'], 'room': ['room'],
})
VERBS = {
    'look at': 'examine', 'examine': 'examine', 'inspect': 'examine', 'x': 'examine',
    'study': 'study', 'read': 'read', 'peruse': 'read',
    'take': 'take', 'get': 'take', 'pick up': 'take', 'borrow': 'take',
    'open': 'open', 'close': 'close', 'shut': 'close',
    'give': 'return', 'return': 'return', 'put': 'return',
    'ask': 'discuss', 'tell': 'discuss', 'discuss': 'discuss',
    'remember': 'remember', 'recall': 'remember',
    # Known unsupported actions must never become an examination or a read.
    'burn': 'burn', 'destroy': 'destroy', 'eat': 'eat', 'drink': 'drink',
    'attack': 'attack', 'kill': 'kill', 'hit': 'hit', 'throw': 'throw',
}
VERBS.update({verb: 'remember' for verb in MEMORY_VERBS})


def descriptor(action):
    if ':' in action:
        verb, target = action.split(':', 1)
        return {'action': action, 'verb': verb, 'target': target}
    verb, target = {
        'mirror': ('examine', 'mirror'), 'photograph': ('examine', 'photograph'),
        'agatha': ('discuss', 'agatha'), 'mina': ('discuss', 'mina'),
        'blood': ('discuss', 'blood'), 'remember': ('remember', 'castle'),
        'return': ('remember', 'convent'), 'look': ('examine', 'room'),
        'journal': ('read', 'journal'),
    }.get(action, (action, action))
    return {'action': action, 'verb': verb, 'target': target}


def targets(command):
    text = command.lower().replace('’', "'")
    # A compound place name such as Castle Dracula is one referent. Match
    # longest spans first so its embedded character name isn't a second target.
    matches = [(match.start(), match.end(), target)
               for target, names in NAMES.items() for name in names
               for match in re.finditer(r'(?<!\w)' + re.escape(name.replace('’', "'")) + r'(?!\w)', text)]
    accepted = []
    for start, end, target in sorted(matches, key=lambda item: -(item[1] - item[0])):
        if not any(start < other_end and end > other_start for other_start, other_end, _ in accepted):
            accepted.append((start, end, target))
    return {target for _, _, target in accepted}


def candidates(command, actions):
    """No noun substitution; no guessing a target for an ungrounded command.

    Agatha may be the addressee and bag the container. Other explicit nouns
    must identify the action's target. The model cannot invent referents.
    """
    if re.search(r'\b(and|then|or|not|never)\b|[;.]|don.t', command):
        return []
    mentioned = targets(command)
    if not mentioned:
        return []
    verb = next((v for phrase, v in sorted(VERBS.items(), key=lambda item: -len(item[0]))
                 if command.startswith(phrase + ' ')), None)
    if verb in ('examine', 'study', 'read', 'take', 'open', 'close'):
        phrase = next(p for p, v in sorted(VERBS.items(), key=lambda item: -len(item[0]))
                      if command.startswith(p + ' '))
        noun = command[len(phrase):].strip().removeprefix('the ').removeprefix('my ')
        if not any(noun == name or noun.startswith(name + ' ') for names in NAMES.values() for name in names):
            return []
    options = []
    for action in actions:
        item = descriptor(action)
        permitted = {item['target']}
        if item['verb'] == 'discuss' or item['verb'] in ('take', 'return'):
            permitted.add('agatha')
        if item['target'] in ('manuscript', 'stake', 'hammer'):
            permitted.add('bag')
        if item['target'] in mentioned and mentioned <= permitted:
            if verb is None or verb == item['verb']:
                options.append(item)
    return options


def refusal(command):
    named = targets(command)
    if named:
        return 'I cannot perform that action as phrased. Try one action on one object, such as “read manuscript” or “examine bag”.'
    return 'I cannot identify that here. Try naming something in the room, or type “look”.'
