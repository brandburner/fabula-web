"""An editorial game adaptation of a small, pinned local graph-export slice.

Narration is paraphrased, not presented as verbatim screenplay. The two
locations are scene anchors: 'remember' is not an invented physical exit.
See seed.json for the exact upstream evidence and content hashes.
"""
import json
from pathlib import Path

REVISION = 'dracula-interview-v1'
SEED = json.loads(Path(__file__).with_name('seed.json').read_text())
OPENING = (
    'You are Jonathan Harker. You have escaped Castle Dracula.\n'
    'Sister Agatha wants your account. One detail refuses to leave you:\n'
    'the Count knew something about Mina you had never told him.\n\n'
    'Find out how he knew.'
)
SCENES = {
    'convent': {
        'name': 'CONVENT ROOM', 'place': 'Convent / Jonathan’s room',
        'time': 'The interview', 'evidence': ['interview', 'blood'],
        'text': 'Daylight reaches into a plain room. You sit on the bed. Sister Agatha waits beside her bag; a silent nun watches.\n\nAgatha is listening. You have memories you would rather not examine.',
    },
    'castle': {
        'name': 'CASTLE BEDROOM', 'place': 'Castle Dracula / Jonathan’s bedroom',
        'time': 'A recollection · earlier', 'evidence': ['bedroom'],
        'text': 'You return to the bedroom in memory. A fire burns behind you. On the dresser: Mina’s photograph, your toiletries, and the broken shaving mirror.\n\nThe Count’s words about Mina are still clear. When you are ready, return to Agatha.',
    },
}
DISCOVERIES = {
    'private': {'title': 'A private memory', 'text': 'The Count described Mina’s hair in sunlight. You had never shared that thought.', 'source': 'blood'},
    'blood': {'title': 'Blood at the mirror', 'text': 'The broken mirror drew blood. In that encounter, Dracula spoke of blood as lives.', 'source': 'bedroom'},
    'connection': {'title': 'What the blood carried', 'text': 'Agatha connects the two: Dracula’s knowledge of Mina came through Jonathan’s blood. The private memory was part of what he took.', 'source': 'blood'},
}
# Fixed, source-backed expansion slots. The author writes these missing
# game objects; it never receives authority to invent an exit or award a clue.
SLOTS = {
    'window': {'scene': 'convent', 'name': 'window', 'source': 'blood',
               'facts': 'Sunlight comes through the window in Jonathan’s convent room. It illuminates an enclosed interview, not a new exit.',
               'local': ['Sunlight lies across the plain walls. At the window, the room seems briefly ordinary. Agatha’s waiting questions keep it from feeling safe.', 'The window lets daylight into the room. You turn toward it for a moment, then back toward the woman waiting for your account.'],
               'detail': 'The light belongs to this room and this moment. Looking outside supplies no new route through your memory.'},
    'bag': {'scene': 'convent', 'name': 'Agatha’s bag', 'source': 'interview',
            'facts': 'Agatha brings a heavy bag. It contains a manuscript, wooden stake and hammer. This inspection does not transfer ownership.',
            'local': ['A manuscript rests over a wooden stake and a hammer. Agatha has brought questions, but she has also prepared for an answer she may not like.', 'The bag is heavy for a simple visit. Beneath the manuscript are a hammer and a wooden stake. Agatha has come prepared.'],
            'detail': 'The objects remain in Agatha’s bag. Their purpose is unsettling enough without taking them.'},
    'fireplace': {'scene': 'castle', 'name': 'fireplace', 'source': 'bedroom',
                  'facts': 'A warm fireplace lights Jonathan’s bedroom in Castle Dracula. Curtains muffle the outside. This is a recollection.',
                  'local': ['The fire gives the bedroom a borrowed comfort. In memory, you can still feel how easy it was to mistake warmth for welcome.', 'Firelight warms the bedroom. Heavy curtains soften the sounds beyond it. You remember how reassuring those ordinary comforts first appeared.'],
                  'detail': 'You linger on the firelight, then turn back to the dresser. The memory’s important traces are still there.'},
    'dresser': {'scene': 'castle', 'name': 'dresser', 'source': 'bedroom',
                'facts': 'The dresser holds Mina’s photograph, Jonathan’s toiletries and his shaving mirror, broken during the encounter. Add no drawers, keys or objects.',
                'local': ['Mina’s photograph stands among your toiletries. Beside it, the shaving mirror is broken. Familiar possessions make an unfamiliar room more disturbing.', 'The dresser gathers the small things you brought to make the journey bearable: toiletries, a photograph, a shaving mirror. The mirror has not survived.'],
                'detail': 'The photograph and the mirror draw your attention for different reasons. Examine either to follow the memory.'},
}

