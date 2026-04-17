"""
SEO & Linked Data Template Tags for Fabula.

Generates JSON-LD structured data using schema.org vocabulary extended with
Fabula's own narrative ontology namespace (fabula:) for connection types,
participation edges, and thematic relationships.

The key insight: Fabula's data IS a knowledge graph. These tags don't just
add SEO markup — they publish the graph as linked data on the open web.

Vocabulary:
    schema.org:     TVSeries, TVSeason, TVEpisode, FictionalCharacter, Place, etc.
    fabula:         NarrativeConnection, EventParticipation, Theme, ConflictArc

Usage:
    {% load seo_tags %}
    {% series_jsonld page %}
    {% episode_jsonld page %}
    {% character_jsonld page %}
    {% event_jsonld page %}
    {% connection_jsonld connection %}
    {% breadcrumb_jsonld crumbs %}
"""

import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()

# Fabula's narrative ontology namespace
FABULA_NS = "https://fabula.productions/ontology/"

# Map connection types to their ontology URIs and schema.org nearest-match
CONNECTION_TYPE_MAP = {
    'CAUSAL': {
        'uri': f'{FABULA_NS}Causal',
        'label': 'Causal',
        'description': 'Event A directly causes or enables Event B',
    },
    'FORESHADOWING': {
        'uri': f'{FABULA_NS}Foreshadowing',
        'label': 'Foreshadowing',
        'description': 'Event A hints at or prefigures Event B',
    },
    'THEMATIC_PARALLEL': {
        'uri': f'{FABULA_NS}ThematicParallel',
        'label': 'Thematic Parallel',
        'description': 'Events A and B explore the same theme from different angles',
    },
    'CHARACTER_CONTINUITY': {
        'uri': f'{FABULA_NS}CharacterContinuity',
        'label': 'Character Continuity',
        'description': 'A character\'s state evolves from Event A to Event B',
    },
    'ESCALATION': {
        'uri': f'{FABULA_NS}Escalation',
        'label': 'Escalation',
        'description': 'Event B raises the stakes established in Event A',
    },
    'CALLBACK': {
        'uri': f'{FABULA_NS}Callback',
        'label': 'Callback',
        'description': 'Event B explicitly references or echoes Event A',
    },
    'EMOTIONAL_ECHO': {
        'uri': f'{FABULA_NS}EmotionalEcho',
        'label': 'Emotional Echo',
        'description': 'Event B evokes the same emotional register as Event A',
    },
    'SYMBOLIC_PARALLEL': {
        'uri': f'{FABULA_NS}SymbolicParallel',
        'label': 'Symbolic Parallel',
        'description': 'Events A and B share symbolic meaning or imagery',
    },
    'TEMPORAL': {
        'uri': f'{FABULA_NS}Temporal',
        'label': 'Temporal',
        'description': 'Time-structure connection between events',
    },
    'NARRATIVELY_FOLLOWS': {
        'uri': f'{FABULA_NS}NarrativelyFollows',
        'label': 'Narratively Follows',
        'description': 'Sequential non-causal narrative progression from Event A to Event B',
    },
}


def _strip_html(text):
    """Strip HTML tags and collapse whitespace."""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _truncate(text, max_len=300):
    """Truncate text to max_len characters at word boundary."""
    text = _strip_html(text)
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(' ', 1)[0] + '...'


def _url(request, path):
    """Build absolute URL from request and path."""
    return f"{request.scheme}://{request.get_host}{path}"


def _fabula_context():
    """
    Return the JSON-LD @context that merges schema.org with Fabula's ontology.
    This allows us to use both schema: and fabula: prefixed types.
    """
    return {
        "@vocab": "https://schema.org/",
        "fabula": FABULA_NS,
    }


def _jsonld(data):
    """Render a JSON-LD script tag."""
    return mark_safe(
        f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
    )


# =============================================================================
# SERIES — TVSeries with nested TVSeason/TVEpisode + Themes
# =============================================================================

