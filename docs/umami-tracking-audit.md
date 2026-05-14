# Umami event-tracking audit (T-006, 2026-05)

Inventory of every `umami.track(...)` call in the codebase, a gap
analysis against the high-value interactions called out in the
ticket, a proposed event taxonomy, and three funnel definitions
that the taxonomy should enable.

## Current inventory

Every `umami.track()` call lives in one of two base templates and
all tracking is fired via a single delegated `click` listener.

### `templates/base.html` (narrative surfaces)

| Event name           | Payload                          | Trigger                                                         |
|----------------------|----------------------------------|-----------------------------------------------------------------|
| `pageview-typed`     | `{ type: pageType }`             | On page load; `pageType` derived from URL (home, catalog, series, episode, character, event, connection, graph, organization, theme, other). |
| `graph-view`         | `{ from: pageType, target }`     | Click on any link matching `/graph` or link text "Graph"/"View Graph"/"View Journey". |
| `episode-click`      | `{ from: pageType }`             | Click on any `/episodes/...` link.                              |
| `character-click`    | `{ from: pageType }`             | Click on any `/characters/...` link.                            |
| `connection-click`   | `{ from: pageType }`             | Click on any `/connections/...` link.                           |
| `series-click`       | `{ series: href }`               | Click on `/explore/<slug>/` link.                               |
| `event-click`        | `{ from: pageType }`             | Click on any `/events/...` link.                                |
| `cta-early-access`   | `{ from: pageType }`             | Click on any `/early-access` link.                              |
| `external-link`      | `{ url }`                        | Click on any `http(s)://` link off-host.                        |

### `templates/marketing_base.html` (marketing surfaces)

| Event name           | Payload                          | Trigger                                                         |
|----------------------|----------------------------------|-----------------------------------------------------------------|
| `pageview-typed`     | `{ type: pageType }`             | On page load; same URL-based classification.                    |
| `nav-explore`        | `{ from: pageType }`             | Click on a "Explore" nav link.                                  |
| `contact-click`      | `{ from: pageType }`             | Click on a "Contact" link.                                      |
| `external-link`      | `{ url, from: pageType }`        | Click on any off-host link.                                     |

### Coverage by surface

- `narrative/templates/narrative/graph_view.html` — **no tracking**.
- `narrative/templates/narrative/catalog.html` — **no tracking**.
- `narrative/templates/narrative/connection_detail.html` — **no tracking**.
- `narrative/templates/narrative/event_page.html` — **no tracking**.
- `narrative/templates/narrative/character_page.html` — **no tracking**.
- `templates/marketing/*.html` — **no per-page tracking** (no
  forms, no hero CTAs differentiated, no FAQ accordion opens).

Total: **11 distinct event names**, all fired by URL-pattern
delegation rather than by user-intent / component-aware
instrumentation.

## Gap analysis

Grouped by surface, ordered by stated importance in the ticket.

### Graph view (D3 force-directed)

The graph is the most interactive surface in the product and is
**completely untracked**. There is no signal in Umami today for:

- **Node clicks** — which node type (event / character /
  episode), which specific node id, how deep into the session.
- **Node-type filter toggles** — the user clicking
  "show / hide event nodes" etc. is a primary differentiator
  between casual and power users; not captured.
- **Edge / connection clicks** — clicks on edges in the graph
  surface a connection card; the click is tracked generically as
  `connection-click` ONLY if the click resolves to navigating to
  `/connections/<pk>/`, not if it opens an inline panel.
- **Zoom / pan** — no signal for engagement intensity.
- **Force simulation pause / play** — no signal.
- **Graph view duration / dwell time** — Umami's automatic
  pageview captures entry, but there's no exit-event so dwell on
  the graph is invisible.

### Connection cards (the "edges-as-content" pitch)

Connection cards appear on event pages and elsewhere. Today every
click on a `/connections/...` link fires `connection-click` with
nothing but `from: pageType`. The richer signals available but
not emitted:

- **Connection type** (CAUSAL, FORESHADOWING, ESCALATION, etc.)
  is in the URL slug or the data attributes already, but isn't
  in the payload.
- **Connection strength** (strong / medium / weak) similarly.
- **Source surface** — was the click from an event page's
  outgoing connections list, the incoming connections list, the
  graph view, or a search result? Currently all are flattened.

