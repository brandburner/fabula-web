# Fabula YAML Contract

> **Contract version**: 2.6.0 (this document is the source of truth for the
> Neo4j → YAML → Wagtail interchange format)
> **Graph schema**: pinned to `fabula_v2/docs/FABULA_SCHEMA_GROUND_TRUTH.md` v1.2.0
> **Producer**: `narrative/management/commands/export_from_neo4j.py` (this repo,
> short-term; long-term the exporter belongs beside `export_dataset.py` in fabula_v2)
> **Consumer**: `narrative/management/commands/import_fabula.py`
> **Change policy**: additive and versioned. The manifest carries
> `fabula_version`; the importer validates it and refuses shapes it does not
> understand. Bump the minor version for additive changes, the major for
> breaking ones.

## Version history

| Version | Change |
|---|---|
| 2.3.0 | Megagraph mode: unified cross-season entities, `season_appearances`, `local_uuids`, acts/plot beats |
| 2.4.0 | Event-layer connections (native, no fan-out), beat layer de-fan-out with `layer`/`scope`, full arcs/themes storyline shape, episode ordinals everywhere, optional `character_episode_profiles.yaml` and `season_profiles.yaml` |
| 2.5.0 | Storyline merge lineage: arcs/themes carry `superseded_uuids`/`superseded_global_ids` (winner-side ids absorbed across rebuilds/consolidation — upstream ec35ea1, UP-004), giving the importer a deterministic prune list; `--cleanup` covers Theme/ConflictArc |
| 2.6.0 | **This document.** Character affiliations become a list: `characters[].affiliations[]` carries every `AFFILIATED_WITH` edge with `relationship_type`, `confidence` and `reasoning`, ranked strongest-tie-first (UP-001, ISS-025). The scalar `affiliated_organization_uuid` survives as the head of that list |

## Manifest (`manifest.yaml`)

Required keys: `fabula_version` (semver string), `export_date`,
`source_database`, `megagraph_mode` (bool), per-model counts. The importer
refuses a missing/unparseable `fabula_version`, imports `< 2.4.0` on the
legacy path, and requires the shapes below for `>= 2.4.0`.

## Episode reference block (used throughout)

Wherever an episode is referenced, the reference is denormalized so no
consumer ever touches bare episode numbers (megagraph hazard: every season
has an "episode 1"; see fabula_v2 commit `852c584`):

```yaml
episode: {uuid: ep_…, season: 1, number: 5, ordinal: 105}
# ordinal = season * 100 + number   (season 0 on single-season DBs)
```

## `connections.yaml`

Two layers, one file, discriminated by `layer`. The 10-type vocabulary (both
layers): `CAUSAL, CHARACTER_CONTINUITY, THEMATIC_PARALLEL, SYMBOLIC_PARALLEL,
EMOTIONAL_ECHO, ESCALATION, CALLBACK, FORESHADOWING, TEMPORAL,
NARRATIVELY_FOLLOWS`.

### Event-layer row (primary form, from native `(:Event)-[r]->(:Event)` edges)

```yaml
- fabula_uuid: conn_9f2c41ab08de          # connection_uuid from the graph edge
  global_id: null                          # null until GER-exported; key on fabula_uuid
  from_event_uuid: cand_evt_scene_94cd_1
  to_event_uuid: cand_evt_scene_7909_1
  connection_type: FORESHADOWING           # full 10-type vocabulary
  strength: medium                         # verbatim graph value (strong|medium|weak)
  description: "…"
  layer: event
  scope: cross_episode                     # intra_episode | cross_episode (derived from endpoints)
  inferred_by: llm_cross_episode_arc       # provenance passthrough (may be null)
  cross_episode_reasoning: "…"             # null for intra-episode
  arc_uuids: [arc_…]                       # PART_OF_ARC intersection of both endpoints
                                           # (workaround until fabula_v2 stamps arc_uuid)
  from_episode: {uuid: ep_…, season: 1, number: 5, ordinal: 105}
  to_episode:   {uuid: ep_…, season: 2, number: 1, ordinal: 201}
```

Direction invariant: every cross-episode edge is validated `earlier → later`
under the composite ordinal — including CALLBACK (the *later* event does the
calling back).

### Beat-layer row (intra-episode texture, one row per beat edge — NO fan-out)

