"""Project one published episode from the narrative graph into a world dict.

No hand authoring. Everything here is read from Wagtail/Postgres: events in
presentation order are the moments, their primary locations are the rooms,
location involvements supply what a room looks like at that moment, and
participations/object involvements supply who and what is present.

The result is JSON-serialisable and keyed by fabula_uuid throughout, so a
saved playthrough survives a reimport. The retrospective analytical prose in
EventPage.description is carried for the evidence view only; the narrator's
packets are built from the observational fields.
"""
import html
import re
from collections import Counter, defaultdict
from functools import lru_cache

from django.utils.html import strip_tags

from narrative.models import EpisodePage, EventPage, Location, SeriesIndexPage

REVISION = 'projection-v1'
MAX_ANCESTORS = 6


def clean(text):
    """Flatten rich text / markdown-ish strings to plain prose."""
    if not text:
        return ''
    text = html.unescape(strip_tags(str(text)))
    text = re.sub(r'\*\*|__', '', text)
    text = re.sub(r'(?<!\w)\*(?!\s)|(?<!\s)\*(?!\w)', '', text)
    return re.sub(r'\s+', ' ', text).strip()


def clean_title(title):
    return clean(title).strip('"“”\'‘’ ')


def listify(value):
    if not value:
        return []
    if isinstance(value, str):
        return [clean(value)]
    out = []
    for item in value:
        if isinstance(item, dict):
            speaker = item.get('speaker') or item.get('character') or ''
            line = item.get('line') or item.get('text') or item.get('quote') or ''
            out.append(clean(f'{speaker}: {line}' if speaker and line else (line or speaker)))
        else:
            out.append(clean(item))
    return [x for x in out if x and not PLACEHOLDER.match(x)]


PLACEHOLDER = re.compile(r'^\(?\s*(no|there is no|none)\b.*\bdialogue', re.I)


def stem(name):
    """Name without its parenthetical qualifier: 'York Place Audience Chamber'."""
    return clean(re.sub(r'\s*\([^)]*\)', '', name or '')).strip(' -–')


def find_episode(series_slug, season_number, episode_number):
    series = SeriesIndexPage.objects.filter(slug=series_slug, live=True).first()
    if series is None:
        return None
    return (EpisodePage.objects.live().filter(path__startswith=series.path, episode_number=episode_number,
                                              season_number=season_number).first())


def _location_row(location):
    return {'uuid': location.fabula_uuid, 'name': clean(location.canonical_name),
            'stem': stem(location.canonical_name), 'type': clean(location.location_type),
            'description': clean(location.description),
            'parent': location.parent_location.fabula_uuid if location.parent_location_id else None,
            'children': [], 'moments': [], 'mentions': [], 'room': False, 'in_episode': True}


def build_world(episode, slug=None):
    """Read one episode into a world dict. Only live pages are included."""
    series = episode.get_ancestors().type(SeriesIndexPage).first()
    events_qs = (EventPage.objects.live().filter(episode=episode)
                 .select_related('location', 'location__parent_location')
                 .prefetch_related('participations__character', 'object_involvements__object',
                                   'location_involvements__location__parent_location')
                 .order_by('scene_sequence', 'sequence_in_scene', 'path'))
    locations, characters, objects, events = {}, {}, {}, []

    def ensure_location(location):
        if location is None or location.fabula_uuid in locations:
            return
        locations[location.fabula_uuid] = _location_row(location)

    for ordinal, event in enumerate(events_qs):
        ensure_location(event.location)
        places = []
        for inv in event.location_involvements.all():
            ensure_location(inv.location)
            places.append({
                'uuid': inv.location.fabula_uuid, 'name': clean(inv.location.canonical_name),
                'primary': event.location_id == inv.location_id,
                'involvement': clean(inv.description_of_involvement),
                'atmosphere': clean(inv.observed_atmosphere), 'role': clean(inv.functional_role),
                'significance': clean(inv.symbolic_significance), 'access': clean(inv.access_restrictions),
                'details': listify(inv.key_environmental_details)})
        participants = []
        for part in event.participations.all():
            char = part.character
            if not char.live:
                continue
            characters.setdefault(char.fabula_uuid, {'uuid': char.fabula_uuid, 'name': clean(char.canonical_name),
                                                     'stem': stem(char.canonical_name), 'kind': clean(char.character_type)})
            participants.append({
                'uuid': char.fabula_uuid, 'name': clean(char.canonical_name), 'importance': part.importance or '',
                'what_happened': clean(part.what_happened), 'observed_status': clean(part.observed_status),
                'emotional_state': clean(part.emotional_state), 'goals': listify(part.goals),
                'beliefs': listify(part.beliefs)})
        involved = []
        for inv in event.object_involvements.all():
            obj = inv.object
            if not obj.live:
                continue
            objects.setdefault(obj.fabula_uuid, {'uuid': obj.fabula_uuid, 'name': clean(obj.canonical_name),
                                                 'stem': stem(obj.canonical_name)})
            involved.append({'uuid': obj.fabula_uuid, 'name': clean(obj.canonical_name),
                             'involvement': clean(inv.description_of_involvement),
                             'before': clean(inv.status_before_event), 'after': clean(inv.status_after_event)})
        row = {'uuid': event.fabula_uuid, 'ordinal': ordinal, 'title': clean_title(event.title),
               'scene': event.scene_sequence or 0, 'seq': event.sequence_in_scene or 0,
               'flashback': bool(event.is_flashback),
               'location': event.location.fabula_uuid if event.location_id else None,
               'description': clean(event.description), 'dialogue': listify(event.key_dialogue),
               'participants': participants, 'objects': involved, 'places': places,
               'url': event.url if hasattr(event, 'url') else ''}
        events.append(row)
        if row['location']:
            locations[row['location']]['room'] = True
            locations[row['location']]['moments'].append(ordinal)
        for place in places:
            if place['uuid'] != row['location']:
                locations[place['uuid']]['mentions'].append(ordinal)

    # Pull in ancestors so containment can be displayed, bounded.
    frontier = [loc['parent'] for loc in locations.values() if loc['parent'] and loc['parent'] not in locations]
    depth = 0
    while frontier and depth < MAX_ANCESTORS:
        rows = Location.objects.filter(fabula_uuid__in=frontier).select_related('parent_location')
        frontier = []
        for location in rows:
            if location.fabula_uuid in locations:
                continue
            entry = _location_row(location)
            entry['in_episode'] = False
            locations[location.fabula_uuid] = entry
            if entry['parent'] and entry['parent'] not in locations:
                frontier.append(entry['parent'])
        depth += 1
    for uuid, loc in locations.items():
        if loc['parent'] in locations:
            locations[loc['parent']]['children'].append(uuid)
        elif loc['parent']:
            loc['parent'] = None  # dangling parent beyond the ancestor bound
    for loc in locations.values():
        loc['children'].sort(key=lambda u: locations[u]['name'])

    world = {'revision': REVISION, 'slug': slug or episode.slug,
             'series': {'slug': series.slug if series else '', 'title': clean(series.title) if series else ''},
             'episode': {'uuid': episode.fabula_uuid, 'title': clean_title(episode.title),
                         'season': episode.season_number, 'number': episode.episode_number,
                         'logline': clean(episode.logline)},
             'events': events, 'locations': locations, 'characters': characters, 'objects': objects,
             'index': {e['uuid']: e['ordinal'] for e in events}}
    world['report'] = report(world)
    return world


