# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fabula Web is a Wagtail 7.2 / Django 5.2 application that publishes narrative graph analysis. The core challenge it solves: **connections between narrative events are first-class content**, not just navigation links. Each connection (causal, foreshadowing, thematic parallel, etc.) has its own URL, description, and semantic weight.

**Data flow**: Neo4j (analysis) → YAML (curation) → Wagtail (publication)

## Key Architecture Concepts

### Hybrid Page/Model Design
- **Wagtail Pages**: Series, Season, Episode, Character, Organization, Event (benefit from page tree, drafts, rich text)
- **Wagtail Snippets**: Theme, ConflictArc, Location (reusable content, not navigable pages)
- **Django Models**: NarrativeConnection, EventParticipation, CharacterEpisodeProfile (relationships with rich edge data)

### Connections as Content
`NarrativeConnection` is the key innovation - it stores the narrative assertion explaining WHY two events connect, not just THAT they connect. Connections have:
- Their own URLs (`/connections/<pk>/`)
- Type taxonomy (CAUSAL, FORESHADOWING, THEMATIC_PARALLEL, etc.)
- Strength indicators (strong/medium/weak)
- Descriptive content (the analytical claim)

### Navigation Patterns
The app supports three navigation modes:
1. **Character journeys**: Follow a character through events via EventParticipation
2. **Theme exploration**: Browse events by thematic tag
3. **Graph traversal**: Navigate via incoming/outgoing connections

## Project Structure

```
narrative/                # Django app (the models live HERE, not wagtail_models/)
├── models.py             # All Wagtail pages, snippets, and Django models
├── views.py              # Custom views for connections, themes, arcs, graph
├── urls.py               # Non-page URL routes
├── templatetags/
│   └── narrative_tags.py # Custom filters and inclusion tags
├── templates/narrative/  # Page-type templates (writerly + dark variants)
│   ├── event_page.html
│   ├── character_page.html
│   ├── connection_detail.html
│   ├── graph_view.html   # 3d-force-graph view
│   └── includes/         # connection_card, participation_card, pagination, …
├── tests/                # ALL tests live here (never narrative/tests.py or
│                         # inside management/commands/ — see ISS-004)
└── management/commands/
    ├── import_fabula.py     # YAML → Wagtail import (idempotent via fabula_uuid)
    ├── export_from_neo4j.py # Neo4j → YAML export (--megagraph for megas)
    └── delete_series.py     # Two-stage series-tree deletion (PROTECT-safe)

templates/base.html       # Master template (Tailwind CSS, Alpine.js, Lucide)
marketing/                # Marketing site app (serves the site root)
fabula_web/               # Settings (base.py/dev.py/production.py), root urls
docs/YAML_CONTRACT.md     # Versioned YAML interchange contract (v2.4.0)
```

## Common Commands

```bash
# Export from Neo4j to YAML (megagraph mode for .mega databases)
python manage.py export_from_neo4j --database wolfhall.mega --megagraph --output ./fabula_export/wolfhall -y

# Import narrative data from YAML (single-series directory)
python manage.py import_fabula ./fabula_export/<series>

# Dry-run import (validate without saving; v2.4.0 exports get shape validation)
python manage.py import_fabula ./fabula_export/<series> --dry-run

# Import with cleanup: deletes deprecated entities WITHIN the imported series
# (series-scoped; other series never touched). Asks for confirmation; pass
# --yes in scripts. Pair with --dry-run to preview the deletion plan only.
python manage.py import_fabula ./fabula_export/<series> --cleanup --dry-run
python manage.py import_fabula ./fabula_export/<series> --cleanup --yes

# Delete a whole series tree safely (events first — PROTECT FK — then tree)
python manage.py delete_series <slug-or-fabula_uuid> --dry-run
```

All manage.py commands need `DJANGO_SETTINGS_MODULE=fabula_web.settings.dev`.
The YAML format is a versioned contract (`docs/YAML_CONTRACT.md`); the manifest
carries `fabula_version` and the importer refuses shapes it doesn't understand.
Full operator runbook (multi-series imports, --cleanup with preview,
series-tree deletion, prod transfer): see `docs/import-workflow.md`.

## Model Relationships

```
SeriesIndexPage → SeasonPage → EpisodePage
                                    ↓
                               EventPage ←─── EventParticipation ───→ CharacterPage
                                    ↑
                          NarrativeConnection (from_event → to_event)
                                    ↓
                    (M2M to Theme, ConflictArc snippets)
```

Key relationships:
- `EventPage.episode` → FK to EpisodePage
- `EventPage.participations` → Inline EventParticipation (rich edge data: emotional_state, goals, what_happened)
- `EventPage.outgoing_connections` / `incoming_connections` → NarrativeConnection
- `CharacterPage.affiliated_organization` → FK to OrganizationPage

## Connection Type Taxonomy

| Type | Icon | Use |
|------|------|-----|
| CAUSAL | arrow-right | A directly causes B |
| FORESHADOWING | sparkles | A hints at B |
| THEMATIC_PARALLEL | git-merge | A and B explore same theme |
| CHARACTER_CONTINUITY | rotate-ccw | Character state evolves |
| ESCALATION | trending-up | B raises stakes from A |
| CALLBACK | arrow-left | B explicitly references A |
| EMOTIONAL_ECHO | heart | B evokes same emotion as A |
| SYMBOLIC_PARALLEL | equal | A and B share symbolic meaning |
| TEMPORAL | clock | Time structure connection |

## Template Tags

Load with `{% load narrative_tags %}`:

- `{{ conn_type|connection_class }}` → CSS class (e.g., `conn-causal`)
- `{{ conn_type|connection_color }}` → Hex color
- `{% connection_icon conn_type %}` → Lucide icon name
- `{% event_card event show_episode=True %}` → Render event card
- `{% connection_summary event direction='both' limit=3 %}` → Inline connections
- `{% get_episode_context event as ep_context %}` → "S1E4" format

## Import Pipeline Details

The `import_fabula` command is idempotent using `fabula_uuid` as the lookup key. Import order respects dependencies:

1. Themes, ConflictArcs, Locations (snippets)
2. Organizations → Characters (pages)
3. Series → Seasons → Episodes (hierarchy)
4. Events (depend on episodes, locations)
5. EventParticipations (depend on events, characters)
6. NarrativeConnections (depend on events)

## Frontend Stack

- **CSS**: Tailwind CSS 3.4 via CDN
- **Icons**: Lucide (via CDN)
- **Interactivity**: Alpine.js for reactive components
- **Graph**: D3.js force-directed layout in `graph_view.html`

## Visual Design Conventions

Connection types use consistent color coding defined in `narrative_tags.py`. CSS classes follow pattern `conn-{type}` (e.g., `conn-causal`, `conn-foreshadowing`). Templates use CSS custom properties for theming.

## Deployment Target

Railway (PaaS) with:
- PostgreSQL database
- Gunicorn WSGI server
- WhiteNoise for static files
