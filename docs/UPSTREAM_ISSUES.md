# Upstream issues journal

A running log of data problems observed in this repo (the Wagtail
publication side) whose **root cause lives in the main fabula project**
(the Neo4j analysis pipeline / megagraph builder / GER). Each entry
records the downstream symptom, the evidence, and what upstream needs to
change — so nothing gets lost between export cycles.

Local-side workarounds (template guards, importer heuristics) can be
noted per entry, but an entry only closes when the upstream fix lands
and a re-export confirms it.

**Conventions**: newest entries first. IDs are `UP-NNN`, monotonically
increasing. Status is one of `open`, `workaround-shipped` (downstream
mitigation live, upstream fix still needed), `fixed-upstream`
(awaiting re-export verification), or `closed`.

---

## UP-004 — Storyline identity churn across megagraph rebuilds strands legacy arcs/themes (closed)

**Raised**: 2026-07-18 (retro-logged; discovered 2026-07-17 during the
T-035/T-036 staging builds) · **Series**: wolfhall, doctorwho ·
**Cross-ref**: ISS-020 (the downstream half)

**Downstream symptom**: a series upgraded in place keeps stale prod-era
storylines alongside the current ones. Wolfhall staging: 27 stale arcs
next to the 12 current (39 rendered on the storylines index). Doctor
Who staging after the GER consolidation: **1,861 of 3,125 arcs stale**
(themes: 0 stale).

**Root cause split**: upstream, megagraph rebuilds / GER consolidation
mint new arc identities — `fabula_uuid`s change per rebuild and only
`global_id`s are quasi-stable — so rows from a prior import match
nothing in the new export. Downstream (tracked as ISS-020, ours):
`import_fabula --cleanup` doesn't cover ConflictArc/Theme, and the
v2.4 `--cleanup --dry-run` exits at shape validation before the
cleanup planner runs, so the preview is silently unavailable.

**Upstream ask**: keep storyline identity stable across rebuilds when
the underlying arc/theme is unchanged (persist `global_id` at minimum,
ideally `fabula_uuid` too), and/or emit a superseded-ids list in the
export so downstream pruning is deterministic instead of a both-ids
heuristic.

**Downstream workaround (shipped on staging)**: surgical purge script —
delete arcs scoped to the series that match **neither** the export's
`fabula_uuid`s **nor** its `global_id`s (uuid-only checks false-positive
on in-place v2.4 upgrades, which match snippets by `global_id` and
retain legacy `fabula_uuid`s).

**Update (2026-07-26, upstream commit ec35ea1)**: the corruption chain
is fixed at all four links. Both merger paths now fetch real storyline
properties (name/description/conflict_description) instead of the
entity-convention names that don't exist on season Theme/ConflictArc
nodes, and GER-created storylines are guaranteed a name (this is what
left arcs born-nameless). The prefetch status filter includes
NULL-status nodes, so storyline source properties load during unified
creation. `consolidate_storylines` no longer falls back to a raw uuid
as a display name (the exact step that stamped GER ids onto 610 arcs).
And the superseded-ids ask is implemented: survivors accumulate
`superseded_uuids`/`superseded_global_ids` before merged nodes are
deleted, GER merges record the loser's id (plus inherited lineage) on
the winner, and the megagraph merger carries it through — exports can
now emit the deterministic prune list. The 610 corrupted names in the
current `doctorwho.mega` are repaired by the T-005 rebuild; closes on
re-export verification after that rebuild.

**Closed (2026-07-31)**: re-export from the rebuilt `doctorwho.mega`
verified — 1,616 arcs / 375 themes, **zero** GER-id names, every row
carrying `superseded_uuids` (1,614 arcs with non-empty lineage). Both
halves are now shipped: contract v2.5.0 exports the lineage
(`export_from_neo4j.py`, arcs/themes), and the ISS-020 downstream half is
fixed — `import_fabula --cleanup` covers Theme/ConflictArc (keep on
current-uuid or current-global_id match, delete superseded/unmatched,
skip when the export has no storyline rows) and `--cleanup --dry-run` on
a ≥2.4 export now reaches the planner instead of exiting at the shape
gate. Stale-arc purge on staging/prod happens on the next real
`--cleanup` import.

