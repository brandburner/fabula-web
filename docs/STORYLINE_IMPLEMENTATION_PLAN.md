# Storyline Support — Implementation Plan

> **Status**: Draft plan — derived from `docs/STORYLINE_ARCHITECTURE_BRIEF.md` (2026-07-16)
> **Verified against code**: 2026-07-16 (`narrative/models.py`, `export_from_neo4j.py`,
> `import_fabula.py`, `narrative/views.py`, templates, migrations 0001–0019)
> **Structure**: five phases, each independently shippable, mirroring the brief's §6.

## 0. Verification notes — where the code differs from the brief

The brief's gap analysis (G1–G7) is confirmed. Six findings adjust the implementation:

1. **R4 is inverted.** `ConnectionStrength` (models.py:51) is already
   `strong | medium | weak` — there is no `moderate` in the model. Normalization at
   import is therefore **beat-layer `moderate` → `medium`**, not `medium → moderate`
   as §4.2 states. No model change needed for strength.
2. **ArcType needs no migration.** The enum (models.py:80) already contains
   `INTERNAL | INTERPERSONAL | SOCIETAL` (plus legacy `ENVIRONMENTAL | TECHNOLOGICAL`,
   harmless to keep). G3 is purely an exporter defect: `export_arcs()` writes
   `title == description == conflict_description` and defaults `arc_type` to
   INTERPERSONAL (export_from_neo4j.py:999-1005).
3. **`EpisodePage.season_number` already exists** (denormalized, migration 0016).
   The G5 ordering audit is a cheap sweep, not a schema change. Six call sites order
   by bare `episode_number` (see Phase 0); `EventIndexView`, `get_participations()`,
   and the graph season gate are already season-correct.
4. **The exporter's beat-layer query already emits all 10 types including
   `NARRATIVELY_FOLLOWS`** (export_from_neo4j.py:1608-1612). Django doesn't enforce
   choices at the DB level, so such rows may already exist unlabeled in the DB. R5
   is real but is a display/validation gap, not an import-crash gap.
5. **`ParentalManyToManyField` does not support `through` models** (modelcluster
   limitation). The brief's §4.2 through-model-with-`SeparateDatabaseAndState` plan
   won't work as written. Use **plain junction models** instead —
   `EventBeatLink` (models.py:1824) is the in-repo precedent. See Phase 2.
6. **`--cleanup` never touches connections, themes, or arcs** — `scoped_specs`
   (import_fabula.py:2014-2021) covers only EventPage/EpisodePage/SeasonPage/
   CharacterPage/OrganizationPage/Location. The v2.4.0 legacy-connection purge (§4.3,
   R3) is **new code**, not an extension of the existing cleanup.

Also confirmed: `manifest.yaml` already carries `fabula_version: 2.3.0` but the
importer loads and **never reads** it (import_fabula.py:191, 336); the on-disk
wolfhall export is dated 2026-02-20 (pre-enrichment) so a re-export is required
regardless; `wagtail.contrib.redirects` + middleware are installed (base.py:18,59),
so the R1 redirect map has infrastructure ready; and
`NarrativeConnection.fabula_uuid` is neither unique nor indexed (models.py:1538) —
it must be indexed before becoming the import key.

## 1. Decisions adopted (brief §8 — confirm or veto)

- **Q1 — Unified storyline presentation**: adopt the brief's recommendation. Theme
  and ConflictArc stay separate models; add a shared
  `/explore/<series>/storylines/` index interleaving both (Phase 3).
- **Q2 — Beat layer**: keep it, exported as `layer: beat` rows without fan-out,
  preserving GER `global_id`s and therefore existing URLs (Phase 1). Site UX leads
  with the event layer; beat rows provide intra-episode texture.
- **Q3 — westwing re-run**: upstream (fabula_v2) decision; gates that series' wave
  in Phase 4 only. Nothing here blocks on it.

---

## Phase 0 — Hardening (no schema changes; de-risks everything after)

**0.1 Episode-ordering sweep (G5).** Move every bare-`episode_number` sort onto
`('episode__season_number', 'episode__episode_number')` (or path-first, matching
`CharacterPage.get_participations()` models.py:686-690):
- views.py:457 (`ThemeDetailView` events)
- views.py:502 (`ArcDetailView` events)
- views.py:592-594, 602-604 (`LocationDetailView` involvements + events)
- views.py:828-831 (`OrganizationDetailView` involvements)
- models.py:999-1001 (`ObjectPage.get_involvements()`)
- `EpisodePage.Meta.ordering` (models.py:519) → `['season_number', 'episode_number']`
- `EventPage.Meta.ordering` (models.py:1134) mirrors it via `episode__…`
- character_page.html `episode_profiles` loop is unordered — add a default ordering
  on `CharacterEpisodeProfile` (Meta only; no data migration).