@register.simple_tag(takes_context=True)
def series_jsonld(context, page):
    """
    Emit a @graph of the full series structure: the TVSeries, its seasons,
    and associated themes as DefinedTerms.
    """
    request = context['request']
    seasons = context.get('seasons', [])

    graph = []

    # The series itself
    series_node = {
        "@type": "TVSeries",
        "@id": _url(request, page.url),
        "name": _strip_html(page.title),
        "url": _url(request, page.url),
        "description": _truncate(page.description) if page.description else (
            f"Narrative graph analysis of {_strip_html(page.title)} "
            f"— characters, events, themes, and the connections between them."
        ),
        "publisher": {"@type": "Organization", "name": "Fabula"},
    }

    if seasons:
        series_node["numberOfSeasons"] = len(seasons)
        series_node["containsSeason"] = [
            {"@id": _url(request, s.url)} for s in seasons
        ]

    graph.append(series_node)

    # Each season as a linked node
    for season in seasons:
        season_node = {
            "@type": "TVSeason",
            "@id": _url(request, season.url),
            "name": f"Season {season.season_number}",
            "seasonNumber": season.season_number,
            "url": _url(request, season.url),
            "partOfSeries": {"@id": _url(request, page.url)},
        }
        episode_count = season.get_children().count()
        if episode_count:
            season_node["numberOfEpisodes"] = episode_count
        graph.append(season_node)

    # Themes as DefinedTerms linked to the series
    if hasattr(page, 'themes'):
        for theme in page.themes.all()[:15]:
            graph.append({
                "@type": "DefinedTerm",
                "@id": _url(request, theme.get_absolute_url()),
                "name": theme.name,
                "description": _truncate(theme.description, 200),
                "url": _url(request, theme.get_absolute_url()),
                "inDefinedTermSet": {
                    "@type": "DefinedTermSet",
                    "name": f"Themes of {_strip_html(page.title)}",
                },
            })

    return _jsonld({"@context": _fabula_context(), "@graph": graph})


# =============================================================================
# EPISODE — TVEpisode @graph with characters, locations, writing credits
# =============================================================================

@register.simple_tag(takes_context=True)
def episode_jsonld(context, page):
    """
    Emit a @graph: the episode, its characters as FictionalCharacters,
    locations as Places, and writing credits.
    """
    request = context['request']
    graph = []

    # The episode
    ep_id = _url(request, page.url)
    episode_node = {
        "@type": "TVEpisode",
        "@id": ep_id,
        "name": _strip_html(page.title),
        "url": ep_id,
        "episodeNumber": page.episode_number,
    }

    if hasattr(page, 'logline') and page.logline:
        episode_node["description"] = _truncate(page.logline)
    elif hasattr(page, 'high_level_summary') and page.high_level_summary:
        episode_node["description"] = _truncate(page.high_level_summary)

    if hasattr(page, 'season_number'):
        episode_node["partOfSeason"] = {
            "@type": "TVSeason",
            "seasonNumber": page.season_number,
        }

    # Walk to series
    for ancestor in page.get_ancestors().specific():
        if hasattr(ancestor, 'season_number'):
            continue
        if hasattr(ancestor, 'fabula_uuid') and hasattr(ancestor, 'description'):
            episode_node["partOfSeries"] = {
                "@type": "TVSeries",
                "@id": _url(request, ancestor.url),
                "name": _strip_html(ancestor.title),
            }
            break

    # Characters — use FictionalCharacter, link by @id
    profiles = list(page.character_profiles.select_related('character')[:20])
    if profiles:
        episode_node["character"] = []
        for p in profiles:
            if not p.character:
                continue
            char_id = _url(request, p.character.url)
            episode_node["character"].append({"@id": char_id})
            char_node = {
                "@type": "FictionalCharacter",
                "@id": char_id,
                "name": _strip_html(p.character.canonical_name),
                "url": char_id,
            }
            if p.character.title_role:
                char_node["jobTitle"] = p.character.title_role
            graph.append(char_node)

    # Locations from events in this episode
    locations_seen = set()
    for event in page.events.select_related('location').all()[:50]:
        if event.location and event.location.pk not in locations_seen:
            locations_seen.add(event.location.pk)
            loc_id = _url(request, event.location.get_absolute_url())
            graph.append({
                "@type": "Place",
                "@id": loc_id,
                "name": _strip_html(event.location.canonical_name),
                "url": loc_id,
            })
            episode_node.setdefault("contentLocation", []).append(
                {"@id": loc_id}
            )

    # Writing credits (CREDITED_ON with WGA-style metadata)
    credits = list(page.writing_credits.select_related('writer').all())
    if credits:
        episode_node["author"] = []
        for c in credits:
            if not c.writer:
                continue
            credit_node = {
                "@type": "Person",
                "name": c.writer.canonical_name,
            }
            if c.credit_type:
                credit_node["fabula:creditType"] = c.credit_type
            episode_node["author"].append(credit_node)

    # Event count as a stat
    event_count = page.events.count()
    if event_count:
        episode_node["fabula:eventCount"] = event_count

    graph.insert(0, episode_node)
    return _jsonld({"@context": _fabula_context(), "@graph": graph})


