# Wolf Hall projection experiment — results

Built 2026-10-08. Question: can an episode's locations and events in the Fabula graph form the
spine of a generative text adventure, with an LLM narrating grounded content on demand and a
deterministic engine persisting the result, **with zero hand authoring**?

Answer so far: **yes, the spine holds.** Wolf Hall S01E01 is walkable end to end from the graph
alone. The weaknesses are in the data's identity and granularity, not in the mechanism.

## What was built

| Module | Role |
| --- | --- |
| `adventure/projection.py` | Reads one published episode from Wagtail/Postgres into a JSON world: moments (events in presentation order), rooms (primary locations), features (involvement-only locations), containment, participants, objects. Keyed by `fabula_uuid` throughout. Includes a coverage report. |
| `adventure/explore.py` | Deterministic engine over that world: position is a moment; `next`/`back` step the episode; `go to <place>` jumps to that place's next recorded moment; `look`/`watch`/`examine` are passages written once and persisted; `who`, `map`, `journal`, `evidence`, `what does X want` are computed. Parser never substitutes a target: ties ask, absent entities say so. Compiles to the same offline transition table as the Dracula prototype. |
| `adventure/narrator.py` | The DM. Builds an observational packet per passage and renders it either verbatim (`local`) or paraphrased in second person (`openrouter`). Both persist the packet's source pointers. |
| `adventure/scenarios.py` | One interface for the views: the hand-authored Dracula prototype and any number of projected worlds from `settings.ADVENTURE_WORLDS`. Dracula's routes, session key and saves are unchanged. |
| `world_report` command | `python manage.py world_report --series wolf-hall --episode 1 [--samples N] [--json]` |

Play at `/play/wolf-hall-e1/` (dev only; `ADVENTURE_ENABLED` is off in production). The same
terminal, writing room, freeze, restart and offline download work as for Dracula.

Tests: 119 pass after the grounding check and retire command (32 new in `adventure/tests/test_projection.py` on a fixture episode with nested
locations, a feature-only place, a flashback, an identity collision and an unpublished event).

## What the graph supplies for S01E01

| Measure | Value |
| --- | --- |
| Moments (live events) | 87, all with a primary location and at least one location involvement |
| Rooms (distinct primary locations) | 27, of which 14 hold a single moment |
| Rooms with a recorded parent / with children | 11 / 4 |
| Feature locations (appear only in involvements) | 15 |
| Ancestors pulled in for containment, outside the episode | 4 |
| Moments in the busiest room | 25 in "York Place Audience Chamber (Central Hall)", then Esher 10, Austin Friars 7 |
| Moments without objects / without dialogue | 18 / 3 |
| Flashbacks | 5 |
| Characters present / single-appearance | 59 / 17 |
| Objects | 73 |
| Passages possible (look + watch + each person and object per moment) | 731 |

## Findings

1. **Moving in space is moving in time.** Position is a moment, so `go to Esher` lands on Esher's
   next recorded moment. That is honest to the record and plays well, but a reader expecting a
   persistent room they can idle in will notice. With 14 of 27 rooms holding one moment, the
   episode is more a sequence of scenes than a map. The spine is events at places, not places.
2. **The primary location is a coarse bucket; involvements name the real rooms.** Moment 1 is
   "Cromwell at the upper-chamber window" but its primary location is the Audience Chamber, which
   absorbs 25 of 87 moments. The LocationInvolvement rows name the Upper Chamber. The engine
   therefore treats involvement places as destinations too, and `look` renders every involvement
   at the moment, primary first.
3. **Location identity is split, not duplicated.** No two Location rows share a name stem, but the
   same place appears under different names: "Upper Chamber of York Place" and "York Place -
   Upper Chamber (Stormy Night - Episode 1)"; "Main Hall of Blackfriars (Legatine Court)" and
   "Blackfriars Legatine Court (Main Hall)"; three Cromwell bedchambers; three Austin Friars
   containers. The parser surfaces these as "Which do you mean?" rather than guessing. This is an
   upstream entity-resolution gap worth a UP entry once verified against the graph.
4. **The hierarchy is partly nonsense.** "Gates of York Place" parents the Upper Chamber;
   "Heart of the Fight" is a location. Containment is displayed, never trusted as a route.
