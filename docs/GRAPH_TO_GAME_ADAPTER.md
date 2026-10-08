# Graph-to-game adapter — working proposal and pilot gate

Revised 6 September 2026 after review · **T-040 reopened; not approved for Stage 2**.

The original purpose is a GraphRAG demonstration of Fabula's showcase story detail,
with an engaging text-adventure interface. Michael's direction remains a
**semi-probabilistic, LLM-infused text adventure**. How much the player can change
story outcomes, and whether/how characters generate new dialogue, remain open
product decisions. The previous draft incorrectly turned an observer-style option
into the product contract. This revision withdraws that decision and the claim
that producing a design document completed the work.

The next step is an authored pilot that proves worth playing. The stale export
can support a small, explicitly limited paper test; it is not yet a sound basis
for automated world construction or a large adapter architecture.

## 1. Decisions retained and decisions reopened

| Retain as a technical boundary | Leave for product testing and Michael's decision |
| --- | --- |
| Graph assertions retain their source identity and provenance; generated prose cannot become source evidence. | Whether play primarily explores recorded moments, enacts plausible extensions, or branches into alternate events. |
| Server-owned scope, reference checks and authoritative saved state. Never trust client-echoed retrieval context (ISS-027). | The amount and disclosure of generated dialogue, atmosphere, object detail and action consequences. |
| Explicit separation of source records, interpretations and invented playthrough content. | Inhabiting Jonathan versus an exploratory narrator; how much analytical attribution belongs in the main prose. |
| A missing graph source must not silently fall back to a handwritten answer while claiming GraphRAG. | How discoveries, puzzles, direct answers and physical agency should motivate continued play. |
| Deterministic evidence retrieval and actions first; LLM optional over that foundation. | Whether the increasingly written artifact is an exploration, an adventure, or a combination. |

A counterfactual playthrough, if chosen, can change its own world state without
rewriting Fabula's source graph. Its invented facts, dialogue and consequences
would need separate identity and must never be offered as canonical evidence.
This is an option to design and test, not authorization to implement it now.
Likewise, the limited paper pilot below does not permanently prohibit actions
that it cannot yet support.

## 2. Gate 0: run the paper experiment

