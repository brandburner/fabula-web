# JSON-LD coverage audit (T-005, 2026-05)

Audit of structured data emitted by `narrative/templatetags/seo_tags.py`
and wired into the page templates. The goal is rich-snippet eligibility,
Google Knowledge Graph inclusion, and AI-answer-engine citation
discoverability.

## Existing pipeline

- Tag library: `narrative/templatetags/seo_tags.py` (~700 lines).
- `@context` merges `schema.org` `@vocab` with Fabula's
  `fabula: https://fabula.productions/ontology/` ontology.
- Tags: `series_jsonld`, `episode_jsonld`, `character_jsonld`,
  `event_jsonld`, `connection_jsonld`, `breadcrumb_jsonld`.
- Wired in templates:
  - `narrative/templates/narrative/series_index_page.html` → `series_jsonld`
  - `narrative/templates/narrative/episode_page.html` → `episode_jsonld`
  - `narrative/templates/narrative/character_page.html` → `character_jsonld`
  - `narrative/templates/narrative/event_page.html` → `event_jsonld`
  - `narrative/templates/narrative/connection_detail.html` → `connection_jsonld`
  - Site-wide: `templates/base.html` → bare `WebSite` + `Organization`.

## Coverage matrix

| Page type           | Tag                | Top-level types emitted                                       | Wired? |
|---------------------|--------------------|---------------------------------------------------------------|:------:|
| SeriesIndexPage     | series_jsonld      | TVSeries (+ contained TVSeasons, DefinedTerm themes)          | yes    |
| SeasonPage          | _none_             | _nothing_ — no per-season detail JSON-LD                      | **no** |
| EpisodePage         | episode_jsonld     | TVEpisode + FictionalCharacter + Place + Person (writers)     | yes    |
| EventPage           | event_jsonld       | CreativeWork+fabula:NarrativeEvent + Place + chars + fabula:* | yes    |
| CharacterPage       | character_jsonld   | FictionalCharacter + Organization                              | yes    |
| NarrativeConnection | connection_jsonld  | fabula:NarrativeConnection + Claim + 2 event nodes            | yes    |
| BreadcrumbList      | breadcrumb_jsonld  | BreadcrumbList                                                | (per-page) |

## `@id` chain integrity

All `@id` values use `_url(request, page.url)` so they point at canonical
site URLs and resolve to rendered pages that emit their own JSON-LD. The
reciprocal link works: `TVEpisode.partOfSeries.@id` → `TVSeries.@id` at
`/<series>/`, which emits its own `series_jsonld`. Same for characters,
places, and connections.

### Confirmed reciprocal chains

- `TVSeries ↔ TVSeason ↔ TVEpisode` — `containsSeason` / `partOfSeason`
  / `partOfSeries` chain, all `@id`s point to live URLs that themselves
  emit JSON-LD (except `TVSeason` — see gaps).
- `TVEpisode.character` / `event_node.fabula:participations` →
  `FictionalCharacter.@id` → character page.
- `TVEpisode.contentLocation` / `event.contentLocation` → `Place.@id` →
  location page.
- `event.fabula:connections.{fromEvent,toEvent}.@id` ↔ event pages.
- `connection_jsonld` emits both end-events as stub nodes so the
  connection page itself is a complete subgraph.

### Broken / weakened `@id` chains

1. **`TVSeason.@id` dangles.** `series_jsonld` emits each season as a
   linked node (`TVSeason.@id` = season URL), but the season page does
   NOT emit a `season_jsonld` tag — that URL renders HTML without any
   structured data. From a crawler's perspective the `@id` resolves
   to a 200 but yields no reciprocal claim. Fix: add `season_jsonld`
   and wire it into `season_page.html`.
2. **`episode_node.partOfSeason` has no `@id`.** In `episode_jsonld`
   the `partOfSeason` block has `@type`+`seasonNumber` but no `@id`,
   even though `partOfSeries` does. The season page exists at a
   discoverable URL via `page.get_parent()`; emit its `@id` so
   crawlers can link the episode back to the season node.
3. **`Organization` publisher node has no `@id`.** Both `series_jsonld`
   and `event_jsonld` emit `"publisher": {"@type": "Organization",
   "name": "Fabula"}` with no `@id`. A canonical Fabula `Organization`
   `@id` (e.g. `https://fabula.productions/#org` or a `sameAs`
   pointing to the site root) would make publisher consolidation
   work across pages.