# These children exist in the source before the model writes their prose.
# Behaviours below are editorial game rules, never LLM-authored Python.
SLOTS.update({
    'manuscript': {
        'scene': 'convent', 'name': 'manuscript', 'parent': 'bag', 'source': 'interview',
        'facts': 'Jonathan wrote an account of his experiences at Castle Dracula. Agatha uses it to question his incomplete recollections. It is in her bag unless Jonathan is consulting it. Do not describe its current position. Do not invent quotations, handwriting details or later revelations.',
        'local': ['This is your written account of Castle Dracula. Agatha has brought it to an interview in which your recollections are still incomplete.'],
        'detail': 'Writing an account and being able to explain it are different things. Agatha is testing the distance between the two.',
        'read_facts': 'Summarize, never quote, Jonathan’s account of his stay at Castle Dracula. The game has only an outline, not manuscript pages. Agatha is comparing that account with his incomplete recollections. End by inviting him to recall the castle bedroom. Do not reveal blood carrying memories, later corruption of the manuscript, or any new clue.',
        'read': 'You read back over your account of the stay at Castle Dracula. It records where you have been; it does not settle what happened to you. Agatha is waiting for what the written account leaves unexplained.\n\nThe bedroom is a place to begin remembering.',
    },
    'stake': {
        'scene': 'convent', 'name': 'wooden stake', 'parent': 'bag', 'source': 'interview',
        'facts': 'Agatha brought a wooden stake and hammer beneath Jonathan’s manuscript. These remain her tools. Do not invent dimensions, carvings, powers, or new clues. Do not claim the manuscript is still covering them.',
        'local': ['A wooden stake. Agatha has brought the means to act as well as the questions she wants answered.'],
        'detail': 'The stake belongs with Agatha’s preparations. It offers no explanation for the Count’s knowledge of Mina.',
    },
    'hammer': {
        'scene': 'convent', 'name': 'hammer', 'parent': 'bag', 'source': 'interview',
        'facts': 'Agatha brought a hammer and wooden stake beneath Jonathan’s manuscript. These remain her tools. Do not invent materials, dimensions, markings, powers, or new clues. Do not claim the manuscript is still covering them.',
        'local': ['Agatha’s hammer accompanies the wooden stake. Their presence makes her questions feel less like a routine interview.'],
        'detail': 'There is no hidden inscription or mechanism to discover. Agatha has brought a tool, and is keeping it close.',
    },
})

# Shared memory vocabulary: generated prose names the bedroom, so all normal
# combinations must work without a model, including in frozen/exported worlds.
MEMORY_VERBS = ('remember', 'recall', 'think about', 'think back to', 'reflect on')
MEMORY_TARGETS = ('castle', 'bedroom', 'castle bedroom', 'castle dracula',
                  "castle dracula's bedroom", 'castle dracula’s bedroom',
                  'bedroom in castle dracula', 'bedroom at castle dracula')

# Each command maps to a finite authored behaviour; aliases export verbatim.
COMMANDS = {
    'look': ['look', 'l', 'look around', 'where am i', 'describe the room'],
    'mina': ['tell agatha about mina', 'ask agatha about mina', 'mina', 'tell her about mina', 'what did dracula know about mina'],
    'remember': ['remember the castle', 'remember castle', 'go to castle', 'castle', 'remember', 'recall the castle', 'remember the bedroom'],
    'return': ['return', 'back', 'return to agatha', 'go back', 'convent', 'return to the convent'],
    'mirror': ['examine mirror', 'examine the mirror', 'look at mirror', 'look at the mirror', 'inspect mirror', 'x mirror'],
    'photograph': ['examine photograph', 'examine the photograph', 'look at the photograph', 'examine photo', 'x photograph'],
    'agatha': ['examine agatha', 'look at agatha', 'talk to agatha', 'speak to agatha', 'ask agatha'],
    'blood': ['ask agatha about blood', 'ask about blood', 'blood', 'tell agatha about blood', 'ask agatha about the count', 'ask agatha about dracula', 'how did he know', 'connect the clues'],
    'journal': ['journal', 'j', 'discoveries', 'what do i know', 'read journal', 'read my journal'],
    'inventory': ['inventory', 'i', 'what am i carrying'],
    'map': ['map', 'm', 'locations'],
    'help': ['help', 'h', '?', 'commands', 'what can i do'],
    'evidence': ['evidence', 'sources', 'show evidence'],
}
COMMANDS['remember'] += [f'{verb} {article}{target}'
                         for verb in MEMORY_VERBS for article in ('', 'the ')
                         for target in MEMORY_TARGETS]
for slug, slot in SLOTS.items():
    COMMANDS[f'examine:{slug}'] = [f'{verb} {article}{name}'
        for verb in ('examine', 'inspect', 'look at', 'x')
        for article in ('', 'the ')
        for name in (slug, slot['name'].lower())]
    COMMANDS[f'study:{slug}'] = [f'{verb} {article}{slug}{suffix}'
        for verb in ('study', 'inspect', 'examine') for article in ('', 'the ')
        for suffix in (' closely', ' more closely')] + [f'study {slug}', f'study the {slug}']


for verb in ('open', 'close', 'take', 'read'):
    targets = ['bag'] if verb in ('open', 'close') else ['manuscript', 'stake', 'hammer']
    for target in targets:
        COMMANDS[f'{verb}:{target}'] = [f'{verb} {article}{target}' for article in ('', 'the ')]
COMMANDS['return:manuscript'] = ['return manuscript', 'return the manuscript', 'give manuscript to agatha', 'give the manuscript to agatha', 'put manuscript in bag', 'put the manuscript in the bag']
COMMANDS['discuss:manuscript'] = ['ask agatha about manuscript', 'ask agatha about the manuscript', 'discuss manuscript']


def aliases():
    return {phrase: action for action, phrases in COMMANDS.items() for phrase in phrases}