```yaml
- fabula_uuid: conn_f846bf418e72
  global_id: ger_narrativeconnection_…     # preserved — existing site URLs survive
  from_event_uuid: …
  to_event_uuid: …
  connection_type: CAUSAL
  strength: strong                         # beat layer vocab is strong|moderate|weak;
                                           # importer normalizes moderate → medium
  description: "…"
  layer: beat
  scope: intra_episode
  from_episode: {…}
  to_episode: {…}
```

Collision rule (importer): if a beat row and an event row share
`(from_event, to_event, connection_type)`, the **event layer wins**; the beat
row is skipped and logged.

## `arcs.yaml` (full storyline shape)

```yaml
- fabula_uuid: arc_4476355656a7
  global_id: ger_conflictarc_…             # may be null
  name: "Cromwell's rise against the old nobility"   # ConflictArc.name — short stable identity
  arc_type: SOCIETAL                       # canonical: INTERNAL | INTERPERSONAL | SOCIETAL
                                           # legacy graphs may carry ENVIRONMENTAL |
                                           # TECHNOLOGICAL | UNKNOWN (passed through verbatim)
  description: "…"                         # conflict_description — distinct from name
  series_uuid: ser_wolf_hall
  season_appearances: [1, 2]               # deduplicated
  episode_count: 14
  events:                                  # from PART_OF_ARC, ordered by ordinal
    - {event_uuid: cand_evt_…, role: START,   episode: {uuid: ep_…, season: 1, number: 1, ordinal: 101}}
    - {event_uuid: cand_evt_…, role: null,    episode: {…}}
    - {event_uuid: cand_evt_…, role: CLIMAX,  episode: {…}}
  involved_character_uuids: [agent_…, agent_…]        # from INVOLVED_IN_ARC
  superseded_uuids: [arc_…, arc_…]         # v2.5.0: arc_uuids this storyline absorbed
                                           # (consolidation/rebuild lineage; may be [])
  superseded_global_ids: [ger_conflictarc_…]  # v2.5.0: absorbed GER ids (may be [])
```

`role` ∈ `START | CLIMAX | RESOLUTION` (nullable).

The superseded lists are the importer's deterministic prune signal: a stored
row whose ids match neither the export's current ids nor survive the lineage
check is a stale generation and `--cleanup` deletes it (see guarantees below).

## `themes.yaml`

Same treatment as arcs, minus roles:

```yaml
- fabula_uuid: theme_…
  global_id: ger_theme_…                   # may be null
  name: "…"
  description: "…"
  series_uuid: ser_…
  season_appearances: [1, 2]
  episode_count: 9
  events:                                  # from EXEMPLIFIES_THEME, with episode blocks
    - {event_uuid: cand_evt_…, episode: {…}}
  related_character_uuids: [agent_…]       # from RELATED_TO_THEME
  superseded_uuids: [theme_…]              # v2.5.0 — as arcs.yaml
  superseded_global_ids: [ger_theme_…]     # v2.5.0 — as arcs.yaml
```

Per-event `arc_uuids` / `theme_uuids` remain on the event files too —
redundancy is cheap and lets the importer cross-check (union, warn on
disagreement).

## `characters.yaml` — affiliations (v2.6.0)

A character belongs to as many organizations as the graph ties them to.
Pre-2.6.0 exports expressed that as **row fan-out** — one duplicate
character row per `AFFILIATED_WITH` edge, differing only in
`affiliated_organization_uuid` — and the importer's dedupe kept whichever
came first, which is Neo4j row order and therefore meaningless. That is
how Brigadier Lethbridge-Stewart published as a Time Lord (UP-001).

v2.6.0 emits one row per character with the edges collected:

```yaml
- fabula_uuid: ger_agent_d5e52d5a4263
  global_id: ger_agent_d5e52d5a4263
  canonical_name: Brigadier Alistair Lethbridge-Stewart
  affiliated_organization_uuid: ger_organization_5904e0e523f6   # = affiliations[0]
  affiliations:                            # ranked, strongest tie first
    - organization_uuid: ger_organization_5904e0e523f6
      relationship_type: leader            # free text — see below
      confidence: 0.9                      # 0-1, from the upstream inference pass
      reasoning: "Commands UNIT's field operations…"
    - organization_uuid: ger_organization_022800f6bc78
      relationship_type: ally
      confidence: 0.8
      reasoning: "…though not indicating direct membership…"
```

