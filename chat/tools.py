"""
The fixed tool surface for Ask the Archive.

Design (docs/CHAT_INTERACTIVITY_ARCHITECTURE_BRIEF.md §4.3): the LLM never
writes queries — it chooses from these fixed, series-scoped tools, each a
parameterized ORM query (plus one in-memory BFS). Every tool takes a required
`series` slug; every returned entity carries a `url` into the catalog so
citation cards can be extracted deterministically downstream.

Tools return plain JSON-serializable dicts. Errors are returned as
{"error": ..., "candidates": [...]} rather than raised, so the model can
self-correct (disambiguation is a conversational move, not an error path).
"""

from collections import deque

from django.db.models import Count, F, Q, TextField
from django.db.models.functions import Cast
from django.utils.html import strip_tags
from django.utils.text import Truncator

from narrative.models import (
    ArcEventMembership,
    CharacterPage,
    ConflictArc,
    ConnectionScope,
    EpisodePage,
    EventPage,
    EventParticipation,
    Location,
    NarrativeConnection,
    OrganizationPage,
    SeriesIndexPage,
    Theme,
)

# Payload discipline: tool results feed straight into the model context.
MAX_TIMELINE_ITEMS = 40
MAX_SHARED_EVENTS = 25
MAX_CONNECTIONS_PER_DIRECTION = 25
MAX_SEARCH_RESULTS = 20
MAX_PATH_HOPS = 6
DESCRIPTION_CHARS = 700
PROFILE_CHARS = 1500


class ToolError(Exception):
    """Raised for malformed calls the executor turns into an error payload."""


# =============================================================================
# Shared resolution helpers
# =============================================================================

def _plain(html_text, limit=DESCRIPTION_CHARS):
    """Rich text field -> truncated plain text."""
    return Truncator(strip_tags(html_text or '')).chars(limit)


def get_series(slug):
    series = SeriesIndexPage.objects.live().filter(slug=slug).first()
    if series is None:
        available = list(
            SeriesIndexPage.objects.live().values_list('slug', flat=True))
        raise ToolError(
            f"Unknown series '{slug}'. The archive holds: {', '.join(available)}")
    return series


def series_events(series):
    return EventPage.objects.live().descendant_of(series)


def series_characters(series):
    return CharacterPage.objects.live().descendant_of(series)


def series_connections(series):
    return NarrativeConnection.objects.filter(
        from_event__in=series_events(series))


def _ordinal(episode):
    """Total ordering across a series: season*100 + episode."""
    if episode is None:
        return None
    return episode.season_number * 100 + episode.episode_number


def _episode_anchor(episode):
    if episode is None:
        return None
    return f"S{episode.season_number}E{episode.episode_number}"


def _event_ref(event):
    """Compact reference block used everywhere an event is mentioned."""
    return {
        'title': event.title,
        'uuid': event.fabula_uuid or str(event.pk),
        'episode': _episode_anchor(event.episode),
        'episode_title': event.episode.title if event.episode_id else None,
        'url': event.get_absolute_url(),
    }


def _character_ref(character):
    return {
        'name': character.canonical_name,
        'uuid': character.fabula_uuid or str(character.pk),
        'url': character.get_absolute_url(),
    }


def _resolve_one(queryset, identifier, name_field, json_alias_field=None,
                 kind='entity'):
    """Resolve a fuzzy identifier (uuid, exact name, substring) to one object.

    Returns (obj, None) on success, (None, error_payload) on failure —
    the error payload carries candidates so the model can disambiguate.
    """
    identifier = (identifier or '').strip()
    if not identifier:
        return None, {'error': f'Empty {kind} identifier.'}

    obj = queryset.filter(
        Q(fabula_uuid=identifier) | Q(global_id=identifier)).first()
    if obj:
        return obj, None

    obj = queryset.filter(**{f'{name_field}__iexact': identifier}).first()
    if obj:
        return obj, None

    matches = queryset.filter(
        **{f'{name_field}__icontains': identifier})
    if json_alias_field and not matches.exists():
        matches = queryset.annotate(
            _aliases=Cast(json_alias_field, TextField())
        ).filter(_aliases__icontains=identifier)

    matches = list(matches[:6])
    if len(matches) == 1:
        return matches[0], None
    if matches:
        return None, {
            'error': f"Ambiguous {kind} '{identifier}' — several candidates "
                     f"match. Retry with the exact name or uuid.",
            'candidates': [
                {'name': getattr(m, name_field),
                 'uuid': m.fabula_uuid or str(m.pk)}
                for m in matches
            ],
        }
    return None, {
        'error': f"No {kind} matching '{identifier}' in this series. "
                 f"Try resolve_entity to search by description or alias.",
    }


