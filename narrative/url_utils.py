"""
Single source of truth for narrative entity URL *format*.

The same entity is reachable at two URLs — a series-scoped one
(`/explore/<series>/events/<id>/`, the canonical/primary form used by internal
navigation and the `/explore/` design) and a legacy global one
(`/events/<id>/`). To stop these drifting apart, every caller that needs an
entity URL — the `{% narrative_url %}` tag, the canonical-tag view mixin, and
the sitemaps — funnels through `build_entity_url()` here.

Callers resolve the `series_slug` differently for performance:
- single page view: from the object's Wagtail ancestry (`get_ancestors`)
- sitemaps: from a prebuilt `{series.path: slug}` dict (NEVER per-item
  `get_ancestors` — that's a query per row / 10k per child sitemap)

`build_entity_url` is format-only and does no DB work.
"""

from django.urls import reverse


# class name -> (series-scoped url name, global url name or None)
PAGE_URL_NAMES = {
    'EventPage': ('series_event_detail', 'event_detail'),
    'CharacterPage': ('series_character_detail', 'character_detail'),
    'OrganizationPage': ('series_organization_detail', 'organization_detail'),
    'ObjectPage': ('series_object_detail', 'object_detail'),
    'EpisodePage': ('series_episode_detail', None),  # episodes always need a series
}

# Index page class name -> (series-scoped url name, global url name)
INDEX_URL_NAMES = {
    'OrganizationIndexPage': ('series_organization_index', 'organization_index'),
    'CharacterIndexPage': ('series_character_index', 'character_index'),
    'ObjectIndexPage': ('series_object_index', 'object_index'),
    'LocationIndexPage': ('series_location_index', 'location_index'),
}


def entity_identifier(obj):
    """The stable identifier used in URLs: global_id, then fabula_uuid, then pk."""
    return (
        getattr(obj, 'global_id', None)
        or getattr(obj, 'fabula_uuid', None)
        or str(obj.pk)
    )


def build_entity_url(class_name, series_slug, identifier):
    """Return the canonical (series-scoped when possible) path for an entity.

    Returns the scoped URL when `series_slug` is given, else the global URL,
    else None (snippets/unknown types — the caller falls back to
    `obj.get_absolute_url()`).
    """
    if class_name == 'SeriesIndexPage':
        # identifier is the series slug for landing pages
        return reverse('series_landing', kwargs={'series_slug': identifier})

    names = PAGE_URL_NAMES.get(class_name)
    if names:
        series_url_name, global_url_name = names
        if series_slug:
            return reverse(series_url_name, kwargs={
                'series_slug': series_slug, 'identifier': identifier,
            })
        if global_url_name:
            return reverse(global_url_name, kwargs={'identifier': identifier})
        return None

    index_names = INDEX_URL_NAMES.get(class_name)
    if index_names:
        series_url_name, global_url_name = index_names
        if series_slug:
            return reverse(series_url_name, kwargs={'series_slug': series_slug})
        return reverse(global_url_name)

    return None


def series_slug_from_ancestry(obj):
    """Resolve an entity's owning series slug from its Wagtail ancestry.

    Single-object use only (one `get_ancestors` query). Returns None for
    snippets / pages with no series ancestor.
    """
    from .models import SeriesIndexPage

    if not hasattr(obj, 'get_ancestors'):
        return None
    for ancestor in obj.get_ancestors():
        specific = ancestor.specific
        if isinstance(specific, SeriesIndexPage):
            return specific.slug
    return None


def canonical_path_for(obj):
    """The canonical URL path for an entity: series-scoped for tree pages,
    global `get_absolute_url()` for cross-series snippets. Used for the
    `<link rel=canonical>` tag. May return None if neither is resolvable
    (caller should fall back to the request path)."""
    class_name = type(obj).__name__
    if class_name == 'SeriesIndexPage':
        return build_entity_url(class_name, None, obj.slug)

    series_slug = series_slug_from_ancestry(obj)
    scoped = build_entity_url(class_name, series_slug, entity_identifier(obj))
    if scoped:
        return scoped
    get_abs = getattr(obj, 'get_absolute_url', None)
    return get_abs() if callable(get_abs) else None
