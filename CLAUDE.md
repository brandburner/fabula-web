# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Fabula Web is a Wagtail 7.2 / Django 5.1 application that publishes narrative graph analysis. The core challenge it solves: **connections between narrative events are first-class content**, not just navigation links. Each connection (causal, foreshadowing, thematic parallel, etc.) has its own URL, description, and semantic weight.

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
wagtail_models/           # Django app
├── models.py             # All Wagtail pages, snippets, and Django models
├── views.py              # Custom views for connections, themes, arcs, graph
├── urls.py               # Non-page URL routes
├── templatetags/         # Custom filters and inclusion tags
│   └── narrative_tags.py
└── management/commands/
    ├── import_fabula.py  # YAML → Wagtail import (idempotent via fabula_uuid)
    └── export_to_yaml.py # Neo4j → YAML export

wagtail_templates/
├── base.html             # Master template (Tailwind CSS, Alpine.js, Lucide)
├── narrative/            # Page-type templates
│   ├── event_page.html
│   ├── character_page.html
│   ├── episode_page.html
│   ├── connection_detail.html
│   └── graph_view.html   # D3.js force-directed graph
└── includes/             # Reusable components
    ├── connection_card.html
    ├── participation_card.html
    └── event_card.html
```

## Common Commands

```bash
# Import narrative data from YAML
python manage.py import_fabula ./fabula_export

# Dry-run import (validate without saving)
python manage.py import_fabula ./fabula_export --dry-run

# Export from Neo4j to YAML
python export_to_yaml.py --output ./fabula_export --series "The West Wing"
```

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