**0.2 Pagination + query hygiene (G7).**
- Paginate `ConnectionIndexView`, `ThemeIndexView`, `ArcIndexView`, and the catalog
  (only `ConnectionTypeView` and `NarrativeSearchView` paginate today).
- `EventIndexView`: stop materializing (`list(context['events'])` views.py:954) —
  order/group in SQL, paginate; same fix in `EventIndexPage.get_context`
  (models.py:1235-1258). *(Shipped as flat event-level pagination; lens review
  flagged that an episode straddling a page boundary splits its group across
  pages — episode-level pagination refinement tracked as ISS-011.)*

**0.3 Search coverage (G7).** Extend `NarrativeSearchView` (views.py:1692) beyond
events/characters/themes to arcs and connections now (locations/objects/orgs
opportunistic). Connection `description` is searchable prose today;
`cross_episode_reasoning` joins in Phase 2. Interim implementation is capped
`icontains` (8 rows/branch); before the Phase 4 fleet multiplies connection
rows, route arc/connection search through the Wagtail search index (or a
`pg_trgm` index on the prose fields) like events/characters already are.

**0.4 PROTECT-FK deletion fix (R7 = tracker ISS-002/ISS-005).** Fix series-tree
deletion ordering (EventPages first, then tree). The expanded re-import flow hits
this constantly; land it before Phase 2. Bundle the open cleanup-robustness issues
that are cheap here (ISS-007 confirmation prompt, ISS-008 bulk deletes).

**0.5 Test-suite unblock (ISS-004).** `narrative/tests.py` vs `narrative/tests/`
collide and 5 view tests fail pre-existing. Phases 1–3 need a trustworthy suite;
fix the collision first.

**Exit criteria**: all indexes paginate; no bare-episode_number ordering remains
(grep-clean); series deletion works end-to-end; test suite green.

## Phase 1 — Contract (exporter v2.4.0 + import validation + docs)

**1.1 `docs/YAML_CONTRACT.md`.** Lift brief §4.1 verbatim into a versioned contract
doc. Pin `export_from_neo4j.py` to `FABULA_SCHEMA_GROUND_TRUTH.md` v1.2.0 (header
comment + doc link).

**1.2 Event-layer connections export (G1/G2).** New query alongside the existing
one: `(:Event)-[r]->(:Event) WHERE type(r) IN $types` — no scene re-projection.
Emit per §4.1: `fabula_uuid` (=`connection_uuid`), `global_id: null`, endpoints,
type, verbatim `strength`, `description`, `layer: event`, `scope` (derived from
endpoint episodes), `inferred_by`, `cross_episode_reasoning`, denormalized
`from_episode`/`to_episode` blocks with `{uuid, season, number, ordinal}` where
`ordinal = season*100 + number`. Arc attribution: intersect endpoints'
`PART_OF_ARC` memberships (workaround until fabula_v2 stamps `arc_uuid`, brief §7.1)
— emit as `arc_uuids: [...]` on the row.

**1.3 Beat-layer export, de-fan-out (Q2).** Keep the PlotBeat→PlotBeat query
(export_from_neo4j.py:1617-1633) but emit one row per beat edge mapped to its
event pair (`layer: beat`, `scope: intra_episode`), keeping GER `global_id`s.
Episode blocks included for symmetry.

**1.4 Full arcs/themes export (G3/G4).** `export_arcs()` reads `name` (identity)
and `conflict_description` (prose) separately, real `arc_type`, `series_uuid`,
deduped `season_appearances`, member `events` from `PART_OF_ARC` with `role` +
episode blocks ordered by ordinal, `involved_character_uuids` from
`INVOLVED_IN_ARC`. `export_themes()` the same minus roles (`EXEMPLIFIES_THEME`,
`RELATED_TO_THEME`).

**1.5 New optional files.** `character_episode_profiles.yaml` from
`AgentEpisodeProfile` (all DBs); `season_profiles.yaml` from `*SeasonProfile` nodes
+ entity `arc_summary`/`season_appearances` (megagraph only).

**1.6 Episode ordinals everywhere.** Add `season_number` + `sort_ordinal` to every
episode reference in series.yaml and event files. While touching filenames, fix R6:
full series slug + composite ordinal instead of `{uuid[:10]}_sNNeNN`.

