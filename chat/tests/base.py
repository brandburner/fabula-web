"""
Shared fixtures: a compact two-series narrative graph built through the
real Wagtail page tree, so series scoping (descendant_of) is tested
against the mechanism production uses.
"""

from django.test import TestCase
from wagtail.models import Page

from narrative.models import (
    ArcEventMembership,
    CharacterIndexPage,
    CharacterPage,
    ConflictArc,
    EpisodePage,
    EventIndexPage,
    EventPage,
    EventParticipation,
    NarrativeConnection,
    SeasonPage,
    SeriesIndexPage,
)


def build_series(slug, title, tag):
    """One series: 2 episodes, 2 characters, 3 events in a connection
    chain e1 -CAUSAL-> e2 -FORESHADOWING-> e3, one arc over e1/e3."""
    root = Page.objects.get(depth=1)
    series = SeriesIndexPage(title=title, slug=slug)
    root.add_child(instance=series)

    char_index = CharacterIndexPage(title=f'{title} Characters',
                                    slug=f'{slug}-characters')
    series.add_child(instance=char_index)
    event_index = EventIndexPage(title=f'{title} Events',
                                 slug=f'{slug}-events')
    series.add_child(instance=event_index)
    season = SeasonPage(title=f'{title} Season 1', slug=f'{slug}-s1',
                        season_number=1)
    series.add_child(instance=season)

    episodes = []
    for n in (1, 2):
        ep = EpisodePage(
            title=f'{title} Episode {n}', slug=f'{slug}-s1e{n}',
            episode_number=n, season_number=1,
            fabula_uuid=f'ep_{tag}{n}',
            logline=f'Episode {n} of {title}.')
        season.add_child(instance=ep)
        episodes.append(ep)

    characters = {}
    for name in (f'Alice {tag}', f'Bob {tag}'):
        char = CharacterPage(
            title=name, slug=f'{slug}-{name.split()[0].lower()}',
            canonical_name=name,
            description=f'<p>{name}, a person of interest.</p>',
            fabula_uuid=f'agent_{tag}_{name.split()[0].lower()}',
            nicknames=[name.split()[0][:2]],
            appearance_count=3)
        char_index.add_child(instance=char)
        characters[name.split()[0]] = char

    events = []
    for i, ep in ((1, episodes[0]), (2, episodes[0]), (3, episodes[1])):
        event = EventPage(
            title=f'{tag} Event {i}', slug=f'{slug}-event-{i}',
            episode=ep, scene_sequence=i,
            description=f'<p>The {tag} incident number {i}, involving '
                        f'a stolen ledger.</p>',
            key_dialogue=[f'Line {i} of {tag}'],
            fabula_uuid=f'event_{tag}{i}')
        event_index.add_child(instance=event)
        events.append(event)

    for event in events:
        for char in characters.values():
            EventParticipation.objects.create(
                event=event, character=char,
                what_happened=f'{char.canonical_name} acted in '
                              f'{event.title}.',
                emotional_state='wary', goals=['survive'],
                importance='primary')

    connections = [
        NarrativeConnection.objects.create(
            from_event=events[0], to_event=events[1],
            connection_type='CAUSAL', strength='strong',
            description=f'{tag}: the theft directly causes the reprisal.',
            layer='beat', scope='intra_episode',
            from_episode=episodes[0], to_episode=episodes[0]),
        NarrativeConnection.objects.create(
            from_event=events[1], to_event=events[2],
            connection_type='FORESHADOWING', strength='medium',
            description=f'{tag}: the reprisal hints at the reckoning.',
            layer='event', scope='cross_episode',
            from_episode=episodes[0], to_episode=episodes[1],
            cross_episode_reasoning='The pattern completes an arc.'),
    ]

    arc = ConflictArc.objects.create(
        fabula_uuid=f'arc_{tag}', title=f'The {tag} Feud',
        description='A quarrel over the ledger.', arc_type='INTERPERSONAL',
        series=series)
    arc.involved_characters.set(characters.values())
    ArcEventMembership.objects.create(event=events[0], arc=arc,
                                      role='START', episode_ordinal=101)
    ArcEventMembership.objects.create(event=events[2], arc=arc,
                                      role='CLIMAX', episode_ordinal=102)

    return {
        'series': series, 'episodes': episodes, 'characters': characters,
        'events': events, 'connections': connections, 'arc': arc,
    }


class NarrativeGraphTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alpha = build_series('alpha-show', 'Alpha Show', 'Alpha')
        cls.beta = build_series('beta-show', 'Beta Show', 'Beta')