`relationship_type` is **free text, never an enum**. Doctor Who alone has
69 distinct values: `member`, `employee`, `leader`, `representative` and
`ally` cover 97% of edges, but the tail (`omen-bearing`, `gatekeeper`,
`ex-member`) is real and a choices field would fail the import on it.

**Ranking** (`Neo4jExporter.rank_affiliations`, so producer and consumer
can't disagree): role tier first — tier 0 leader/founder/commander,
tier 1 member/employee/operative/agent/soldier/lieutenant/subordinate,
tier 2 representative *and anything unrecognised*, tier 3 ally/former
member — then the organization's season breadth descending, then
confidence descending,
then `organization_uuid` for stability. Breadth outranks confidence
deliberately: the Brigadier leads both UNIT (0.90, 12 seasons) and a
one-episode Goodge Street detachment (0.95), and UNIT is the answer a
reader expects.

`affiliated_organization_uuid` is retained so pre-2.6.0 importers keep
working; it is `affiliations[0].organization_uuid`, never an arbitrary row.

## `series.yaml` and event files

Every episode entry carries `season_number` and `sort_ordinal` in addition to
`episode_number`. Event filenames use the full series slug + composite
ordinal (`{series_slug}_s{NN}e{NN}.yaml`) — the former
`{series_uuid[:10]}` truncation was a collision hazard.

## `character_episode_profiles.yaml` (optional, all DBs)

From `AgentEpisodeProfile` nodes; keyed on `(character_uuid, episode_uuid)`
(matches `CharacterEpisodeProfile`'s unique constraint):

```yaml
- character_uuid: agent_…
  episode_uuid: ep_…
  description_in_episode: "…"              # role_in_episode + state synthesis
  core_dilemma: "…"                        # core_dilemma_or_conflict_in_episode
  change_or_stasis: "…"                    # significant_change_or_stasis_in_episode
  traits_in_episode: [w, x]
  contradictions: [y]
```

## `season_profiles.yaml` (optional, megagraph exports only)

From `*SeasonProfile` nodes (`HAS_SEASON_PROFILE`), verbatim per-season
descriptions keyed by `(entity_global_id, season_number)`; entity rows also
carry `arc_summary` (LLM cross-season arc summary) and `season_appearances`:

```yaml
- entity_global_id: ger_agent_…
  entity_type: character                   # character | location | object | organization
  season_number: 1
  description: "…"                         # verbatim per-season portrait
  tier: anchor
  source_database: wolfhall_s01
```

## Importer guarantees (v2.4.0+)

- Event-layer rows keyed on `fabula_uuid` (`connection_uuid`), with
  `(from, to, type)` fallback; beat rows keyed on `global_id`.
- Strength normalized to one DB vocabulary: `moderate → medium`.
- Legacy purge (rows with unset/legacy `layer`) runs inside the same
  transaction as the inserts, scoped via `_descendants_of()`, gated by
  dry-run/`--yes`, with every deleted identifier logged first.
- Re-import is idempotent: same export twice → no changes on the second run.

## Importer guarantees (v2.5.0)

- `--cleanup` covers Theme/ConflictArc (ISS-020), series-scoped. Per-row
  precedence: keep on `fabula_uuid` match; keep on `global_id` match
  (in-place upgrades retain legacy `fabula_uuid`s by design); otherwise
  delete — whether named in a superseded list (deterministic lineage) or
  matching nothing (stale generation).
- `--cleanup --dry-run` on a ≥2.4.0 export prints the full cleanup plan
  (previously the v2.4 shape gate exited before the planner ran — ISS-020).

## Importer guarantees (v2.6.0)

- Every affiliation lands in `CharacterAffiliation` (character,
  organization, relationship_type, confidence, reasoning, rank,
  is_primary), keyed on `(character, organization)`.
- `CharacterPage.affiliated_organization` stays populated as the
  denormalised head of that list — admin, search and older code keep
  working — but it is now `rank=0`, not "first row in the file".
- **Pre-2.6.0 exports still gain affiliations.** The loader harvests the
  fan-out rows before dedupe discards them, so the other series get their
  full membership without a re-export. Those rows carry org identity
  only: no `relationship_type`, no `confidence`, no `reasoning`, and a
  flat rank, because file order means nothing.
- Re-import prunes affiliations the export no longer asserts, so an
  upstream org merge doesn't leave orphaned ties behind.
