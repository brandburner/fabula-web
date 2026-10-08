"""A small published episode with nested locations, feature-only places,
a flashback, an identity collision ("cloak") and a coverage hole, built
through the real Wagtail page tree so projection reads what production reads."""
from wagtail.models import Page

from narrative.models import (CharacterIndexPage, CharacterPage, EpisodePage, EventIndexPage, EventPage,
                              EventParticipation, Location, LocationInvolvement, ObjectIndexPage, ObjectInvolvement,
                              ObjectPage, SeasonPage, SeriesIndexPage)

SLUG = 'test-show'
WORLD = {'slug': 'test-show-e1', 'series': SLUG, 'season': 1, 'episode': 1}


def build():
    root = Page.objects.get(depth=1)
    series = SeriesIndexPage(title='Test Show', slug=SLUG)
    root.add_child(instance=series)
    chars = CharacterIndexPage(title='Characters', slug='test-characters')
    series.add_child(instance=chars)
    events_idx = EventIndexPage(title='Events', slug='test-events')
    series.add_child(instance=events_idx)
    objects_idx = ObjectIndexPage(title='Objects', slug='test-objects')
    series.add_child(instance=objects_idx)
    season = SeasonPage(title='Season 1', slug='test-s1', season_number=1)
    series.add_child(instance=season)
    episode = EpisodePage(title='**"The Ledger"**', slug='test-s1e1', episode_number=1, season_number=1,
                          fabula_uuid='ep_test1', logline='A ledger goes missing.')
    season.add_child(instance=episode)
    episode2 = EpisodePage(title='Unpublished', slug='test-s1e2', episode_number=2, season_number=1,
                           fabula_uuid='ep_test2', live=False)
    season.add_child(instance=episode2)

    def loc(uuid, name, kind, parent=None, description=''):
        return Location.objects.create(fabula_uuid=uuid, canonical_name=name, location_type=kind,
                                       parent_location=parent, description=description)
    manor = loc('loc_manor', 'Ashby Manor', 'Country House', description='A manor house.')
    hall = loc('loc_hall', 'Great Hall (Ashby Manor)', 'Hall', manor, 'The long hall of the manor.')
    study = loc('loc_study', "Ward's Study (Ashby Manor)", 'Study', hall)
    inn = loc('loc_inn', 'The Crown Inn', 'Inn')
    yard = loc('loc_yard', 'Stable Yard (The Crown Inn)', 'Yard', inn)

    def char(uuid, name):
        page = CharacterPage(title=name, slug=uuid, canonical_name=name, fabula_uuid=uuid,
                             description=f'<p>{name}.</p>')
        chars.add_child(instance=page)
        return page
    alice = char('agent_alice', 'Alice Ward')
    bob = char('agent_bob', 'Bob Ward')
    keeper = char('agent_keeper', 'The Innkeeper (Crown Inn)')
    cloaked = char('agent_cloaked', 'Man in a Dark Cloak')

    def obj(uuid, name):
        page = ObjectPage(title=name, slug=uuid, canonical_name=name, fabula_uuid=uuid, description=f'<p>{name}.</p>')
        objects_idx.add_child(instance=page)
        return page
    ledger = obj('object_ledger', "Alice's Ledger")
    cloak = obj('object_cloak', 'Dark Cloak')

    spec = [
        # uuid, title, scene, location, flashback, participants, objects, involvements, dialogue
        ('evt_1', '**"Arrival at the Hall"**', 1, hall, False, [alice, bob], [ledger], [hall, study], ['Alice: Where is it?']),
        ('evt_2', 'The Study, Remembered', 2, study, True, [alice], [ledger], [study], []),
        ('evt_3', 'A Drink at the Crown', 3, inn, False, [bob, keeper], [], [inn, yard], ['(No direct dialogue occurs.)']),
        ('evt_4', 'A Stranger in the Hall', 4, hall, False, [alice, bob, cloaked], [ledger, cloak], [hall], ['Bob: Who are you?']),
        ('evt_5', 'Closing Time', 5, inn, False, [bob], [], [], []),
    ]
    events = []
    for uuid, title, scene, location, flashback, people, things, places, dialogue in spec:
        event = EventPage(title=title, slug=uuid, fabula_uuid=uuid, episode=episode, scene_sequence=scene,
                          sequence_in_scene=1, location=location, is_flashback=flashback,
                          description=f'<p>Analysis of <b>{title}</b>, foreshadowing the end.</p>', key_dialogue=dialogue)
        events_idx.add_child(instance=event)
        for person in people:
            EventParticipation.objects.create(event=event, character=person, importance='primary',
                                              what_happened=f'{person.canonical_name} does something in {title}.',
                                              observed_status=f'{person.canonical_name} stands by the door.',
                                              emotional_state='wary', goals=['find the ledger'], beliefs=['Bob took it'])
        for thing in things:
            ObjectInvolvement.objects.create(event=event, object=thing, description_of_involvement=f'{thing.canonical_name} lies on the table.',
                                             status_before_event='closed', status_after_event='open')
        for place in places:
            LocationInvolvement.objects.create(event=event, location=place, description_of_involvement='It is used here.',
                                               observed_atmosphere=f'Quiet in {place.canonical_name}.',
                                               access_restrictions='Family only.' if place is study else '',
                                               key_environmental_details=['a cold hearth', 'rain on the glass'])
        events.append(event)
    # An unpublished event must not appear.
    hidden = EventPage(title='Hidden', slug='evt_hidden', fabula_uuid='evt_hidden', episode=episode, scene_sequence=6,
                       sequence_in_scene=1, location=hall, live=False, description='<p>Hidden.</p>')
    events_idx.add_child(instance=hidden)
    hidden.unpublish()
    return {'series': series, 'episode': episode, 'events': events, 'locations': [manor, hall, study, inn, yard],
            'characters': {'alice': alice, 'bob': bob, 'keeper': keeper, 'cloaked': cloaked},
            'objects': {'ledger': ledger, 'cloak': cloak}}