# =============================================================================
# CHARACTER — FictionalCharacter @graph with affiliations and journey stats
# =============================================================================

@register.simple_tag(takes_context=True)
def character_jsonld(context, page):
    """
    Emit a @graph: the character as FictionalCharacter, their organization
    affiliation, and narrative statistics.
    """
    request = context['request']
    graph = []

    char_id = _url(request, page.url)
    char_node = {
        "@type": "FictionalCharacter",
        "@id": char_id,
        "name": _strip_html(page.canonical_name),
        "url": char_id,
    }

    if page.description:
        char_node["description"] = _truncate(page.description)
    if page.title_role:
        char_node["jobTitle"] = page.title_role
    if hasattr(page, 'nicknames') and page.nicknames:
        char_node["alternateName"] = page.nicknames
    if hasattr(page, 'traits') and page.traits:
        char_node["fabula:traits"] = page.traits

    # Importance tier as narrative weight
    if hasattr(page, 'importance_tier') and page.importance_tier:
        char_node["fabula:importanceTier"] = page.importance_tier

    # Appearance count
    if hasattr(page, 'appearance_count'):
        char_node["fabula:appearances"] = page.appearance_count

    # Affiliation as linked Organization
    if page.affiliated_organization:
        org_id = _url(request, page.affiliated_organization.url)
        char_node["affiliation"] = {"@id": org_id}
        graph.append({
            "@type": "Organization",
            "@id": org_id,
            "name": _strip_html(page.affiliated_organization.canonical_name),
            "url": org_id,
        })

    graph.insert(0, char_node)
    return _jsonld({"@context": _fabula_context(), "@graph": graph})


# =============================================================================
# EVENT — the narrative hub: @graph with participations, connections, location
# =============================================================================