4. **`templates/base.html` `Organization` not linked to per-page
   publisher.** The site-wide `WebSite` + `Organization` graph in
   base.html uses one identifier; the per-page `publisher.Organization`
   uses no identifier. Crawlers therefore see them as separate
   entities. Reuse the same `@id`.
5. **Writer `Person` nodes have no `@id`.** `episode_jsonld.author`
   emits `Person` blocks with just `name` and `fabula:creditType`.
   Writers are real entities with stable `fabula_uuid` and pages —
   they should have `@id`s for cross-episode consolidation (Aaron
   Sorkin appearing on 22 episodes should be ONE entity, not 22
   anonymous blocks).
6. **`FictionalCharacter` `affiliation.@id` is fine** but the
   `Organization` node graph emitted alongside lacks `parentOrganization`
   even when the model has such a hierarchy. Low-impact.

## Per-page findings

### SeriesIndexPage

- **Add `genre`, `inLanguage`, `countryOfOrigin`, `numberOfEpisodes`,
  `datePublished`.** Schema.org TVSeries expects all of these and
  Google's "TV series" rich result needs at least `name`,
  `description`, `image`, `aggregateRating` (or `numberOfEpisodes`).
- **Add `image`.** No `image` is emitted today — losing rich-result
  eligibility on the TVSeries entity.
- **Add `sameAs` to Wikidata, IMDb, Wikipedia.** This is the single
  highest-leverage AI-answer-engine + Knowledge Graph signal:
  "this is THE West Wing, here's its canonical identifier." Each
  series should carry one or more `sameAs` URIs.
- **Theme node `DefinedTerm` is good** but `inDefinedTermSet` only
  has a `name`, no `@id` — give the term set an `@id` so themes
  consolidate across pages.

### SeasonPage

- **No JSON-LD at all.** Add a `season_jsonld` tag that emits
  `TVSeason` with `@id`, `seasonNumber`, `partOfSeries.@id`,
  `containsEpisode` list of `@id`s pointing at episode pages,
  `numberOfEpisodes`, and ideally `datePublished`.

### EpisodePage

- **Add `datePublished` / `dateCreated`.** Wagtail has `first_published_at`;
  use it. `TVEpisode.datePublished` is a strong rich-snippet signal.
- **Add `image`.** Same as series — no image, no rich result.
- **Add `subtitleLanguage`, `aggregateRating`** (if Fabula ever
  publishes ratings or beat-scoring), `timeRequired` (runtime).
- **Writer consolidation:** as above, give writers `@id`s.
- **Expose `EventPage.key_dialogue` as `Quotation` nodes** so
  AI-answer-engines can cite memorable lines. Currently the dialogue
  is buried in the event's `fabula:keyDialogue` array under a custom
  predicate that crawlers won't understand. Cheap to wrap in
  `schema:Quotation` alongside.

### EventPage

- **Strong coverage already** — this is the richest tag in the
  system.
- **Add `dateCreated` / `position` (scene order).** `position` is a
  schema.org property that lets a crawler reconstruct event ordering
  within an episode without inferring it from `fabula:sceneNumber`.
- **Use `subjectOf` and `mainEntityOfPage`** to point AI engines
  at the specific event URL as the canonical claim location. AI
  citation engines (Perplexity, ChatGPT search) follow these.
- **`fabula:keyDialogue` → `schema:Quotation`** (see Episode finding).
  Quote objects with `Person.@id` speaker links would be a strong
  citation hook.
- **Themes (`about`)**: good. Could add `keywords` (a flat list) for
  legacy SEO crawlers that don't follow nested `@id`s.

### CharacterPage

- **Add `sameAs`** — same Wikidata/IMDb argument as series.
- **`affiliation.Organization` is good** but lacks `parentOrganization`
  even when the data model supports it (e.g., White House → Office of
  Chief of Staff).
- **Add `subjectOf`** pointing at the character page so AI engines
  treat the URL as the canonical Fabula description of the character.
- **`fabula:traits`, `fabula:importanceTier`, `fabula:appearances`**
  are all custom predicates; generic crawlers ignore them but they
  do help Fabula-aware federation. Keep.

### NarrativeConnection