---

## UP-003 — Theme materialization hasn't run on current-generation graphs (open)

**Raised**: 2026-07-18 (retro-logged; discovered 2026-07-16/17 during
storylines Phases 2–4) · **Series**: wolfhall, happyvalley2 (doctorwho
OK) · **Cross-ref**: ISS-015

**Downstream symptom**: megagraph exports ship an empty `themes.yaml`,
so storyline surfaces are **arc-only** for the affected series —
no theme timelines, no theme-based navigation.

**Evidence**: only `nightmanager.s01` (10) and `encanto.s01` (4) have
Theme nodes at all. `happyvalley2` carries only
`related_theme_names_initial` precursor lists on arcs — the
materialization stage never ran. `wolfhall.mega` has no Theme labels.
`doctorwho.mega` *does* have themes materialized — which is the wider
lesson: **layer materialization varies per graph generation/instance**
(doctorwho conversely lacks the Event→Event connection layer wolfhall
has, so no season bridges there). Always probe topology before an
export: `MATCH (a)-[r]->(b) RETURN labels(a)[0], type(r), labels(b)[0],
count(*)`.

**Upstream ask**: run the theme materialization stage on the
happyvalley2/wolfhall generation of graphs and ensure Theme nodes
survive into `.mega` builds; ideally make per-layer presence a checked
invariant of the mega build rather than a per-run accident.

**Update (2026-07-26)**: waits on the wolfhall/happyvalley2 Neo4j
instance swap before the materialization stage can run.

**Update (2026-07-31)**: the parenthetical DW observation above is now
stale — the rebuilt `doctorwho.mega` (T-005) carries a full Event→Event
layer (43,858 edges, all with `connection_uuid`/`inferred_by`, zero
backwards). The wolfhall/happyvalley2 theme-materialization ask itself
still waits on the instance swap.

**Downstream half (already resolved here)**: migration 0025 (T-031,
commit `ca5711d`) backfilled `Theme.series` / `ConflictArc.series` from
membership evidence — 47/47 westwing themes and 96/99 arcs scoped.

---

## UP-002 — `*SeasonProfile` nodes carry no `description` (closed)

**Raised**: 2026-07-18 · **Series**: doctorwho (only megagraph export with
season profiles so far)

**Downstream symptom**: the "Across the Seasons" tabs on entity pages
render empty panels — just the "SEASON N · TIER" label over a blank
body. The tabs work; there is simply nothing to show. Users read the
whole section as broken (e.g. Brigadier Lethbridge-Stewart,
`ger_agent_d5e52d5a4263`).

**Evidence**: all **22,306 rows** in
`fabula_export/doctorwho/season_profiles.yaml` have `description: ''`
(10,301 object, 6,202 location, 4,222 character, 1,581 organization).
The exporter reads `p.description` off `*SeasonProfile` nodes
(`export_from_neo4j.py`, `export_season_profiles`); the v2.4.0 contract
(`docs/YAML_CONTRACT.md`) defines the field as the "verbatim per-season
portrait".

**Open question**: is the portrait missing from the graph entirely, or
stored under a different property name? Neo4j was down when diagnosed.
To settle: `MATCH (p:AgentSeasonProfile) RETURN keys(p) LIMIT 5`
against `doctorwho.mega`. If it's a naming mismatch, the fix may be a
one-line exporter change here instead of an upstream one — reclassify
accordingly.

**Upstream ask**: populate `description` on `AgentSeasonProfile` /
`LocationSeasonProfile` / `ObjectSeasonProfile` / `OrgSeasonProfile`
nodes with the per-season portrait text, or document the property that
already holds it.