5. **Three fields are retrospective analysis, not observation.** `EventPage.description`
   ("a masterclass in power's true nature"), `Location.description` (series-wide, names later
   events and the Esher scourge) and `ObjectInvolvement.description_of_involvement` ("not merely an
   article of clothing but a symbol"). The first two are kept out of every narrated packet and
   shown only under `evidence`, as are LocationInvolvement's `functional_role`,
   `symbolic_significance` and `description_of_involvement`. The object field is still narrated
   because it is the only description an object has; it is the weakest link for spoilers.
6. **The observational fields are good.** `observed_atmosphere`, `key_environmental_details`,
   `access_restrictions`, `what_happened`/`observed_status` and `status_before/after_event` render
   into a coherent room and action with no editing. `what_happened` equals `observed_status` in
   all 391 participations, so the two are redundant in this export.
7. **Bare names carry no kind.** "Patch" (`ger_object_a6406bc07bbf`) is Wolsey's mule, recorded
   as an object; the narrator receives only the name in the `objects` list and rendered it as
   "a patch". Animals, kits and documents all arrive as undifferentiated object names. Seven
   `key_dialogue` entries are placeholders ("(No direct dialogue occurs…)"), now filtered.
8. **Goals and beliefs are interpretation.** They are exposed through `what does X want`, labelled
   as the record's reading, and never fed to the narrator.

## Second series by configuration: Happy Valley S01E01

Added 2026-10-08 with one line in `settings.ADVENTURE_WORLDS` and no change to the projection,
engine or narrator. Playable at `/play/happy-valley-e1/`.

| Measure | Wolf Hall S01E01 | Happy Valley S01E01 |
| --- | --- | --- |
| Moments | 87 | 85 |
| Rooms / single-moment rooms | 27 / 14 | 43 / 25 |
| Moments in the busiest room | 25 | 6 |
| Rooms with a parent / with children | 11 / 4 | 13 / 5 |
| Feature locations | 15 | 22 |
| Flashbacks | 5 | 0 |
| Moments without participants / objects | 0 / 18 | 1 / 8 |
| Characters / objects | 59 / 73 | 46 / 106 |
| Passages possible | 731 | 754 |
| Offline download | 4.3 MB | 6.2 MB |

What the second series showed:

- **The claim holds for projection and play.** Every command family worked on the first run.
- **Happy Valley's primary locations are finer.** No room acts as a bucket: the busiest holds 6
  moments, against Wolf Hall's 25. The cost is more fragmentation: 25 of 43 rooms hold a single
  moment, which strengthens finding 1. The spine is events at places.
- **Possessive names broke the parser, and the fixes are general.** Happy Valley names places
  and things after people ("Catherine's House", "Catherine's Cheap Sunglasses"). Three defects
  surfaced, none Wolf Hall specific. An owner name no longer identifies the thing, so
  "examine catherine" when she is absent says so instead of offering her sunglasses. For places,
  an owner name still counts, so "go to catherine" asks among her nine places. When one candidate
  contains all the others, containment decides: "go to the farm" means the farm, not its yard.
  The part before a dash ("York Place - Upper Chamber") now names the container rather than the
  room. Wolf Hall replays unchanged, except "go to york place" now asks rather than guessing.
- **Identity splits recur.** "Mrs. Beresford's Office (Ryan's School)" and "Mrs. Beresford's
  Office (St. Marks Junior School)" are two Location rows that look like one place. Same class as
  finding 3.
- **Presence looks fused across scenes.** Moments 22 and 23 sit in the school office with a second
  involvement at Catherine's rear doorstep. They list "70-Year-Old Community Witness (Hebden
  Bridge)" from the opening newsagent scene among those present. This looks like the fused-frame
  pattern recorded for Dracula as UP-009, and needs graph verification before it is filed.
- **The offline download scales badly.** At 6.2 MB it is now a practical limit: every moment
  carries the arrival text of every place it can jump to. Sharing those blocks is the fix.

## Shared, durable passages (added 2026-10-08)

The world now writes itself for everyone. Passages belong to the world, not to a visitor.

- **Auto-accept.** The first passage written for a slot is stored in `WorldPassage` and serves
  every later visitor. A visitor's save keeps only position, visited moments and which passages
  they have seen.
- **Fingerprinted by the record.** Each row stores a hash of the source packet it was written
  from. If a reimport changes that record, the hash no longer matches, the old row is retired and
  kept as history, and the next request writes a fresh passage.
- **Two editions per slot.** Each slot is written at most once per backend: the local author's
  verbatim record, and the LLM author's telling. Visitors get their chosen backend's passage, or
  the other one if theirs isn't written. A frozen visitor reads whatever exists and writes nothing.
- **The LLM budget belongs to the world.** `ADVENTURE_WORLD_LLM_BUDGET`, default 1000, caps the
  LLM passages a world may accumulate across all visitors. A world's natural ceiling is its slot
  count, about 750 per episode, since nothing is written twice. Command interpretation by the LLM
  keeps its per-save cap of 12.
- **The offline edition is the shared world** as written so far, not one visitor's slice.
- **Attribution.** Each row records the playthrough that wrote it.

Verified with two separate sessions on Wolf Hall: the second visitor, frozen, replayed the first
visitor's passages with no new rows. The record-change, budget, frozen and export paths are
covered by tests. 113 tests pass.