**1.7 Import-side version gate.** `run_import()` reads the (currently ignored)
manifest: `fabula_version >= 2.4.0` → new shapes; older → today's paths
(backwards compatible); unknown/missing → refuse with a clear message.
**Confine the gate to one dispatch point** — a phase table (name → filename,
loader, importer method) selected once per run — rather than spreading
v2.4-vs-legacy branches through the per-entity importers. `import_fabula.py`
is already a 2,100-line single-class command with an 11-positional-parameter
`run_import()`; Phases 1–2 add five phases and two files, so the dispatch
refactor lands here, before the growth, not after.

**1.8 Docs.** Update `CLAUDE.md` (stale `wagtail_models/` paths → `narrative/`) and
`docs/import-workflow.md`. (`DATA_FLOW.md`/`EXPORT_USAGE.md` from brief §4.5 are
not in this repo — they're fabula_v2's to retire.) Also update the two
hand-maintained agent-facing surfaces in `fabula_web/urls.py` — `sitemap_md()`
(lines 296-317) and `agent_friendly_404()` (lines 224-244) — whose URL-pattern
tables list `/connections/<id>/` and must document the layer/scope split, the
redirect semantics for collapsed beat-layer URLs (Phase 2.5), and later the
storylines route (Phase 3.2); prefer deriving the table from `urlpatterns`
so it can't go stale again.

**Exit criteria**: re-export wolfhall from `wolfhall.mega`; manifest says 2.4.0;
connections.yaml contains ~1,814 event-layer rows (zero backwards under the
ordinal check) + beat rows with preserved global_ids; arcs.yaml has real names,
types, members, roles; `import_fabula --dry-run` passes the version gate and
validates shapes.

## Phase 2 — Models & import (migrations 0020+)

**2.1 `NarrativeConnection`.**
- Add: `layer` (`event|beat`, default `beat` for legacy rows), `scope`
  (`intra_episode|cross_episode`), `inferred_by` (CharField, blank),
  `cross_episode_reasoning` (TextField, blank), nullable `from_episode`/`to_episode`
  FKs → EpisodePage (SET_NULL) — makes "bridges seasons" one indexed query.
- Add `NARRATIVELY_FOLLOWS` to `ConnectionType` + icon/color/class in
  `narrative_tags.py` and the graph `CONNECTION_CONFIG`.
- Index `(scope, connection_type)`; add `db_index=True` on `fabula_uuid` (it becomes
  the event-layer import key; currently unindexed, models.py:1538).
- Keep `unique_together (from_event, to_event, connection_type)`; collision rule:
  **event layer wins**, beat row skipped + logged (R2).

**2.2 Junction models (not `through=` — see verification note 5).**
`ArcEventMembership(event FK, arc FK, role CharField null, episode_ordinal int)`
and `ThemeEventMembership(event FK, theme FK, episode_ordinal int)`, each
`unique_together (event, arc|theme)`, modeled on `EventBeatLink`. Data migration
backfills from the existing M2M rows (`role/ordinal` null → filled on next
import). Keep the legacy M2Ms through Phase 3 (templates/admin still read them),
retire in a follow-up migration once all read paths use the junctions.
Add `involved_characters` M2M on ConflictArc (from `INVOLVED_IN_ARC`) and
`related_characters` on Theme (`RELATED_TO_THEME`).

**2.3 Season-profile model.** `CharacterSeasonProfile` mirroring
`CharacterEpisodeProfile` (`character FK, season_number, description, tier,
source_database`, unique on `(character, season_number)`), + `arc_summary`
TextField on CharacterPage (megagraph entity extra). Location/Object/Org season
profiles deferred until a surface needs them.

**2.4 Import phases (v2.4.0-gated).**
- Arcs/themes: set `series` FK (G4 — FK fields already exist, importer just never
  sets them), name/description split, memberships from the `events` lists,
  reconciled (union + warn) against per-event `arc_uuids`/`theme_uuids`.
- Connections: event-layer rows keyed on `fabula_uuid` with `(from, to, type)`
  fallback; beat rows keyed on `global_id` as today; strength normalization
  `moderate → medium`; populate episode FKs from the YAML blocks.
- **Legacy purge (R3)** — five lens findings converged here; the spec is now:
  (a) the purge and the connection inserts run **inside the same
  `transaction.atomic()` as `run_import()`** — never as a separate
  cleanup-style call — so a failed insert rolls the purge back too (a crash
  between purge and insert must not leave a series with zero connections);
  (b) scoping **reuses `_descendants_of()`** (import_fabula.py:2106) — no
  second hand-rolled series-scope computation (ISS-001 taught this lesson);
  (c) the purge participates in `--dry-run` preview and is gated by the
  same confirm/`--yes` flow T-018 added to cleanup — never unconditional;
  (d) before deleting, the purge **logs every deleted connection's
  identifiers** (pk, fabula_uuid, endpoints, type) so the deletion set is
  reviewable and reconstructable;
  (e) named tests: `ConnectionPurgeScopingTest` (two sibling series — B's
  connections survive a purge of A), a collision-precedence test (seed a
  beat row, import an event row on the same `(from, to, type)`; event layer
  wins, skip logged), and the R3 idempotency test.