**Downstream workaround (not yet shipped)**: hide the season tabs when
every profile description is blank, so the section doesn't render as a
dead widget.

**Update (2026-07-26) — reclassified local**: the open question is
settled — the portrait was never missing, it's stored as
`foundational_description` on `*SeasonProfile` nodes; the exporter was
reading the wrong property. Fixed in this repo
(`export_from_neo4j.py`, `export_season_profiles`): reads
`foundational_description` first, falling back to legacy
`description`. No upstream change needed; the upstream ask above is
moot. Closes when the next doctorwho re-export ships non-empty
portraits in `season_profiles.yaml`.

**Closed (2026-07-31)**: re-export from the rebuilt `doctorwho.mega`
ships 22,207/22,207 non-empty season-profile portraits.

---

## UP-001 — GER entity resolution: duplicate organizations (closed)

**Raised**: 2026-07-18 · **Series**: doctorwho

**Downstream symptom**: characters get an arbitrary single affiliation.
Brigadier Lethbridge-Stewart shows "Ministry of Defence" instead of
UNIT: the graph gives him **nine** org affiliations, the export fans
them out as nine duplicate character rows, and the importer's
first-occurrence dedupe keeps whichever org happens to come first in
file order.

**Evidence**: the nine affiliated orgs include three UNIT variants that
exist as **separate org nodes** — "United Nations Intelligence
Taskforce (UNIT)" (`ger_organization_8c8ffa8cb5fb`), "UNIT Global
Command Unit (Strategic Intelligence Taskforce)"
(`ger_organization_3379779b9059`), and "UNIT"
(`ger_organization_5904e0e523f6`) — plus near-duplicates like "British
Army (Goodge Street HQ…)", "Regular Army", "Earth's Military and
Authorities", and "Brigadier Lethbridge-Stewart's Command".

**Upstream ask**: GER should merge same-real-world-organization nodes
(UNIT ×3 at minimum) so each org resolves to one `ger_organization_*`
id. Even a smarter downstream "most-frequent affiliation wins"
heuristic is defeated while UNIT's votes are split three ways.

**Related local work (this repo, not upstream)**:
`CharacterPage.affiliated_organization` is a single FK, so multiple
affiliations can't be stored even once the graph is clean. Supporting
multiple affiliations means an M2M/through model, an export shape
change (contract v2.5), importer support, and template updates.

**Update (2026-07-26, upstream T-003 non-agent dedup pass)**: the org
merge landed. UNIT is one canonical org — "UNIT (United Nations
Intelligence Taskforce)", 12 season mappings — absorbing the three
variants named above plus Geneva Central Command. Same pass also
merged K9, the sonic screwdriver, four TARDIS Console Room variants,
the canonical Daleks collective, Whitehall, and the Nemesis Statue;
net 28 duplicate globals eliminated, 23 winners carrying merge
lineage. Detection note for future passes: the similarity detector
never surfaced the UNIT trio — it came from CROSS_GLOBAL reports plus
a name sweep. The merge lives in the fabulager: the current
`doctorwho.mega` still shows the Brigadier's nine affiliations and
heals when T-005 rebuilds from the cleaned fabulager. Closes on
re-export verification after that rebuild. The local single-FK limitation above is unchanged
and is now the remaining cause of wrong/arbitrary affiliations
(first-occurrence dedupe still picks whichever org row comes first).

**Closed (2026-07-31)**: re-export from the rebuilt `doctorwho.mega`
verified — exactly one canonical "UNIT (United Nations Intelligence
Taskforce)" organization; the Brigadier fans out to 8 affiliation rows
(down from 9), the remaining ones legitimately distinct (the Inferno
"Brigade Leader" is a separate persona by design). The single-FK
multi-affiliation limitation stays a **local** roadmap item (M2M +
contract v2.6, importer, templates) — not an upstream issue.