def resolve_character(series, identifier):
    return _resolve_one(
        series_characters(series).order_by('-appearance_count'), identifier,
        'canonical_name', json_alias_field='nicknames', kind='character')


def resolve_event(series, identifier):
    return _resolve_one(
        series_events(series).select_related('episode'), identifier,
        'title', kind='event')


def resolve_arc(series, identifier):
    return _resolve_one(
        ConflictArc.objects.filter(series=series), identifier,
        'title', kind='arc')


# =============================================================================
# Tool implementations
# =============================================================================

def resolve_entity(series, query, entity_type=None):
    """Fuzzy name search across every entity type in one series."""
    query = (query or '').strip()
    if not query:
        return {'error': 'Empty query.'}

    searches = {
        'character': (
            series_characters(series)
            .annotate(_nick=Cast('nicknames', TextField()))
            .filter(Q(canonical_name__icontains=query) |
                    Q(title_role__icontains=query) |
                    Q(_nick__icontains=query))
            .order_by('-appearance_count'),
            lambda c: {
                'type': 'character',
                'name': c.canonical_name,
                'role': c.title_role,
                'uuid': c.fabula_uuid or str(c.pk),
                'url': c.get_absolute_url(),
            }),
        'organization': (
            OrganizationPage.objects.live().descendant_of(series)
            .filter(canonical_name__icontains=query),
            lambda o: {
                'type': 'organization',
                'name': o.canonical_name,
                'uuid': o.fabula_uuid or str(o.pk),
                'url': o.get_absolute_url(),
            }),
        'location': (
            Location.objects.filter(series=series,
                                    canonical_name__icontains=query),
            lambda l: {
                'type': 'location',
                'name': l.canonical_name,
                'uuid': l.fabula_uuid or str(l.pk),
                'url': l.get_absolute_url(),
            }),
        'arc': (
            ConflictArc.objects.filter(series=series,
                                       title__icontains=query),
            lambda a: {
                'type': 'arc',
                'name': a.title,
                'arc_type': a.arc_type,
                'uuid': a.fabula_uuid or str(a.pk),
                'url': a.get_absolute_url(),
            }),
        'theme': (
            Theme.objects.filter(series=series, name__icontains=query),
            lambda t: {
                'type': 'theme',
                'name': t.name,
                'uuid': t.fabula_uuid or str(t.pk),
                'url': t.get_absolute_url(),
            }),
        'event': (
            series_events(series).select_related('episode')
            .filter(title__icontains=query),
            lambda e: {**_event_ref(e), 'type': 'event',
                       'name': e.title}),
    }

    if entity_type and entity_type in searches:
        searches = {entity_type: searches[entity_type]}

    results = []
    for _kind, (qs, shape) in searches.items():
        results.extend(shape(obj) for obj in qs[:5])

    if not results:
        return {
            'query': query,
            'matches': [],
            'note': 'No entity in this series matches. The archive may not '
                    'cover what the user described — say so rather than '
                    'guessing.',
        }
    return {'query': query, 'matches': results[:15]}