- New phase: `character_episode_profiles.yaml` → `CharacterEpisodeProfile`
  (existing `(character, episode)` unique key; model needs no change).
- New phase (megas): `season_profiles.yaml` → `CharacterSeasonProfile` +
  `arc_summary`.

**2.5 Redirect map (R1).** The purge writes `wagtail.contrib.redirects` rows
(installed, middleware active): old connection pk-URL → surviving event-layer
connection where endpoints+type match, else → the from-event page. Log unmatched.
Watch AgentMiss/GSC after wolfhall ships; sitemap regenerates automatically.
For any purge against **production** data (Phase 4), take a
`pg_dump narrative_narrativeconnection` (or full dump) immediately before the
import — connection descriptions are curated content, and the transaction
guard only covers failed runs, not a bad-but-successful purge.

**Exit criteria**: `import_fabula ./fabula_export/wolfhall` (real run) — arcs have
series + members + roles; connection rows carry layer/scope/reasoning/episode FKs;
zero fan-out leftovers; redirects in place; re-running the import is idempotent
(no stacking, R3).

## Phase 3 — Storyline UX

**3.1 Arc timeline (headline deliverable).** `arc_detail.html` (currently a flat
list, no grouping): group `ArcEventMembership` by season → episode via
`episode_ordinal`; START/CLIMAX/RESOLUTION role badges; involved-character rail;
**"Season bridges"** section — cross-episode connections with both endpoints in
this arc and `from_episode.season_number != to_episode.season_number` (wolfhall:
228). Gate the section on data presence (R8 — partial-enrichment series must not
render an empty promise). Theme detail gets the same treatment minus roles.

**3.2 Storylines index (Q1).** `/explore/<series>/storylines/` interleaving arcs +
themes — presentation-only, no new model.

**3.3 Connection surfaces.**
- `ConnectionIndexView`: actually scope the already-routed series URLs
  (urls.py:72 vs 211 currently both render global data) via the new episode FKs;
  filter/split by `scope`; paginated (Phase 0).
- `connection_detail.html`: "Why this matters across episodes" block
  (`cross_episode_reasoning`); discreet `inferred_by` provenance; directional
  framing for FORESHADOWING/CALLBACK — "Seeded in S1E5 → pays off in S2E1" (both
  point forward in broadcast order, brief §2.3).
- `event_page.html`: split incoming/outgoing (template reads related managers
  directly, event_page.html:304) into "Within this episode" / "Across episodes"
  by `scope`.

**3.4 Character journey.** `CharacterDetailView` (views.py:723-729) is what the
page actually uses — `get_emotional_journey()` is defined+tested but dead
(models.py:692); either wire it in or enrich the view directly. Interleave
`CharacterEpisodeProfile` cards (ordered, season-filtered — the current template
loop is neither); megagraph series get `arc_summary` + per-season profile tabs
from `CharacterSeasonProfile`.

**3.5 Graph + JSON-LD.** `build_graph_data` edge dicts gain `scope` so the graph
can style/filter cross-episode edges; extend connection JSON-LD with the new
fields where schema.org allows.

**3.6 Accessibility (cross-cutting for 3.1–3.5).** The plan previously said
nothing about accessibility; the new surfaces must specify it up front:
- Storylines index (3.2): ARIA landmark/heading structure; arc/theme cards as
  links with accessible names.
- Arc timeline (3.1): role badges carry `aria-label` (the existing
  participation_card.html convention); season groups are headed sections, not
  purely visual dividers.
- Season profile tabs (3.4): full WAI-ARIA Tabs pattern — `role="tablist"` /
  `tab` / `tabpanel`, `aria-selected` + `aria-controls`, roving tabindex with
  arrow-key + Home/End navigation, first available season selected on load.
  (No tab precedent exists in the repo; the graph node-toggles are NOT a model
  to copy — they lack ARIA state.)
- Scope filters/toggles (3.3): keyboard-operable with visible focus and
  announced state.