The pitch is that connections are first-class content; the
analytics taxonomy doesn't reflect that. The single bare
`connection-click` event is the equivalent of tracking every
product purchase as "product-click".

### Character-journey navigation

A character page shows the events the character participates in,
in order. Clicking from one event to the next IS captured by the
generic `event-click` event, but the payload doesn't carry:

- **Journey position** (event N of M in this character's
  journey).
- **Character context** — which character page we came from.
- **Navigation direction** (forward through the journey vs. back
  to the character page vs. cross-jump to another event).

So funnels of the form "% of character-journey starters who
reach event N" cannot be computed.

### Scoped graph toggles

The graph view has a UI toggle bank (`.node-toggle` buttons keyed
by `data-type`) that filters node types. Per CLAUDE.md / MEMORY.md
this is a meaningful UX dimension. No `umami.track()` call exists
for it.

### Catalog

`templates/narrative/catalog.html` is the discovery entry point
for the explore experience. Today:

- The `pageview-typed` event fires with `type: 'catalog'`.
- A click on a series card fires `series-click` with the series
  href.

But there is no signal for:

- **Series card hover** — for above-the-fold engagement.
- **Catalog scroll depth** — how far into the list users scroll
  before clicking.
- **Empty-state engagement** — what happens when a user filters
  / searches and finds nothing.

### Marketing pages

Only three events on marketing surfaces — `pageview-typed`,
`nav-explore`, `contact-click`. The whole funnel surface is
under-instrumented. Notable gaps:

- **Hero CTA differentiation** — `homepage_page.html` has
  multiple CTAs (early access, demo, learn more). All blur
  together because the URL-based delegation matches `early-
  access` but not the differentiated CTA placement (hero vs
  pricing vs footer vs sticky).
- **Demo / Early Access form interactions** — no
  `form-started`, `field-touched`, or `form-submitted` events
  on `demo_request_page.html` and `early_access_page.html`.
  Funnel drop-off inside the form is invisible.
- **Pricing tier clicks** — which tier did the visitor click
  "Start Trial" on?
- **FAQ accordion opens** — which questions were curious
  visitors asking?
- **Scroll-depth on long pages** (`homepage`, `product`,
  `for_production`) — no 25/50/75/100% markers.
- **Share / copy-link clicks** on benchmarks / case-study pages.

### Cross-cutting issues with the existing approach

1. **URL-pattern delegation is brittle.** When URLs change (and
   they have — the data-pipeline migration changed
   `/connections/` patterns), the delegation falls silent
   without warning. Component-anchored `data-umami-event`
   attributes are more durable.
2. **Payloads carry no entity ids.** `event-click` doesn't carry
   the event uuid, `episode-click` doesn't carry the episode
   uuid, etc. So engagement-per-entity analyses
   (which characters get clicked most?) cannot be done in
   Umami without joining against external data.
3. **No event name standardisation.** Mix of `noun-verb`
   (`graph-view`), `verb-noun` (`connection-click`), and
   `cta-x` patterns. Hard to filter / group in Umami's UI.
4. **No funnel-stage events.** Funnels are computed today by
   eyeballing four or five generic click events, which is fragile.
   Explicit `funnel:reached:<stage>` events would let Umami's
   funnel-builder do the work.

## Proposed taxonomy

### Naming convention

Use `{surface}:{verb}:{object}` consistently. Three lowercase
segments, hyphenated.

| Component | Examples                              |
|-----------|---------------------------------------|
| surface   | `marketing`, `catalog`, `narrative`, `graph`, `funnel` |
| verb      | `view`, `click`, `toggle`, `open`, `submit`, `dwell`, `reached` |
| object    | concrete UI element or stage (`series-card`, `node-type-filter`, `connection-card`, `demo-form`) |

Examples:

- `narrative:click:connection-card` — replaces the bare
  `connection-click`.
- `graph:click:node` — node click in the D3 view.
- `graph:toggle:node-type` — node-type filter toggle.
- `marketing:submit:demo-form` — form submit on Demo Request.
- `funnel:reached:event-opened` — explicit funnel-stage event.

### Payload conventions

Always include:

- `from: pageType` (already done).
- A `source` field naming the originating component when not
  obvious from the surface (e.g. `source: 'incoming-card'` vs
  `source: 'graph-edge'` for the same `narrative:click:connection-card`).