def get_character(series, character):
    char, err = resolve_character(series, character)
    if err:
        return err

    top_co = (
        EventParticipation.objects
        .filter(event__in=EventPage.objects.live().filter(
            participations__character=char))
        .exclude(character=char)
        .values('character__canonical_name', 'character__fabula_uuid')
        .annotate(shared_events=Count('id'))
        .order_by('-shared_events')[:6]
    )
    arcs = list(char.involved_arcs.all()[:8])
    themes = list(char.related_themes.all()[:8])

    return {
        'name': char.canonical_name,
        'uuid': char.fabula_uuid or str(char.pk),
        'url': char.get_absolute_url(),
        'title_role': char.title_role,
        'character_type': char.character_type,
        'importance_tier': char.importance_tier,
        'sphere_of_influence': char.sphere_of_influence,
        'description': _plain(char.description, PROFILE_CHARS),
        'traits': char.traits,
        'nicknames': char.nicknames,
        'affiliated_organization': (
            char.affiliated_organization.canonical_name
            if char.affiliated_organization_id else None),
        # Strongest tie first; the role is what stops the model saying the
        # Brigadier "is a Time Lord" when the graph only calls him an ally.
        'affiliations': [
            {'organization': a.organization.canonical_name,
             'relationship': a.relationship_type or None}
            for a in char.get_affiliations()],
        'event_appearances': char.appearance_count,
        'episode_count': char.episode_count,
        'season_appearances': char.season_appearances,
        'arc_summary': Truncator(char.arc_summary or '').chars(PROFILE_CHARS),
        'arcs': [{'title': a.title, 'uuid': a.fabula_uuid,
                  'url': a.get_absolute_url()} for a in arcs],
        'themes': [{'name': t.name, 'url': t.get_absolute_url()}
                   for t in themes],
        'most_frequent_co_participants': [
            {'name': c['character__canonical_name'],
             'shared_events': c['shared_events']}
            for c in top_co
        ],
    }


def character_timeline(series, character, season=None, limit=20):
    char, err = resolve_character(series, character)
    if err:
        return err

    limit = max(1, min(int(limit or 20), MAX_TIMELINE_ITEMS))
    parts = (
        EventParticipation.objects
        .filter(character=char, event__live=True,
                event__in=series_events(series))
        .select_related('event', 'event__episode')
        .order_by('event__episode__season_number',
                  'event__episode__episode_number',
                  'event__scene_sequence',
                  'event__sequence_in_scene')
    )
    if season:
        parts = parts.filter(event__episode__season_number=int(season))

    total = parts.count()
    items = []
    for p in parts[:limit]:
        items.append({
            'event': _event_ref(p.event),
            'what_happened': p.what_happened,
            'emotional_state': p.emotional_state,
            'goals': p.goals,
            'importance': p.importance,
        })
    return {
        'character': _character_ref(char),
        'season_filter': season,
        'total_participations': total,
        'showing': len(items),
        'timeline': items,
        'note': (f'Showing first {len(items)} of {total} — pass season= or '
                 f'a higher limit for more.') if total > len(items) else None,
    }


def relationship_history(series, character_a, character_b, limit=15):
    a, err = resolve_character(series, character_a)
    if err:
        return err
    b, err = resolve_character(series, character_b)
    if err:
        return err
    if a.pk == b.pk:
        return {'error': 'Both identifiers resolved to the same character '
                         f'({a.canonical_name}).'}

    limit = max(1, min(int(limit or 15), MAX_SHARED_EVENTS))
    shared = (
        series_events(series)
        .filter(participations__character=a)
        .filter(participations__character=b)
        .select_related('episode')
        .order_by('episode__season_number', 'episode__episode_number',
                  'scene_sequence', 'sequence_in_scene')
        .distinct()
    )
    total = shared.count()

    items = []
    for event in shared[:limit]:
        pa = event.participations.filter(character=a).first()
        pb = event.participations.filter(character=b).first()
        items.append({
            'event': _event_ref(event),
            a.canonical_name: {
                'what_happened': pa.what_happened if pa else '',
                'emotional_state': pa.emotional_state if pa else '',
            },
            b.canonical_name: {
                'what_happened': pb.what_happened if pb else '',
                'emotional_state': pb.emotional_state if pb else '',
            },
        })
    return {
        'characters': [_character_ref(a), _character_ref(b)],
        'total_shared_events': total,
        'showing': len(items),
        'shared_events': items,
    }


def get_episode(series, season, episode):
    ep = (
        EpisodePage.objects.live().descendant_of(series)
        .filter(season_number=int(season), episode_number=int(episode))
        .first()
    )
    if ep is None:
        available = list(
            EpisodePage.objects.live().descendant_of(series)
            .order_by('season_number', 'episode_number')
            .values_list('season_number', 'episode_number'))
        return {
            'error': f'No S{season}E{episode} in this series.',
            'available_episodes': [f'S{s}E{e}' for s, e in available],
        }

    credits = [
        {'writer': wc.writer.canonical_name, 'credit': wc.credit_type}
        for wc in ep.writing_credits.select_related('writer')
    ]
    events = list(ep.get_events().select_related('episode'))
    return {
        'title': ep.title,
        'episode': _episode_anchor(ep),
        'url': f'/explore/{series.slug}/episodes/{ep.fabula_uuid or ep.pk}/',
        'logline': ep.logline,
        'summary': _plain(ep.high_level_summary, PROFILE_CHARS),
        'dominant_tone': ep.dominant_tone,
        'writing_credits': credits or ep.written_by or None,
        'event_count': len(events),
        'events': [_event_ref(e) for e in events],
    }