Run the [forked three-packet paper test](DRACULA_PAPER_PLAYTEST.md) with **three
unfamiliar readers**. The [23 selected source values](prototypes/dracula-paper-packets.json)
cover two interview leads (nun/fly and bag/Agatha's intentions), a crucifix dead end,
the bedroom recollection and Agatha's hypothesis. Readers choose their route; the
manuscript is no longer advertised. These are authored navigation choices, not
asserted NarrativeConnection paths.

The paper protocol defines the next decision before sessions begin:

| Signal | Required observation |
| --- | --- |
| Unscripted breadth (U) | At least one reader makes an unsolicited request absent from the response sheet that a previously unselected YAML field answers. Record exact pointer, value hash and reply; synonyms do not count. |
| Early hypothesis (H) | At least one reader independently links blood with the private memory before packet 3 or any other answer disclosure. Record the command and clue route before confirming it. |
| Agency (A) | With at least four eligible commands per reader, DO outnumbers LOOK for at least two readers, or LOOK outnumbers DO for at least two. Count unsupported first action requests too; exclude suggestions, retries and meta commands. |

**Exit rule:** U + H passing and a clear A direction advances to source verification
and a small prototype brief. A DO majority selects consequential actions for the
next paper experiment; a LOOK majority selects deeper grounded exploration. This
is a reversible experimental stance, not a permanent restriction on generated
dialogue or alternate outcomes. Source readiness must pass before adapter construction.

If U fails, expand the evidence/opportunities to explore; if H fails, revise the
clue sequence; if A is inconclusive, revise the agency experiment. Test the revision
with a new unfamiliar cohort. A second failed round stops this version for redesign.
The [paper protocol](DRACULA_PAPER_PLAYTEST.md) defines eligible commands, prior
knowledge, disclosure, lookup limits and the [blank log](prototypes/dracula-paper-session-log.csv).
First-lead choice, dead-end recovery and voluntary stopping diagnose whether the
small scene is limiting the result. These thresholds guide a pilot; they do not
prove broad or sustained enjoyment.

Michael and the assistant can rehearse voice and facilitation. Their familiarity
with the answer excludes them from the discovery gate. Compare the attributed
voice and invented-dialogue variant only after measured play. Technical validation,
a rehearsal or reaching packet 3 cannot replace the required reader evidence.

Budget one 45-minute source review, then up to 20 minutes of play and 10 minutes
of debrief per reader. Record actual preparation and manual lookup times. This
reviews 23 selected values, not the episode's 439 participations, 347 object
involvements, 195 location involvements or thousands of prose fields. The immediate
work is the paper session and its recorded decision. **Gate 0 remains pending.**

## 3. What data we actually have

The [hashed audit](prototypes/dracula-adapter-data-audit.json) describes a
**February 18, 2026, contract v2.3.0 export** from `dracula.s01`, not a fresh graph
read. The model schema and newer contract support more than this file supplies.
Michael reports that the Dracula database does not yet have the newer enrichment
and Neo4j is currently occupied with TNG remediation. Do not expect a new export
alone to manufacture absent analysis.

| Input | February Dracula export | Consequence for this pilot |
| --- | --- | --- |
| Events and episode/scene sequence | 348 series events; 144 in episode one | Available as recorded event anchors, not a complete fictional timeline. |
| Location hierarchy | 129 locations; zero populated parent links | Do not build nested geography from inferred names. |
| Primary event location | Zero of 144 pilot events set location_uuid | Use inspected involvement rows; multiple contexts remain possible. |
| Location involvement | 143 of 144 events; 195 rows | Useful descriptions, but often analytical and sometimes retrospective. |
| Object involvement | 120 of 144 events; 347 rows | Identity collisions and repeated rows prevent naïve object materialization. |
| Character participation | 439 rows | Goals/beliefs are useful but not necessarily observable facts or physical presence. |
| Connections | 430 rows, 97 distinct UUIDs, 75 UUIDs reused | Suspected legacy export fan-out; not 430 independent meaningful leads. |
| layer, scope, inferred_by, cross_episode_reasoning | Absent from all 430 connection rows | Treat as unavailable. Schema defaults cannot establish their historical provenance. |
| Themes | Zero in manifest | No theme-based pilot route. |
| Arcs | 13 in manifest; newer storyline memberships absent | Do not assume role-bearing memberships or modern storyline enrichment. |
| Wagtail import | No Dracula series or seed interview in the inspected local DB | No live ORM-backed Dracula demo yet. Do not quietly substitute the prototype. |

The local absence is not a production audit. The old prototype's three anchor
events have no direct connecting edge among them in this file; supporting statements
inside events may still answer the question. A conclusion from those statements
must not be presented as a pre-existing edge.

### UP-007: scene-level connection fan-out

Of the 75 reused UUID groups, 31 stay within one scene. For
`conn_3fc2ea6be93d`, four events produce all 12 ordered pairs with identical
CHARACTER_CONTINUITY description. This is evidence of the reported clique pattern,
not a basis for inventing a new multi-projection provenance feature.

The current `export_connections()` code in
[export_from_neo4j.py](../narrative/management/commands/export_from_neo4j.py)
explicitly describes replacing the old scene-based Cartesian join with beat-to-event
mapping. That supports a legacy export defect diagnosis, but does not verify the
current Dracula relationships or prove that re-exporting its present data is sufficient.

The legacy importer looks up connections by endpoint pair and type. Twelve
distinct pairs therefore remain twelve rows. It does not fix the fan-out; a
warning about deduplicating UUIDs does not protect the published site.
The adapter must not offer the three repeated interview leads as independently
meaningful relationships. Quarantine this sample from traversal testing until
source relationships and mapping are verified. For paper play, use the explicitly
authored three-moment route and make no graph-path claim.

### UP-008: collapsed object identity and discarded involvements

Hammer, stake and bag are represented by `object_24bccae12e12`, named
“Sister Agatha's Hammer and Stake Kit.” The interview has three involvement rows
with that same UUID describing different things. Across episode one there are
16 repeated event/object groups, containing 37 rows: **21 excess rows beyond the
first**. Preserve that counting definition when comparing reports.

`import_object_involvements()` skips subsequent occurrences of an object within
an event. The first interview row is the hammer description; bag/stake-specific
rows can be discarded. A clean manuscript UUID does not establish clean object
identity throughout the pilot.

The paper packet retains source row indexes as provenance for separate mentions.
Those indexes are not invented canonical object IDs and do not justify spawning
portable bag/hammer/stake entities. Determine whether the collapse originated in
analysis, consolidation, export or their interaction before assigning the fix.
The same check must address whether multiple legitimate involvement records need
preserving, rather than treating every repeated UUID as a safe duplicate.

### UP-009: recollection and framing interview fused

The bedroom event `cand_evt_scene_fbdfed5d901968f6_03` has Agatha reacting “Lives?”
in `/events/26/participations/1/observed_status`, a castle bedroom location
involvement, and `/events/26/is_flashback: false`. It fuses the framing interview
reaction with the remembered action. The event cannot establish one place/time
for all its participants. Filtering out Agatha or merely flipping the flag would
leave the extraction's mixed frames unresolved.

The paper labels the bedroom as a recollection by editorial choice. Automated
room population or chronology must wait for verification of event segmentation,
derived beats and participation/frame attribution. The
[upstream journal](UPSTREAM_ISSUES.md) tracks UP-007–009 with open status and
explicitly unverified upstream ownership; the [audit](prototypes/dracula-adapter-data-audit.json)
stores the third defect's exact diagnostic values separately from player evidence.

### Neo4j verification status

Following the required `properties(r)` check, a bounded read-only query explicitly
against `dracula.s01` returned `Neo.ClientError.Database.DatabaseNotFound` on the
configured server. [Attempt and follow-up queries](prototypes/dracula-neo4j-verification.json).
No database was started, stopped, renamed or switched; no TNG query was made.
The live properties remain unverified. These are defect candidates with export/code
evidence, not confirmed current upstream graph faults. See UP-007–009
in [UPSTREAM_ISSUES.md](UPSTREAM_ISSUES.md). Verification can resume when the correct
Dracula database is available without disrupting remediation.

### Existing chat limitation to retain

The existing `connection_path` BFS uses undirected adjacency. It can describe an
association path, but does not substantiate a directed causal chain. Object
resolution is missing, timeline payloads omit rich fields, profiles can expose
later spoilers, and connection reads need both-endpoint scope checks. These are
known implementation gaps, not an adapter design or evidence that chat already
supplies the proposed game interface.

## 4. Evidence is not generated claims

The immutable evidence is the original source value/excerpt plus its identity and
hash. An LLM-proposed atomic claim or a reviewed paraphrase is a **derived annotation**,
never a replacement source. Review can mark it usable for presentation; it cannot
make the wording canonical or erase the distinction between observation and analysis.
A later generation retrieves the original evidence, not an earlier invented summary.

The immediate pilot uses 23 assistant-selected values and human-review-pending
presentation. It has no automatic extraction, no episode-wide publication, and no
claim of screenplay verification. If scalable claim normalization becomes necessary,
it needs a separately costed experiment: actual review minutes, rejection rate,
coverage and semantic errors. It is not a hidden prerequisite to Stage 2.

Keep identifiers/source validation separate from semantic fidelity. A valid citation
can still accompany an unsupported sentence. Dense phrases such as “a masterclass
in psychological and supernatural tension” are analytical material to evaluate,
not an instruction to reproduce that voice in the terminal. The paper test checks
whether selecting concrete details can retain grounding while becoming readable.

## 5. Visibility, revisions and persistence: explicit gaps

**Page records:** proposed runtime eligibility requires the selected series,
allowed episode/event scope, live status and the site's actual access restrictions.
Checking `live=True` alone does not establish public accessibility. Both endpoints
of a traversed edge must be eligible before ranking, counts or suggestions.

**Snippets:** Location, Theme and ConflictArc have no live flag. Proposed pilot
rule: permit a snippet reference only when its series matches and it is linked
from an eligible selected event; permit only the fields explicitly included in the
pilot's reviewed packet. This does not authorize its entire cross-series or
whole-story description. Unlinked/unscoped snippets and unrestricted standalone
snippet lookup are excluded from the pilot. A broader editorial publication rule
for snippets needs a separate decision and implementation; do not call them
“published” merely because a row exists. The paper fixture itself is not public
catalog content and uses file references, not invented catalog URLs.

**Temporal visibility:** episode/scene presentation order and is_flashback are
insufficient for “only what Jonathan knows now.” Pilot disclosure is that it covers
the selected Dracula episode moments. Its chosen passages need review for later
outcomes; no guaranteed spoiler-safe policy is implemented by these documents.

**Existing saves:** `adventure.views.current_run()` raises 404 on a scenario_revision
mismatch. The code does **not** preserve playable old revisions. Keep the current
revision and saves unchanged during design/paper work. Before a new runtime revision,
implement and test either dispatch to the old engine/content or an explicit,
non-destructive migration/recovery path. Merely pinning a revision is insufficient.
Do not promise backwards-compatible play until that behavior exists.

**Future persistence:** source evidence, generated presentation and any chosen
fictional overlay must remain separate. Save accepted prose for navigation/replay,
with source/policy dependencies. Scope or access changes override cache reuse.
What becomes increasingly written depends on the product stance still to be chosen;
it need not be confined forever to an observer's journal. Offline export must state
its packaged evidence boundary and cannot imply live GraphRAG or unknown source coverage.

## 6. Work after the paper decision

| Gate | Work | Exit |
| --- | --- | --- |
| 0. Reader evidence | Run the forked paper session and record U, H and A. | The rule in section 2 passes. Current status: pending; no unfamiliar-reader results. |
| 1. Source readiness | When Dracula is available, inspect properties(r), event/beat frames, connection mapping and object identity; establish repair/re-export/import scope for UP-007–009. | The chosen slice supports the prototype's required identities, frames and relationships. No disruption to TNG remediation. |
| 2. Working prototype brief and implementation | Use the observed agency direction and verified source slice to define the smallest useful graph-connected terminal experiment. | Real command play demonstrates evidence-dependent behavior, fidelity and measured review effort. Save-version behavior is proven before revision changes. |
| 3. Broader generation | Extend the authored pilot only after it proves engaging in use. | Evidence for sustained engagement, fidelity and cost at the tested level of agency. |

The adapter architecture has been removed from the active plan. Design it from
the paper findings and verified source, rather than committing to interfaces,
modules or a publication workflow before those results exist.

Retain future technical checks: reproducible source hashes; missing evidence
invalidates claims/leads; targets cannot silently change; client context cannot
become evidence; retries and concurrent turns preserve state; advertised commands
work; causal claims preserve direction. Another corpus must not require handwritten
story answers to masquerade as retrieval.

T-040 remains in progress until reader evidence and the resulting scope decision
are recorded. Paper testing is the current work; adapter construction follows its
gate and source verification. Runtime revisions and database state remain unchanged.