Limits of the store:

- Two visitors asking for the same unwritten LLM passage at the same moment can both pay for it.
  The first row stands and the second is discarded. A per-slot lease would prevent that.
- The projected world is cached per process. After a reimport, every web worker must restart
  before the new fingerprints apply everywhere; a stale worker would keep serving retired passages.
- Learned LLM command phrasings are still saved per visitor, not per world.
- Local-author passages are stored too, though they could be recomputed. Storing them keeps one
  path for both backends and makes the offline edition complete.

## Grounding check and retiring passages (added 2026-10-08)

Auto-accept now sits behind a check, and any shared passage can be retired.

**The grounding check** runs on every LLM passage before it joins the world. A paraphrase may
reword its packet; it may not add to it. The check is lexical and flags:

- a capitalised name, mid-sentence, that the packet doesn't contain;
- interpretive vocabulary such as "symbol", "foreshadow" or "testament", unless the record itself
  already uses it;
- numbers the packet doesn't contain;
- a single-word name used as a common noun ("a patch" for Wolsey's mule), unless the record does
  the same;
- drift: fewer than 70% of the passage's content words sharing a five-letter stem with the packet.

A refused passage is stored already retired, with its reasons, for review. The visitor gets the
local author's verbatim record and a line saying why. Each slot gets two LLM attempts per version
of its record (`ADVENTURE_LLM_ATTEMPTS_PER_SLOT`); after that the record serves the slot until it
changes, so a hard slot cannot drain the world budget. Refused attempts count against that budget.

Calibration, all against real data:

| Passage | Result |
| --- | --- |
| Four faithful live Wolf Hall passages from earlier in the day | All pass |
| The Esher `look` that leaked later events | Refused on five counts: invented names, "symbol", Patch as a common noun, drift |
| The Wolsey passage ending "a testament to his ruin" | Passes: that wording is the record's own |
| A Dracula-style invented leather cover | Refused: an invented place name and drift |
| Every local verbatim passage in Wolf Hall E1 | 701 of 731 pass. The 30 others are the engine's stock line for an empty record, and local passages are never checked |
| Five new live Happy Valley passages | All accepted; all read as faithful |

What it cannot catch: invented detail phrased in the record's own words, and misattribution, such
as giving one person's action to another. It checks vocabulary, not meaning. Those cases need the
retire command, or a model-based check later.

**Retiring.** `python manage.py retire_passage <world> …` lists passages (`--list`, `--grep`,
`--retired`), retires one by key or row id, or sweeps live LLM passages through the grounding
check (`--check`). Nothing changes without `--apply`. A retired passage stays as history and
stops serving anyone; the next visitor to ask writes a fresh one. Uniqueness now applies only to
live rows, so a retired slot can be rewritten. Retiring a local passage is allowed but warns that
the rewrite will be identical unless the record has changed.

## Live narrator sample (six OpenRouter calls, capped at six in advance)

Five passages at moments 1 and 24 were planned; a sixth call confirmed the encoding fix. Cost was
not checked against the OpenRouter dashboard. Observational packets paraphrased
faithfully: `watch` and `examine Cromwell` at moment 1 added nothing and dropped the analysis.
Two defects surfaced and were fixed before the confirmation call:

- `look` at Esher reproduced `Location.description` including later events. The field is now
  excluded from narrated packets (finding 5).
- Curly apostrophes came back as mojibake ("stormâs"). Cause: OpenRouter streams
  `text/event-stream` without a charset and `requests` guesses ISO-8859-1. Fixed in
  `chat/llm.py` by forcing UTF-8; this also affected Ask the Archive.

The LLM rendered "Patch" as "a patch", which is finding 7 reaching the player.

## Known limits of this experiment

- The offline edition compiles one state per moment, so its journal shows only the exported
  position and its "moments reached" counter stays at 0. Online play is complete. The download
  was checked for content and JS syntax only; it was **not browser-tested** on this world (the
  Playwright setup from September is gone from /tmp).
- The world is cached per process; a reimport needs a server restart.
- Learned LLM parser aliases are scoped per world (Dracula's are per scene).
- Only `live` pages are read. Snippet locations have no live flag and are read whenever an event links them.
- No reveal boundary: `go to` can reach the episode's last moment from its first.

## Suggested next steps

- Shrink the offline edition by sharing repeated blocks across states.
- Decide whether position should stay "moment" or become "room at a moment" with idle narration.
- File the identity splits (finding 3) and the object/character misclass (finding 7) upstream
  once the graph can be queried, with `properties()` evidence as the journal requires.
- Unfamiliar-reader play on this world, rather than the authored Dracula scene, is now the more
  informative test of engagement, since this is the mechanism the concept actually describes.