def list_storylines(series):
    arcs = (
        ConflictArc.objects.filter(series=series)
        .annotate(event_count=Count('event_memberships', distinct=True))
        .order_by('-event_count')
    )
    themes = (
        Theme.objects.filter(series=series)
        .annotate(event_count=Count('event_memberships', distinct=True))
        .order_by('-event_count')
    )
    return {
        'series': series.slug,
        'conflict_arcs': [
            {'title': a.title, 'arc_type': a.arc_type,
             'event_count': a.event_count,
             'uuid': a.fabula_uuid, 'url': a.get_absolute_url()}
            for a in arcs
        ],
        'themes': [
            {'name': t.name, 'event_count': t.event_count,
             'uuid': t.fabula_uuid, 'url': t.get_absolute_url()}
            for t in themes
        ],
    }


def get_arc(series, arc):
    arc_obj, err = resolve_arc(series, arc)
    if err:
        return err

    memberships = (
        ArcEventMembership.objects
        .filter(arc=arc_obj, event__live=True)
        .select_related('event', 'event__episode')
        .order_by('episode_ordinal')
    )
    events = [
        {**_event_ref(m.event), 'arc_role': m.role}
        for m in memberships
    ]
    if not events:
        # Legacy fallback: series imported before the v2.4.0 membership table.
        events = [
            {**_event_ref(e), 'arc_role': None}
            for e in arc_obj.events.filter(live=True)
            .select_related('episode')
            .order_by('episode__season_number', 'episode__episode_number',
                      'scene_sequence')
        ]
    return {
        'title': arc_obj.title,
        'uuid': arc_obj.fabula_uuid,
        'url': arc_obj.get_absolute_url(),
        'arc_type': arc_obj.arc_type,
        'description': _plain(arc_obj.description, PROFILE_CHARS),
        'involved_characters': [
            _character_ref(c) for c in arc_obj.involved_characters.all()[:12]
        ],
        'event_count': len(events),
        'events': events,
    }


def connections_for_event(series, event):
    ev, err = resolve_event(series, event)
    if err:
        return err

    def shape(conn, other_event, direction):
        return {
            'direction': direction,
            'type': conn.connection_type,
            'strength': conn.strength,
            'scope': conn.scope,
            'layer': conn.layer,
            'description': conn.description,
            'cross_episode_reasoning': conn.cross_episode_reasoning or None,
            'other_event': _event_ref(other_event),
            'url': conn.get_absolute_url(),
        }

    outgoing = (ev.outgoing_connections
                .select_related('to_event', 'to_event__episode'))
    incoming = (ev.incoming_connections
                .select_related('from_event', 'from_event__episode'))
    out_total, in_total = outgoing.count(), incoming.count()

    return {
        'event': _event_ref(ev),
        'description': _plain(ev.description),
        'outgoing_total': out_total,
        'incoming_total': in_total,
        'outgoing': [
            shape(c, c.to_event, 'outgoing')
            for c in outgoing[:MAX_CONNECTIONS_PER_DIRECTION]],
        'incoming': [
            shape(c, c.from_event, 'incoming')
            for c in incoming[:MAX_CONNECTIONS_PER_DIRECTION]],
    }