def report(world):
    """Coverage and defect counts: what the graph supplies, where it is thin."""
    events, locations = world['events'], world['locations']
    rooms = [l for l in locations.values() if l['room']]
    features = [l for l in locations.values() if l['in_episode'] and not l['room']]
    per_room = Counter(e['location'] for e in events if e['location'])
    stems = defaultdict(set)
    for loc in locations.values():
        if loc['in_episode']:
            stems[loc['stem'].lower()].add(loc['uuid'])
    inversions = []
    for loc in locations.values():
        parent = locations.get(loc['parent']) if loc['parent'] else None
        # A parent whose name is contained in the child's name is suspect:
        # 'Tower of London - Court Gate' parented by 'Anne's Prison Chambers'.
        if parent and parent['room'] and loc['room'] and len(parent['moments']) < len(loc['moments']) \
                and parent['stem'].lower() not in loc['name'].lower():
            inversions.append((parent['name'], loc['name']))
    char_counts = Counter(p['uuid'] for e in events for p in e['participants'])
    slots = sum(2 + len(e['participants']) + len(e['objects']) for e in events)  # look + watch + each entity
    return {
        'events': len(events),
        'events_live_only': True,
        'events_with_primary_location': sum(1 for e in events if e['location']),
        'events_without_location_involvement': sum(1 for e in events if not e['places']),
        'events_whose_primary_is_not_in_involvements': sum(
            1 for e in events if e['location'] and e['location'] not in [p['uuid'] for p in e['places']]),
        'events_without_participants': sum(1 for e in events if not e['participants']),
        'events_without_objects': sum(1 for e in events if not e['objects']),
        'events_without_dialogue': sum(1 for e in events if not e['dialogue']),
        'flashbacks': sum(1 for e in events if e['flashback']),
        'rooms': len(rooms),
        'rooms_with_parent': sum(1 for l in rooms if l['parent']),
        'rooms_with_children': sum(1 for l in rooms if l['children']),
        'rooms_single_moment': sum(1 for l in rooms if len(l['moments']) == 1),
        'feature_locations': len(features),
        'ancestors_outside_episode': sum(1 for l in locations.values() if not l['in_episode']),
        'moments_per_room_top': [(locations[u]['name'], n) for u, n in per_room.most_common(8)],
        'duplicate_location_stems': sorted(
            [(s, len(u)) for s, u in stems.items() if len(u) > 1], key=lambda x: -x[1]),
        'hierarchy_inversions': inversions,
        'characters': len(world['characters']),
        'characters_single_appearance': sum(1 for n in char_counts.values() if n == 1),
        'objects': len(world['objects']),
        'passage_slots': slots,
    }


@lru_cache(maxsize=16)
def cached_world(episode_pk, slug):
    episode = EpisodePage.objects.live().filter(pk=episode_pk).first()
    return build_world(episode, slug) if episode else None


def load_world(config):
    """config: {'slug', 'series', 'season', 'episode'} from settings.ADVENTURE_WORLDS."""
    episode = find_episode(config['series'], config.get('season', 1), config['episode'])
    if episode is None:
        return None
    return cached_world(episode.pk, config['slug'])