- **Strong coverage** as `Claim` + `fabula:NarrativeConnection`.
  Schema.org `Claim` is exactly the right vocabulary for "Event A
  causes Event B" — this is the project's unique edge-as-content
  pitch landing in machine-readable form.
- **Add `author`** (Fabula `Organization.@id`) on each `Claim` so
  AI engines know who is making the claim. Without it the claim
  looks anonymous and is weaker citation material.
- **Add `dateCreated`** from the model.

## Cross-cutting findings

1. **`mainEntityOfPage` is not used anywhere.** Adding it to each
   detail page (series, episode, event, character, connection) tells
   Google "the entity I'm describing here IS this URL", which both
   improves canonicalisation and helps AI engines cite the right
   page.
2. **No `Organization` `@id` is shared between base.html and per-page
   publishers** (see `@id` finding #3). Consolidate.
3. **`fabula:` namespace URI must resolve.** `FABULA_NS =
   "https://fabula.productions/ontology/"` — if a crawler fetches
   that URL it must return something machine-readable (RDF, JSON-LD
   schema, or at minimum HTML describing the terms). Currently:
   uncertain. If 404, generic semantic crawlers treat the namespace
   as broken and may downgrade trust in the full graph. File a
   follow-up to publish an ontology document at that URL.
4. **No `image` anywhere.** Every entity type (TVSeries, TVEpisode,
   FictionalCharacter, NarrativeEvent) supports `image` and several
   of Google's rich results require it. Fabula doesn't currently
   render images on detail pages, but at minimum each could emit a
   site-wide OG default (`/fabula-og-default.png` exists in the repo).
5. **Connection types in `CONNECTION_TYPE_MAP` are not exposed as
   `DefinedTerm`s anywhere.** The 9 connection types
   (CAUSAL, FORESHADOWING, …) are emitted only as inline predicates
   on individual connections. A site-wide `DefinedTermSet` listing
   them, emitted once on a /connections/ index page, would let AI
   engines understand the taxonomy as a whole.
6. **No `aggregateRating` / `interactionStatistic`** anywhere —
   could compute one from `appearance_count` or `episode_count`
   for characters, or from `event count` for episodes, to populate
   schema.org engagement signals.
7. **No sitemap entry for `/connections/<pk>/` URLs.** Outside the
   JSON-LD scope but worth flagging: connections are first-class
   content, so the XML sitemap should include them or Google will
   never see the `Claim` nodes.

## Prioritised follow-up list

In order of leverage × cheapness:

1. **Add `season_jsonld`** with `containsEpisode`. Cheap; fixes the
   only fully-missing page type and closes the `TVSeason.@id`
   dangling reference. _(new ticket)_
2. **Emit `image` everywhere** (site-wide default OK as a fallback).
   Cheap; unlocks rich-result eligibility across all entity types.
3. **Add `sameAs` URIs to SeriesIndexPage and CharacterPage** (and
   eventually OrganizationPage). Highest leverage for AI answer
   engines and Knowledge Graph; manual data work per entity but the
   plumbing is one-time.
4. **Consolidate `Organization` `@id`** between base.html and
   per-page publishers. Tiny code change; small but real authority
   signal.
5. **Give Writers stable `@id`s** in `episode_jsonld.author`.
6. **Wrap `key_dialogue` as `schema:Quotation`** with speaker
   `@id`s. Cheap and unlocks dialogue-citation paths in AI engines.
7. **Add `mainEntityOfPage` and `subjectOf`** to every detail page.
8. **Publish the Fabula ontology at `FABULA_NS`** as a real RDF/JSON-LD
   document so the namespace IRI dereferences.
9. **Emit `datePublished` on TVEpisode** from `first_published_at`,
   and `dateCreated` on connections from the model timestamp.
10. **Add `image` for the OG default fallback** + an `og:image` tag
    in `base.html` head if not already there.
11. **Add a `/connections/` index page that emits a `DefinedTermSet`
    of connection types**, plus include `/connections/<pk>/` URLs
    in the XML sitemap.

Each item is small enough to be a single ticket; items 1–7 are
under a day's work each, items 8–11 a bit more.

## Out of scope for this audit

- Open Graph and Twitter Card meta tags.
- XML sitemap structure (touched on in cross-cutting #7 but not
  audited end-to-end).
- Front-end markup beyond the JSON-LD `<script>` tags.
- Validating live URLs (we read the code only).
