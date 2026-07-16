# Fabula YAML Contract

> **Contract version**: 2.4.0 (this document is the source of truth for the
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
| 2.4.0 | **This document.** Event-layer connections (native, no fan-out), beat layer de-fan-out with `layer`/`scope`, full arcs/themes storyline shape, episode ordinals everywhere, optional `character_episode_profiles.yaml` and `season_profiles.yaml` |

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
  arc_type: SOCIETAL                       # INTERNAL | INTERPERSONAL | SOCIETAL
  description: "…"                         # conflict_description — distinct from name
  series_uuid: ser_wolf_hall
  season_appearances: [1, 2]               # deduplicated
  episode_count: 14
  events:                                  # from PART_OF_ARC, ordered by ordinal
    - {event_uuid: cand_evt_…, role: START,   episode: {uuid: ep_…, season: 1, number: 1, ordinal: 101}}
    - {event_uuid: cand_evt_…, role: null,    episode: {…}}
    - {event_uuid: cand_evt_…, role: CLIMAX,  episode: {…}}
  involved_character_uuids: [agent_…, agent_…]        # from INVOLVED_IN_ARC
```

`role` ∈ `START | CLIMAX | RESOLUTION` (nullable).

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
```

Per-event `arc_uuids` / `theme_uuids` remain on the event files too —
redundancy is cheap and lets the importer cross-check (union, warn on
disagreement).

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

## Importer guarantees (v2.4.0)

- Event-layer rows keyed on `fabula_uuid` (`connection_uuid`), with
  `(from, to, type)` fallback; beat rows keyed on `global_id`.
- Strength normalized to one DB vocabulary: `moderate → medium`.
- Legacy purge (rows with unset/legacy `layer`) runs inside the same
  transaction as the inserts, scoped via `_descendants_of()`, gated by
  dry-run/`--yes`, with every deleted identifier logged first.
- Re-import is idempotent: same export twice → no changes on the second run.