**3.7 Performance guard.** The storyline views are derived, read-heavy, and
change only on import: (a) season-bridges is one set-based query —
`NarrativeConnection.objects.filter(from_event__in=arc_member_event_ids,
to_event__in=arc_member_event_ids, scope='cross_episode')
.select_related('from_event__episode', 'to_event__episode')` — never a
per-membership loop; (b) apply the existing `cache_page` pattern
(CharacterDetailView precedent) to arc/theme detail and the storylines index,
and make the importer **clear the cache on completion** — the 24h TTL already
outlives an import, which also affects today's cached character pages.

**Exit criteria**: wolfhall arc pages show season-grouped timelines with role
badges and a populated season-bridges rail; series-scoped connection index splits
intra/cross; event pages split connection blocks; character pages show episode
profiles. **Automated tests gate exit** (not just visual checks): arc-detail
grouping/ordering across two seasons, season-bridges query (incl. an arc
confined to one season → empty rail gated off, and a connection with a null
episode FK → excluded without raising), scope-split rendering on event pages,
and tab-panel wiring for season profiles.

## Phase 4 — Fleet rollout (per brief §6 readiness table)

Order: **wolfhall (pilot, done in Phases 1–3)** → happyvalley2 + indianajones
(wave 2) → startrektng (wave 3, label enrichment "partial" in UI per R8) →
westwing (after upstream re-run decision) → doctorwho (blocked on T-005 mega
rebuild). Each series: pre-import `pg_dump` backup → re-export → `--dry-run` →
import → spot-check bridges → prod transfer via the established
`pg_dump -Fc | pg_restore` path (never import_fabula over the Railway TCP
proxy). **Per-wave gate**: advance to the next wave only when every series in
the current wave has passed spot-check and prod transfer; a series that fails
mid-wave is either retried in place (single-series re-export/re-import) or
explicitly deferred to a later wave — never silently skipped.

---

## Risk register (brief §5 → where mitigated)

| Risk | Mitigation | Phase |
|---|---|---|
| R1 URL churn from de-fan-out | Beat rows keep global_ids; redirect map via wagtail.contrib.redirects; monitor AgentMiss | 1.3, 2.5 |
| R2 layer collision on (from,to,type) | Event layer wins; beat row skipped + logged | 2.1, 2.4 |
| R3 re-import stacking | Series-scoped legacy purge before insert; idempotency test | 2.4 |
| R4 strength vocab | `moderate→medium` at import (direction corrected vs brief) | 2.4 |
| R5 enum drift | `NARRATIVELY_FOLLOWS` added before any v2.4.0 import | 2.1 |
| R6 filename truncation | Full slug + composite ordinal while touching exporter | 1.6 |
| R7 PROTECT-FK deletion | Fixed up front (ISS-002/ISS-005) | 0.4 |
| R8 partial enrichment | Bridge UI gated on data presence; "partial" label | 3.1, 4 |

## Out of scope (fabula_v2 tickets, brief §7)

1. Stamp `arc_uuid` on arc-guided enrichment edges (until then: PART_OF_ARC
   intersection in the exporter, 1.2).
2. GER export for event-layer connections (optional; `connection_uuid` keying
   suffices).
3. westwing enrichment re-run decision; doctorwho T-005 mega rebuild.

## Lens review log

**Round 1 (2026-07-16, reviewId lens-mrnpc5wn)** — 9 lenses, full coverage.
Verdict: **REVISE** — 0 blocking, 7 major, 7 minor, 3 suggestions. All findings
were incorporated into this document in the same session:

| Finding (lens) | Disposition |
|---|---|
| Legacy purge: no backup/gate (data-safety), transaction boundary (error-handling), no audit log (security), scoping reuse (clean-code), scoping+collision test gaps (test-quality) | §2.4 rewritten as a 5-point spec; prod backup step added to §2.5 and Phase 4 |
| Importer god-class growth (clean-code) | §1.7 now requires the phase-table dispatch refactor before the gate lands |
| Flat event pagination splits episodes (performance) | Shipped in T-016; episode-level refinement filed as ISS-011 |
| Phase 3 has no test strategy (test-quality) | Exit criteria now name the required automated tests |
| No accessibility consideration + tabs pattern (accessibility ×2) | New §3.6 |
| icontains search scans (performance) | §0.3 notes the interim caps and the pre-fleet index requirement |
| No caching for storyline views (performance) | New §3.7, incl. cache-clear-on-import |
| sitemap_md/agent_friendly_404 staleness (api-design) | §1.8 extended |
| Fleet wave partial failure (error-handling) | Phase 4 per-wave gate |
| Phase 0.4 bundling (clean-code, suggestion) | Moot — shipped with per-issue tests and resolutions (ISS-002/005/007/008) |

Round 2 re-review is recommended at the start of Phase 1 implementation, against
this revised text.
