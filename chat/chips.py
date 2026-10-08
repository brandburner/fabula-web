"""
Deterministic suggestion chips — no LLM anywhere in here.

Two surfaces:
- welcome_chips(page_type, ...): per-page-type openers shown before the
  first message (served by /api/chat/suggestions/).
- followup_chips(collected, final_text): seeded from the turn's ACTUAL tool
  results (the response-aware generator the prior art identified as its own
  gap — built response-aware from the start, per brief §4.4).

Chip roles follow the ported model: Deepen / Explore / Pivot / Outward
(Outward = a link into the catalog, not a message).

Spoiler conservatism: chips only ever reference entities that already
surfaced in this conversation's tool results or the current page — chips
never volunteer late-canon material (the 'no premature alarm' transplant).
"""

MAX_CHIPS = 3


def welcome_chips(page_type, entity_name=None, series_slug=None):
    """Openers per page type. `send` chips post that message; `url` chips
    navigate."""
    name = entity_name or 'this'
    chips_by_type = {
        'series': [
            {'label': 'What does the archive hold for this series?',
             'send': 'What does the archive hold for this series?'},
            {'label': 'What are the major storylines?',
             'send': 'What are the major storylines in this series?'},
            {'label': 'Strongest season-bridging connections',
             'send': 'What are the strongest connections that bridge '
                     'seasons in this series?'},
        ],
        'character': [
            {'label': f'Walk {name} through the story',
             'send': f'Walk me through {name}\'s journey through the '
                     f'story, event by event.'},
            {'label': f'Who is {name} closest to?',
             'send': f'Who does {name} share the most scenes with, and '
                     f'what is between them?'},
            {'label': f'Which storylines pull {name} in?',
             'send': f'Which conflict arcs is {name} involved in?'},
        ],
        'event': [
            {'label': 'What led to this moment?',
             'send': f'What led to this event ({name})? What are its '
                     f'incoming connections?'},
            {'label': 'What does this set up?',
             'send': f'What does this event ({name}) cause or foreshadow '
                     f'later?'},
            {'label': 'Who was here, and what did they want?',
             'send': f'Who participated in this event ({name}), and what '
                     f'were their goals and emotional states?'},
        ],
        'episode': [
            {'label': 'What happens in this episode?',
             'send': f'Give me the key events of {name} in order.'},
            {'label': 'Which threads does it advance?',
             'send': f'Which ongoing storylines does {name} advance?'},
            {'label': 'Who wrote it?',
             'send': f'Who wrote {name}?'},
        ],
        'connection': [
            {'label': 'Explain this connection',
             'send': 'Explain this connection: why does the archive link '
                     'these two events, and how strong is the claim?'},
            {'label': 'More links between these episodes',
             'send': 'What other connections run between these two '
                     'episodes?'},
        ],
        'arc': [
            {'label': 'Trace this storyline',
             'send': f'Trace the {name} storyline from start to '
                     f'resolution.'},
            {'label': 'Who drives this conflict?',
             'send': f'Which characters drive the {name} arc?'},
        ],
        'theme': [
            {'label': 'Where does this theme surface?',
             'send': f'Which events exemplify the theme {name}?'},
        ],
    }
    chips = chips_by_type.get(page_type, [
        {'label': 'What can I ask the archive?',
         'send': 'What can I ask you? Show me what this archive holds.'},
        {'label': 'What are the major storylines?',
         'send': 'What are the major storylines in this series?'},
    ])
    return chips[:MAX_CHIPS]


def followup_chips(collected, final_text=''):
    """Response-aware follow-ups seeded from this turn's tool results."""
    chips = []
    text = final_text or ''

    def add(chip):
        if len(chips) < MAX_CHIPS and \
                chip['label'] not in {c['label'] for c in chips}:
            chips.append(chip)

    called = {c['tool'] for c in collected}

    for call in collected:
        tool, result = call['tool'], call['result']
        if not isinstance(result, dict) or 'error' in result:
            continue

        if tool == 'get_character' and 'name' in result:
            name = result['name']
            if 'character_timeline' not in called:
                add({'label': f"Walk {name}'s timeline",
                     'send': f"Walk me through {name}'s journey event by "
                             f"event."})
            co = result.get('most_frequent_co_participants') or []
            if co and 'relationship_history' not in called:
                other = co[0]['name']
                add({'label': f'{name} and {other}',
                     'send': f'How does the relationship between {name} '
                             f'and {other} evolve?'})
            add({'label': f'Open {name} in the catalog',
                 'url': result['url'], 'role': 'outward'})

        elif tool == 'character_timeline' and result.get('timeline'):
            name = result['character']['name']
            first = result['timeline'][0]['event']['title']
            last = result['timeline'][-1]['event']['title']
            if len(result['timeline']) > 1:
                add({'label': 'What connects the ends of that journey?',
                     'send': f'What chain of connections links '
                             f'"{first}" to "{last}"?'})
            add({'label': f'Open {name} in the catalog',
                 'url': result['character']['url'], 'role': 'outward'})

        elif tool == 'relationship_history' and result.get('shared_events'):
            a, b = (c['name'] for c in result['characters'])
            last_event = result['shared_events'][-1]['event']
            add({'label': 'Why does their last scene matter?',
                 'send': f'What connections surround the event '
                         f'"{last_event["title"]}"?'})
            add({'label': f'{a} alone',
                 'send': f"Walk me through {a}'s own journey."})

        elif tool == 'connections_for_event':
            outgoing = result.get('outgoing') or []
            if outgoing:
                strongest = next(
                    (c for c in outgoing if c['strength'] == 'strong'),
                    outgoing[0])
                other = strongest['other_event']['title']
                add({'label': f'Follow the chain onward',
                     'send': f'What does "{other}" go on to connect to?'})
            if result.get('event'):
                add({'label': 'Open this event in the catalog',
                     'url': result['event']['url'], 'role': 'outward'})

        elif tool == 'connection_path' and result.get('path_found'):
            add({'label': 'Open the first hop',
                 'url': result['path'][0]['url'], 'role': 'outward'})

        elif tool == 'get_arc' and 'title' in result:
            chars = result.get('involved_characters') or []
            if chars:
                add({'label': f"{chars[0]['name']} in this arc",
                     'send': f"How does {chars[0]['name']} move through "
                             f"the {result['title']} arc?"})
            add({'label': 'Open this storyline',
                 'url': result['url'], 'role': 'outward'})

        elif tool == 'list_storylines':
            arcs = result.get('conflict_arcs') or []
            if arcs:
                add({'label': f'Trace "{arcs[0]["title"]}"',
                     'send': f'Trace the {arcs[0]["title"]} storyline.'})

        elif tool == 'graph_stats':
            add({'label': 'What are the major storylines?',
                 'send': 'What are the major storylines in this series?'})
            add({'label': 'Strongest season bridges',
                 'send': 'What are the strongest connections that bridge '
                         'seasons?'})

        elif tool == 'search_events' and result.get('results'):
            top = result['results'][0]
            add({'label': f'Why "{top["title"][:40]}" matters',
                 'send': f'What connections surround the event '
                         f'"{top["title"]}"?'})

    # Generic safety net so the tail is never empty.
    if not chips and 'storylines' not in text.lower():
        add({'label': 'What are the major storylines?',
             'send': 'What are the major storylines in this series?'})
    return chips[:MAX_CHIPS]