Entity-anchored events should include:

- `entity_id` (the fabula_uuid or pk).
- `entity_type` (event, character, episode, series, connection).

Connection events should include:

- `connection_type` (CAUSAL, etc.).
- `strength` (strong / medium / weak).

### Funnel events

Five canonical funnel stages, each fired once per session per
stage:

| Event                         | Fired when                                          |
|-------------------------------|-----------------------------------------------------|
| `funnel:reached:catalog`      | Catalog page viewed.                                |
| `funnel:reached:series`       | Any SeriesIndexPage viewed.                         |
| `funnel:reached:episode`      | Any EpisodePage viewed.                             |
| `funnel:reached:event`        | Any EventPage viewed.                               |
| `funnel:reached:connection`   | Any /connections/<pk>/ page viewed.                 |

These are deliberately granular so the funnel-builder can mix and
match (e.g. "% of catalog visitors who reached an event without
going through a series" — possible if all five stages fire).

### Marketing-funnel events (parallel set)

| Event                                 | Fired when                                       |
|---------------------------------------|--------------------------------------------------|
| `funnel:reached:marketing-home`       | Marketing homepage viewed.                       |
| `funnel:reached:marketing-product`    | Product page viewed.                             |
| `funnel:reached:marketing-pricing`    | Pricing page viewed.                             |
| `funnel:reached:marketing-demo-form`  | Demo request form rendered (not yet submitted).  |
| `funnel:reached:marketing-demo-submit`| Demo form submitted.                             |

## Funnel design

Three concrete funnels the proposed taxonomy should support:

### 1. Creator funnel (marketing → demo)

```
funnel:reached:marketing-home
→ funnel:reached:marketing-product
→ funnel:reached:marketing-demo-form
→ funnel:reached:marketing-demo-submit
```

Answer: "What % of homepage visitors actually request a demo, and
where do they drop off?"

### 2. Explorer funnel (catalog → connection card)

```
funnel:reached:catalog
→ funnel:reached:series
→ funnel:reached:episode
→ funnel:reached:event
→ funnel:reached:connection
```

Answer: "Did Fabula's edge-as-content pitch land for this visitor?
Did they actually open a connection card?" This is the
product-truth metric.

### 3. AI-builder funnel (for-production → early-access)

```
funnel:reached:marketing-home
→ funnel:reached:marketing-product
→ funnel:reached:for-production
→ cta-early-access  (existing; rename to funnel:reached:marketing-early-access)
→ funnel:reached:marketing-early-access-submit
```

Answer: "Is the for-production positioning landing with the
intended audience?"

## Prioritised follow-up list

In order of leverage × cheapness:

1. **Instrument graph view node clicks and node-type toggles** —
   the biggest single product surface that has zero analytics.
2. **Enrich connection-click payload** with `connection_type`,
   `strength`, and `source` (graph-edge / outgoing-card /
   incoming-card / search). Drop-in template attribute work.
3. **Add five `funnel:reached:<narrative-stage>` events** — fire
   once per session at each narrative pageview. Unlocks all three
   funnels.
4. **Add five `funnel:reached:<marketing-stage>` events** —
   parallel to (3).
5. **Instrument demo + early-access form lifecycle** —
   `form-started`, `field-touched`, `form-submitted`,
   `form-abandoned`. The single highest-leverage marketing fix.
6. **Add `entity_id` + `entity_type` to all entity click events**
   — engagement-per-character / per-episode analyses become
   possible.
7. **Hero CTA differentiation** — give each hero / footer / sticky
   CTA a `data-umami-event` attribute so they don't all flatten
   into `cta-early-access`.
8. **Catalog interactions** — `narrative:click:series-card`
   payload + scroll-depth on the catalog page.
9. **FAQ accordion opens** + pricing-tier clicks on marketing.
10. **Standardise the existing 11 events to the new taxonomy** —
    one-shot rename pass. Keep the old names firing for two
    weeks in parallel for dashboard continuity, then remove.

## Out of scope

- PII review of payloads (none of the proposed events should
  carry user-identifiable data, but a privacy review at
  implementation time is healthy).
- Umami dashboard / saved-funnel configuration (downstream of
  the taxonomy, not part of this audit).
- Page-load / Core Web Vitals signals.
