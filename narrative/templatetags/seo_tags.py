"""
SEO Template Tags for Fabula.

Generates JSON-LD structured data for search engines.
Uses schema.org vocabulary: TVSeries, TVSeason, TVEpisode, Person, etc.

Usage:
    {% load seo_tags %}
    {% series_jsonld page %}
    {% episode_jsonld page %}
    {% character_jsonld page %}
    {% breadcrumb_jsonld crumbs %}
"""

import json
import re

from django import template
from django.utils.safestring import mark_safe

register = template.Library()


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


def _build_url(request, path):
    """Build absolute URL from request and path."""
    return f"{request.scheme}://{request.get_host}{path}"


@register.simple_tag(takes_context=True)
def series_jsonld(context, page):
    """
    Generate TVSeries JSON-LD for a SeriesIndexPage.
    Includes seasons, episode count, and description.
    """
    request = context['request']
    seasons = context.get('seasons', [])

    data = {
        "@context": "https://schema.org",
        "@type": "TVSeries",
        "name": _strip_html(page.title),
        "url": _build_url(request, page.url),
        "description": _truncate(page.description) if page.description else f"Narrative analysis of {_strip_html(page.title)} — characters, events, themes, and connections.",
        "publisher": {
            "@type": "Organization",
            "name": "Fabula",
            "url": _build_url(request, '/'),
        },
    }

    if seasons:
        data["numberOfSeasons"] = len(seasons)
        data["containsSeason"] = []
        for season in seasons:
            season_data = {
                "@type": "TVSeason",
                "seasonNumber": season.season_number,
                "name": f"Season {season.season_number}",
                "url": _build_url(request, season.url),
            }
            episode_count = season.get_children().count()
            if episode_count:
                season_data["numberOfEpisodes"] = episode_count
            data["containsSeason"].append(season_data)

    return mark_safe(
        f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
    )


@register.simple_tag(takes_context=True)
def episode_jsonld(context, page):
    """
    Generate TVEpisode JSON-LD for an EpisodePage.
    Includes season context, characters, and event count.
    """
    request = context['request']

    data = {
        "@context": "https://schema.org",
        "@type": "TVEpisode",
        "name": _strip_html(page.title),
        "url": _build_url(request, page.url),
        "episodeNumber": page.episode_number,
    }

    if hasattr(page, 'logline') and page.logline:
        data["description"] = _truncate(page.logline)
    elif hasattr(page, 'high_level_summary') and page.high_level_summary:
        data["description"] = _truncate(page.high_level_summary)

    if hasattr(page, 'season_number'):
        data["partOfSeason"] = {
            "@type": "TVSeason",
            "seasonNumber": page.season_number,
        }

    # Series context
    series = page.get_ancestors().type(
        page.__class__.__mro__[0]  # Will be resolved at runtime
    ).first()
    # Walk up to find the SeriesIndexPage
    for ancestor in page.get_ancestors().specific():
        if hasattr(ancestor, 'season_number'):
            continue
        if hasattr(ancestor, 'fabula_uuid') and hasattr(ancestor, 'description'):
            data["partOfSeries"] = {
                "@type": "TVSeries",
                "name": _strip_html(ancestor.title),
                "url": _build_url(request, ancestor.url),
            }
            break

    # Characters (actors mapped to characters)
    profiles = page.character_profiles.all()[:20]
    if profiles:
        data["actor"] = [
            {
                "@type": "Person",
                "name": _strip_html(p.character.canonical_name),
                "url": _build_url(request, p.character.url),
            }
            for p in profiles
            if hasattr(p, 'character') and p.character
        ]

    # Writing credits
    if hasattr(page, 'written_by') and page.written_by:
        data["author"] = {
            "@type": "Person",
            "name": page.written_by,
        }

    return mark_safe(
        f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
    )