@register.simple_tag(takes_context=True)
def event_jsonld(context, page):
    """
    Emit the richest @graph in the system: the event as a creative work,
    its character participations with rich edge data (emotional state, goals),
    its narrative connections with typed edges, location, and themes.

    This is where Fabula's ontology really shines — the edges carry meaning.
    """
    request = context['request']
    graph = []

    event_id = _url(request, page.url)
    event_node = {
        "@type": ["CreativeWork", "fabula:NarrativeEvent"],
        "@id": event_id,
        "name": _strip_html(page.title),
        "url": event_id,
        "isPartOf": {
            "@type": "TVEpisode",
            "name": _strip_html(page.episode.title) if page.episode else "Unknown",
            "url": _url(request, page.episode.url) if page.episode else None,
        },
        "publisher": {"@type": "Organization", "name": "Fabula"},
    }

    if page.description:
        event_node["description"] = _truncate(page.description)
    if page.is_flashback:
        event_node["fabula:isFlashback"] = True
    if page.scene_sequence:
        event_node["fabula:sceneNumber"] = page.scene_sequence
    if hasattr(page, 'key_dialogue') and page.key_dialogue:
        event_node["fabula:keyDialogue"] = page.key_dialogue[:5]

    # Location as Place (with hierarchy via PART_OF)
    if page.location:
        loc_id = _url(request, page.location.get_absolute_url())
        event_node["contentLocation"] = {"@id": loc_id}
        loc_node = {
            "@type": "Place",
            "@id": loc_id,
            "name": _strip_html(page.location.canonical_name),
            "url": loc_id,
        }
        if hasattr(page.location, 'parent_location') and page.location.parent_location:
            parent = page.location.parent_location
            parent_id = _url(request, parent.get_absolute_url())
            loc_node["containedInPlace"] = {
                "@type": "Place",
                "@id": parent_id,
                "name": _strip_html(parent.canonical_name),
            }
        graph.append(loc_node)

    # Character participations — the rich edges
    participations = list(
        page.participations.select_related('character')[:15]
    )
    if participations:
        event_node["fabula:participations"] = []
        for p in participations:
            if not p.character:
                continue
            char_id = _url(request, p.character.url)
            participation = {
                "@type": "fabula:EventParticipation",
                "fabula:character": {"@id": char_id},
            }
            if p.emotional_state:
                participation["fabula:emotionalState"] = _truncate(
                    p.emotional_state, 200
                )
            if p.what_happened:
                participation["fabula:action"] = _truncate(
                    p.what_happened, 200
                )
            if p.goals:
                participation["fabula:goals"] = (
                    p.goals if isinstance(p.goals, list) else []
                )
            if p.observed_status:
                participation["fabula:observedStatus"] = _truncate(
                    p.observed_status, 200
                )
            if hasattr(p, 'beliefs') and p.beliefs:
                participation["fabula:beliefs"] = (
                    p.beliefs if isinstance(p.beliefs, list) else []
                )
            if hasattr(p, 'observed_traits') and p.observed_traits:
                participation["fabula:observedTraits"] = (
                    p.observed_traits if isinstance(p.observed_traits, list)
                    else []
                )
            if hasattr(p, 'importance') and p.importance:
                participation["fabula:importance"] = p.importance
            event_node["fabula:participations"].append(participation)

            # Also emit the character as a node
            graph.append({
                "@type": "FictionalCharacter",
                "@id": char_id,
                "name": _strip_html(p.character.canonical_name),
                "url": char_id,
            })

    # Narrative connections — typed, directed edges with assertions
    outgoing = list(
        page.outgoing_connections.select_related('to_event')[:10]
    )
    incoming = list(
        page.incoming_connections.select_related('from_event')[:10]
    )

    connections = []
    for conn in outgoing:
        if not conn.to_event:
            continue
        conn_type = CONNECTION_TYPE_MAP.get(conn.connection_type, {})
        connections.append({
            "@type": "fabula:NarrativeConnection",
            "fabula:connectionType": conn_type.get('uri', conn.connection_type),
            "fabula:connectionLabel": conn_type.get('label', conn.connection_type),
            "fabula:fromEvent": {"@id": event_id},
            "fabula:toEvent": {
                "@id": _url(request, conn.to_event.url),
                "name": _strip_html(conn.to_event.title),
            },
            "fabula:strength": conn.strength,
            "description": _truncate(conn.description, 200) if conn.description else None,
            "url": _url(request, conn.get_absolute_url()),
        })

    for conn in incoming:
        if not conn.from_event:
            continue
        conn_type = CONNECTION_TYPE_MAP.get(conn.connection_type, {})
        connections.append({
            "@type": "fabula:NarrativeConnection",
            "fabula:connectionType": conn_type.get('uri', conn.connection_type),
            "fabula:connectionLabel": conn_type.get('label', conn.connection_type),
            "fabula:fromEvent": {
                "@id": _url(request, conn.from_event.url),
                "name": _strip_html(conn.from_event.title),
            },
            "fabula:toEvent": {"@id": event_id},
            "fabula:strength": conn.strength,
            "description": _truncate(conn.description, 200) if conn.description else None,
            "url": _url(request, conn.get_absolute_url()),
        })

    if connections:
        event_node["fabula:connections"] = connections

    # Themes
    if hasattr(page, 'themes'):
        themes = list(page.themes.all()[:10])
        if themes:
            event_node["about"] = [
                {
                    "@type": "DefinedTerm",
                    "@id": _url(request, t.get_absolute_url()),
                    "name": t.name,
                }
                for t in themes
            ]

    # Conflict arcs (PART_OF_ARC)
    if hasattr(page, 'arcs'):
        arcs = list(page.arcs.all()[:5])
        if arcs:
            event_node["fabula:conflictArcs"] = [
                {
                    "@type": "fabula:ConflictArc",
                    "@id": _url(request, arc.get_absolute_url()),
                    "name": arc.title,
                    "description": _truncate(arc.description, 150),
                    "fabula:arcType": arc.arc_type,
                }
                for arc in arcs
            ]

    # Object involvements (INVOLVED_WITH)
    if hasattr(page, 'object_involvements'):
        obj_involvements = list(
            page.object_involvements.select_related('object')[:10]
        )
        if obj_involvements:
            event_node["fabula:objectInvolvements"] = []
            for oi in obj_involvements:
                if not oi.object:
                    continue
                obj_id = _url(request, oi.object.get_absolute_url())
                involvement = {
                    "@type": "fabula:ObjectInvolvement",
                    "fabula:object": {"@id": obj_id},
                }
                if oi.description_of_involvement:
                    involvement["description"] = _truncate(
                        oi.description_of_involvement, 150
                    )
                event_node["fabula:objectInvolvements"].append(involvement)
                graph.append({
                    "@type": "Thing",
                    "@id": obj_id,
                    "name": _strip_html(oi.object.canonical_name),
                    "url": obj_id,
                })

    # Organization involvements
    if hasattr(page, 'organization_involvements'):
        org_involvements = list(
            page.organization_involvements.select_related('organization')[:10]
        )
        if org_involvements:
            event_node["fabula:organizationInvolvements"] = []
            for oi in org_involvements:
                if not oi.organization:
                    continue
                org_id = _url(request, oi.organization.get_absolute_url())
                involvement = {
                    "@type": "fabula:OrganizationInvolvement",
                    "fabula:organization": {"@id": org_id},
                }
                if oi.description_of_involvement:
                    involvement["description"] = _truncate(
                        oi.description_of_involvement, 150
                    )
                event_node["fabula:organizationInvolvements"].append(
                    involvement
                )
                graph.append({
                    "@type": "Organization",
                    "@id": org_id,
                    "name": _strip_html(oi.organization.canonical_name),
                    "url": org_id,
                })

    graph.insert(0, event_node)

    # Strip None values for cleanliness
    def _clean(obj):
        if isinstance(obj, dict):
            return {k: _clean(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [_clean(i) for i in obj]
        return obj

    return _jsonld(_clean({"@context": _fabula_context(), "@graph": graph}))


# =============================================================================
# CONNECTION — the first-class edge as linked data
# =============================================================================

@register.simple_tag(takes_context=True)
def connection_jsonld(context, connection):
    """
    Emit a NarrativeConnection as a linked data resource.
    This is Fabula's unique contribution: edges-as-content.
    The connection carries an analytical claim about narrative structure.
    """
    request = context['request']

    conn_type = CONNECTION_TYPE_MAP.get(connection.connection_type, {})

    graph = []

    # The connection itself
    conn_node = {
        "@type": ["fabula:NarrativeConnection", "Claim"],
        "@id": _url(request, connection.get_absolute_url()),
        "name": (
            f"{conn_type.get('label', connection.connection_type)}: "
            f"{_strip_html(connection.from_event.title)} → "
            f"{_strip_html(connection.to_event.title)}"
        ),
        "url": _url(request, connection.get_absolute_url()),
        "fabula:connectionType": conn_type.get('uri', connection.connection_type),
        "fabula:connectionLabel": conn_type.get('label', connection.connection_type),
        "fabula:strength": connection.strength,
        "fabula:fromEvent": {
            "@id": _url(request, connection.from_event.url),
        },
        "fabula:toEvent": {
            "@id": _url(request, connection.to_event.url),
        },
    }

    if connection.description:
        conn_node["description"] = _truncate(connection.description)

    if conn_type.get('description'):
        conn_node["fabula:typeDescription"] = conn_type['description']

    graph.append(conn_node)

    # The two events as linked nodes
    graph.append({
        "@type": ["CreativeWork", "fabula:NarrativeEvent"],
        "@id": _url(request, connection.from_event.url),
        "name": _strip_html(connection.from_event.title),
        "url": _url(request, connection.from_event.url),
    })
    graph.append({
        "@type": ["CreativeWork", "fabula:NarrativeEvent"],
        "@id": _url(request, connection.to_event.url),
        "name": _strip_html(connection.to_event.title),
        "url": _url(request, connection.to_event.url),
    })

    return _jsonld({"@context": _fabula_context(), "@graph": graph})


# =============================================================================
# BREADCRUMBS
# =============================================================================

@register.simple_tag(takes_context=True)
def breadcrumb_jsonld(context, crumbs):
    """
    Generate BreadcrumbList JSON-LD.

    Args:
        crumbs: list of (name, url) tuples.
    """
    request = context['request']

    items = []
    for i, (name, url) in enumerate(crumbs, start=1):
        item = {
            "@type": "ListItem",
            "position": i,
            "name": _strip_html(name),
        }
        if url:
            item["item"] = _url(request, url)
        items.append(item)

    return _jsonld({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    })
