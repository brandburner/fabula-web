"""Small physical world with source-seeded contents and explicit game rules."""
DEFAULTS = {'bag_open': True, 'manuscript_held': False, 'manuscript_read': False}
ACTIONS = ['open:bag', 'close:bag', 'take:manuscript', 'take:stake', 'take:hammer',
           'read:manuscript', 'read:stake', 'read:hammer', 'return:manuscript', 'discuss:manuscript']


def position(state):
    return {**DEFAULTS, **state.get('props', {})}


def accessible(state, slug):
    pos = position(state)
    return state['scene'] == 'convent' and (pos['bag_open'] or (slug == 'manuscript' and pos['manuscript_held']))


def handle(state, action, say):
    """Return True when handled; response text never decides an effect."""
    pos = position(state)
    state['props'] = pos
    if action == 'inventory':
        say('YOU ARE CARRYING\n' + ('Your manuscript · being consulted in the convent.' if pos['manuscript_held'] else 'Nothing. Agatha has the manuscript, stake and hammer.'))
    elif action == 'open:bag':
        say('The bag is already open.' if pos['bag_open'] else 'You open the bag. The stake and hammer remain inside.' + (' The manuscript is with you.' if pos['manuscript_held'] else ' Your manuscript is there too.'))
        pos['bag_open'] = True
    elif action == 'close:bag':
        say('You close the bag.' if pos['bag_open'] else 'The bag is already closed.')
        pos['bag_open'] = False
    elif action.startswith(('take:', 'read:')):
        verb, target = action.split(':')
        if not accessible(state, target):
            say('The ' + target + ' is inside Agatha’s closed bag. Open the bag first.', 'system')
            state['moves'] -= 1
        elif target != 'manuscript':
            say('Agatha keeps the ' + target + ' with her. You can examine it; it is not yours to take.' if verb == 'take' else 'There is no writing to read on the ' + target + '.', 'system')
            state['moves'] -= 1
        elif verb == 'take':
            say('You already have the manuscript.' if pos['manuscript_held'] else 'Agatha lets you take your manuscript to consult it. The stake and hammer stay in her bag.')
            pos['manuscript_held'] = True
        else:
            # Generated passage is replayed by engine.transition after checks.
            return False
    elif action == 'return:manuscript':
        if not pos['manuscript_held']:
            say('Agatha already has the manuscript.')
        elif not pos['bag_open']:
            say('Open the bag before putting the manuscript back.', 'system')
            state['moves'] -= 1
        else:
            pos['manuscript_held'] = False
            say('You return the manuscript to Agatha’s bag. What you have read stays with you.')
    elif action == 'discuss:manuscript':
        if not pos['manuscript_read']:
            say('Agatha wants you to read your account before defending it. You can consult the manuscript from her bag.')
        elif 'blood' not in state['discoveries']:
            say('You have read your account. Agatha wants you to put the page aside and return to what you remember: the castle bedroom, and the broken mirror.')
        else:
            say('You set the account beside your memory of the broken mirror. Agatha now has something specific to question: what the Count knew about Mina, and the blood drawn in that room. Ask her about blood when you have both pieces.')
    else:
        return False
    return True