def connection_path(series, from_event, to_event, max_hops=4):
    """Shortest path between two events through the connection layer.

    The connection graph for one series is a few thousand rows — small
    enough to BFS in memory, which buys the 'what links A to B' showcase
    without a graph engine (brief §6, open question 4).
    """
    src, err = resolve_event(series, from_event)
    if err:
        return err
    dst, err = resolve_event(series, to_event)
    if err:
        return err
    if src.pk == dst.pk:
        return {'error': 'Both identifiers resolved to the same event.'}

    max_hops = max(1, min(int(max_hops or 4), MAX_PATH_HOPS))

    edges = series_connections(series).values_list(
        'id', 'from_event_id', 'to_event_id')
    adjacency = {}
    for conn_id, f, t in edges:
        adjacency.setdefault(f, []).append((t, conn_id))
        adjacency.setdefault(t, []).append((f, conn_id))  # walk undirected

    # BFS from src to dst
    seen = {src.pk}
    queue = deque([(src.pk, [])])
    path_conn_ids = None
    while queue:
        node, path = queue.popleft()
        if len(path) >= max_hops:
            continue
        for neighbor, conn_id in adjacency.get(node, ()):
            if neighbor in seen:
                continue
            if neighbor == dst.pk:
                path_conn_ids = path + [conn_id]
                queue.clear()
                break
            seen.add(neighbor)
            queue.append((neighbor, path + [conn_id]))

    if path_conn_ids is None:
        return {
            'from_event': _event_ref(src),
            'to_event': _event_ref(dst),
            'path_found': False,
            'note': f'No path within {max_hops} hops through the connection '
                    f'layer. The events may sit in unconnected regions of '
                    f'the graph.',
        }

    conns = {
        c.pk: c for c in
        NarrativeConnection.objects.filter(pk__in=path_conn_ids)
        .select_related('from_event', 'from_event__episode',
                        'to_event', 'to_event__episode')
    }
    hops = []
    cursor = src.pk
    for conn_id in path_conn_ids:
        conn = conns[conn_id]
        forward = conn.from_event_id == cursor
        hops.append({
            'from': _event_ref(conn.from_event),
            'to': _event_ref(conn.to_event),
            'walked_against_direction': not forward,
            'type': conn.connection_type,
            'strength': conn.strength,
            'description': conn.description,
            'url': conn.get_absolute_url(),
        })
        cursor = conn.to_event_id if forward else conn.from_event_id

    return {
        'from_event': _event_ref(src),
        'to_event': _event_ref(dst),
        'path_found': True,
        'hop_count': len(hops),
        'path': hops,
    }


def search_events(series, query, season=None, limit=10):
    query = (query or '').strip()
    if len(query) < 2:
        return {'error': 'Query too short.'}

    limit = max(1, min(int(limit or 10), MAX_SEARCH_RESULTS))
    qs = (
        series_events(series)
        .select_related('episode')
        .annotate(_dialogue=Cast('key_dialogue', TextField()))
        .filter(Q(title__icontains=query) |
                Q(description__icontains=query) |
                Q(_dialogue__icontains=query))
        .order_by('episode__season_number', 'episode__episode_number',
                  'scene_sequence')
    )
    if season:
        qs = qs.filter(episode__season_number=int(season))

    total = qs.count()
    results = []
    for e in qs[:limit]:
        results.append({
            **_event_ref(e),
            'snippet': _plain(e.description, 300),
            'key_dialogue': e.key_dialogue[:3] if e.key_dialogue else [],
        })
    return {
        'query': query,
        'total_matches': total,
        'showing': len(results),
        'results': results,
    }


def graph_stats(series):
    events = series_events(series)
    conns = series_connections(series)

    by_type = dict(
        conns.values_list('connection_type')
        .annotate(n=Count('id')).order_by('-n'))
    cross_episode = conns.filter(scope=ConnectionScope.CROSS_EPISODE)
    # Season bridges: endpoints in different seasons.
    season_bridge_count = (
        cross_episode
        .filter(from_episode__isnull=False, to_episode__isnull=False)
        .exclude(from_episode__season_number=F('to_episode__season_number'))
        .count()
    )

    episodes = EpisodePage.objects.live().descendant_of(series)
    seasons = sorted(set(episodes.values_list('season_number', flat=True)))

    return {
        'series': series.title,
        'name': series.title,  # lets the rich-link walker emit a series card
        'slug': series.slug,
        'url': f'/explore/{series.slug}/',
        'seasons_covered': seasons,
        'episodes': episodes.count(),
        'events': events.count(),
        'characters': series_characters(series).count(),
        'organizations':
            OrganizationPage.objects.live().descendant_of(series).count(),
        'locations': Location.objects.filter(series=series).count(),
        'themes': Theme.objects.filter(series=series).count(),
        'conflict_arcs': ConflictArc.objects.filter(series=series).count(),
        'connections_total': conns.count(),
        'connections_by_type': by_type,
        'cross_episode_connections': cross_episode.count(),
        'season_bridging_connections': season_bridge_count,
    }