@register.simple_tag(takes_context=True)
def character_jsonld(context, page):
    """
    Generate Person JSON-LD for a CharacterPage.
    Includes description, traits, and affiliations.
    """
    request = context['request']

    data = {
        "@context": "https://schema.org",
        "@type": "Person",
        "name": _strip_html(page.canonical_name),
        "url": _build_url(request, page.url),
    }

    if hasattr(page, 'description') and page.description:
        data["description"] = _truncate(page.description)

    if hasattr(page, 'title_role') and page.title_role:
        data["jobTitle"] = page.title_role

    if hasattr(page, 'nicknames') and page.nicknames:
        data["alternateName"] = page.nicknames

    if hasattr(page, 'affiliated_organization') and page.affiliated_organization:
        data["affiliation"] = {
            "@type": "Organization",
            "name": _strip_html(page.affiliated_organization.canonical_name),
            "url": _build_url(request, page.affiliated_organization.url),
        }

    return mark_safe(
        f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
    )


@register.simple_tag(takes_context=True)
def event_jsonld(context, page):
    """
    Generate Article JSON-LD for an EventPage.
    Events are analytical content — the core narrative assertions.
    Includes connections as related content.
    """
    request = context['request']

    data = {
        "@context": "https://schema.org",
        "@type": "Article",
        "name": _strip_html(page.title),
        "url": _build_url(request, page.url),
        "publisher": {
            "@type": "Organization",
            "name": "Fabula",
        },
        "isPartOf": {
            "@type": "TVEpisode",
            "name": _strip_html(page.episode.title) if page.episode else "Unknown",
        },
    }

    if hasattr(page, 'description') and page.description:
        data["description"] = _truncate(page.description)
    if hasattr(page, 'analysis') and page.analysis:
        data["articleBody"] = _truncate(page.analysis, max_len=500)

    # Connections as related articles — this is the unique SEO value
    outgoing = list(page.outgoing_connections.select_related('to_event')[:10])
    incoming = list(page.incoming_connections.select_related('from_event')[:10])
    related = []
    for conn in outgoing:
        if conn.to_event:
            related.append({
                "@type": "Article",
                "name": _strip_html(conn.to_event.title),
                "url": _build_url(request, conn.to_event.url),
                "description": f"{conn.get_connection_type_display()}: {_truncate(conn.description, 150)}" if conn.description else conn.get_connection_type_display(),
            })
    for conn in incoming:
        if conn.from_event:
            related.append({
                "@type": "Article",
                "name": _strip_html(conn.from_event.title),
                "url": _build_url(request, conn.from_event.url),
                "description": f"{conn.get_connection_type_display()}: {_truncate(conn.description, 150)}" if conn.description else conn.get_connection_type_display(),
            })
    if related:
        data["relatedLink"] = related

    # Characters involved
    participations = list(page.participations.select_related('character')[:15])
    if participations:
        data["mentions"] = [
            {
                "@type": "Person",
                "name": _strip_html(p.character.canonical_name),
                "url": _build_url(request, p.character.url),
            }
            for p in participations
            if p.character
        ]

    return mark_safe(
        f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
    )


@register.simple_tag(takes_context=True)
def breadcrumb_jsonld(context, crumbs):
    """
    Generate BreadcrumbList JSON-LD.

    Args:
        crumbs: list of (name, url) tuples, e.g.:
            [("Home", "/"), ("The West Wing", "/explore/the-west-wing/"), ("Season 1", None)]
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
            item["item"] = _build_url(request, url)
        items.append(item)

    data = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": items,
    }

    return mark_safe(
        f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
    )


@register.simple_tag(takes_context=True)
def connection_jsonld(context, connection):
    """
    Generate JSON-LD for a NarrativeConnection — unique to Fabula.
    Models the connection as a structured claim about narrative relationships.
    """
    request = context['request']

    data = {
        "@context": "https://schema.org",
        "@type": "Claim",
        "name": f"{connection.get_connection_type_display()}: {_strip_html(connection.from_event.title)} → {_strip_html(connection.to_event.title)}",
        "url": _build_url(request, f"/connections/{connection.pk}/"),
    }

    if connection.description:
        data["description"] = _truncate(connection.description)

    data["about"] = [
        {
            "@type": "Article",
            "name": _strip_html(connection.from_event.title),
            "url": _build_url(request, connection.from_event.url),
        },
        {
            "@type": "Article",
            "name": _strip_html(connection.to_event.title),
            "url": _build_url(request, connection.to_event.url),
        },
    ]

    return mark_safe(
        f'<script type="application/ld+json">\n{json.dumps(data, indent=2)}\n</script>'
    )
