# Fabula chat: experience direction and launch readiness

Date: 2026-09-05. Status: working plan; experience details remain proposals.

Implementation update, 2026-09-06: a local terminal prototype now exists.
See [runbook and verified scope](STORY_TERMINAL_PROTOTYPE.md) for the playable
route, saved authoring, offline export, tests and remaining limitations.
The historical chat-readiness assessment below predates this prototype.

Review update, 2026-09-06 (T-040 reopened): GraphRAG remains the showcase
purpose, and the semi-probabilistic, LLM-infused adventure remains the design
exploration. The [revised adapter proposal](GRAPH_TO_GAME_ADAPTER.md) does not
settle agency, generated dialogue or canon-changing play. Its previous claim to
be authoritative and to exclude those options is withdrawn. Begin with the
[forked paper playtest](DRACULA_PAPER_PLAYTEST.md) with three unfamiliar readers.
Its gate requires an unscripted YAML-supported request, an independently reached
early hypothesis, and an observable DO/LOOK direction. Michael/assistant rehearsals
do not count as discovery sessions. An authored pilot proving engaging remains
the gate before procedural generation or Stage 2 construction.

## Direction from Michael

Ground the experience in the fictional world it serves. A generic chat
invitation risks eliciting production trivia such as “Who starred in…”.
Invite exploratory input instead; Michael suggested framing an episode
like an Infocom adventure game.

Further direction: nested locations should seed geography; ordered events
at those locations should support exploratory chronology. Characters,
dialogue, intentions and object interactions come from event data. The
experience needs an ongoing motivation to interact, rather than requiring
visitors to invent disconnected questions. Tool-backed turns and latency
masking are design considerations.

Michael also proposed written or GitHub-sourced Twine-like middleware for
persistent world state, with generated descriptions saved for navigation.
The emerging concept is a semi-probabilistic, LLM-infused text adventure
grounded in the world-model graph. This broadens the design exploration;
the limits on generated world details and canon-changing actions remain
undecided, rather than permanently excluded by the observer-first pilot.

The supplied terminal concept art further establishes an embedded webpage
component, with a command prompt and transcript, and illustrates inhabiting
Jonathan Harker's viewpoint in Dracula S1E1. This supersedes the earlier
observer-first recommendation as the leading design direction. The final
pilot, freedom to alter events, and generated-dialogue policy remain open.

## Proposed experience: enter the episode

Working entry label: **Enter the story**. Supporting copy:
“Explore this episode. Follow its characters, examine what matters, and
discover how its events connect.”

Start at an episode's opening event, or the event page the visitor is
already viewing. Establish the location, people present, and immediate
situation using retrieved event data. Offer three grounded actions beside
an open text input. Accept natural language as well as short commands.

| Input | Behaviour |
| --- | --- |
| Look around | Describe the recorded setting and who or what is present at this event. |
| Examine [object] | Retrieve that object's involvement and recorded state at this moment. |
| Follow [character] | Move to their next recorded event within the chosen episode and reveal boundary. |
| What does [character] want? | Explain event-specific goals and beliefs, attributing interpretation appropriately. |
| How did we get here? | Trace available earlier events and causal connections. |
| Continue / go back | Move through the episode's recorded presentation order. |
| Show the evidence | Open supporting event, entity, and connection pages. |

The leading direction is now an embodied viewpoint: a visitor explores
through an established character, with commands such as asking, telling,
remembering and examining. Selecting a character viewpoint does not itself
decide whether actions can change canonical outcomes. For the first pilot,
author the allowed interactions and their supported effects explicitly.
Distinguish stepping to another recorded scene from physical movement;
define any generated dialogue or supplemental world detail under the
separate playthrough policy below.

Use a scene-setting narrator; keep machinery and connection taxonomy in
optional evidence details. The original “proud provenance” principle still
applies, but a graph-count welcome would break the proposed entrance into
the fiction. For cast/crew questions, briefly explain that this experience
explores the story; offer verified production information only if supported
and explicitly requested. Never improvise performer facts from memory.

## Decisions to settle

1. How much agency does the embodied viewpoint permit? Character-centred
   exploration and canon-changing simulation are separate choices. Start
   with an authored set of interactions tied to recorded discoveries.
2. Reveal policy: progressive discovery from the current moment, or free
   exploration of a completed episode? Recommend progressive discovery with
   an explicit full-episode option. Entering a later event establishes a
   later starting boundary; episode-page summaries may already contain spoilers.
3. Viewpoint knowledge: distinguish what the character knows or remembers
   from what the player has discovered. Do not expose another character's
   private intentions without a supported interaction or narrated reveal.
4. Pilot episode and final public name. The supplied art proposes Dracula
   S1E1, Jonathan Harker and the convent interview. Audit that sequence as
   the leading candidate; Wolf Hall was the older architecture proposal.
5. Model and spend budget, then placement beyond episode/event pages.

## Terminal component: supplied visual reference

Reference: Michael's concept art attached on 2026-09-05, showing the Fabula
marketing page with an embedded Dracula terminal. The image establishes
visual and interaction intent; its dialogue and narrative claims are not
independently verified source material.

Preserve the cream editorial page and its large serif typography around a
wide, dark, monospaced playable region. Within it: muted session/scenario
header, contrasting current-location strip, warm white narration, amber
commands and prompt, green discovery announcements with explicit text
labels. Keep the rectangular, restrained terminal treatment. Render the
interface as selectable semantic HTML with a real input.

The component has one chronological transcript and one active prompt.
The visitor submits `look`, `tell agatha about mina`, or natural-language
equivalents. Echo the command immediately, append the response, then any
new discovery. Restore that exact transcript with the saved playthrough.
The scenario controls a suggested first command and context-specific help
so newcomers need not know adventure-game syntax.

Proposed command families:

- Observation: look, examine, listen, remember.
- Conversation: ask [person] about [topic], tell [person] about [topic].
- Navigation: supported place/scene choices, follow [person], revisit.
- Orientation: help, journal, map, evidence.

Conversation actions require present participants and valid topics at this
moment. `tell` additionally checks what the player-character can know.
The scenario can use recollection to enter an earlier recorded event,
clearly marking the memory and its return point. Exact source quotations
and generated paraphrases must remain distinguishable in evidence details.

Discovery announcements are the principal reward: expose a supported new
relationship or resolve an uncertainty, then record it in the journal.
The mockup's numerical score can represent unique discoveries if an authored
scoring rule is useful. Repeated commands do not farm points; help and
failed input do not incur penalties. Move count is descriptive, and no
time pressure is implied unless a scenario deliberately implements it.

Usability requirements: Enter submits; optional Up/Down history only while
the prompt has focus and without breaking text editing; normal Tab focus;
an accessible submit control for touch users; readable mobile text and
wrapping; no focus or scroll capture on page load. Announce complete
response blocks to assistive technology instead of every streamed token.
Respect reduced motion for the cursor and omit artificial typewriter delay.
Preserve reading position when the user scrolls back through the transcript.

Show pending/saved/retry states truthfully. Leave the typed command intact
on failure; retry the same turn safely. Restart is separate from `look`
and starts a fresh run deliberately. A dedicated play page can expand the
same component and resume the same server-side playthrough. The displayed
`fabula://play/...` in the artwork is decorative; actual navigation uses
normal web URLs.

First playable demonstration: the convent interview, a short authored
investigation, one meaningful recollection or scene transition, and a
return that preserves previous discoveries. Verify the script/event data
before adopting the artwork's precise lines or its proposed conclusion.

## Exploration structure and motivation

Treat the experience as places visited at particular story moments. A
location contains other locations; each has a sequence of recorded events.
The same room revisited later may have different people, objects and
atmosphere. Maintain separate current-event, selected-location, visited
evidence and reveal-boundary state. Looking around does not advance time;
following a person or continuing to another event explicitly does.

`Location.parent_location` supplies containment, not physical adjacency,
compass directions or evidence of a traversable doorway. Use nested place
navigation and explicit scene transitions until actual routes are verified.
Likewise, episode/scene/event ordering is presentation order, not a global
physical clock. `is_flashback` exists; do not infer simultaneity or let a
visit to another room silently combine people from different events.

Give a pilot a short, editorially selected **investigation thread**:
an uncertainty the episode genuinely supplies evidence for. Possible
patterns include tracing an object's changing significance, understanding
why a character changes allegiance, or reconciling two characters' accounts.
These are templates, not claims that a particular episode contains them.

The proposed loop is:

1. Establish a concrete situation and a question worth pursuing.
2. Offer two or three meaningful leads grounded in visible evidence.
3. Let the visitor inspect, follow, revisit or ask freely.
4. Record the new finding and how it changes the current question.
5. Offer the next supported lead, or resolve the thread with its evidence.

A small journal tracks the active question, discoveries and unresolved
leads. Revisiting remains possible; discoveries are not mechanically
withheld behind a mandatory sequence. A direct question can take a supported
shortcut. Label substantive hypotheses as interpretations, accept ambiguity,
and give the thread closure before offering another. Measure progress toward
understanding and voluntary further exploration, not raw turn count.

Initially curate one short route through one episode, with optional side
branches. A Wagtail-managed exploration record can hold an opening question,
starting event, source-linked leads, reveal conditions, supported resolution
and fallback actions. Keep those references attached to canonical records;
refresh or invalidate derived material when those records change. Procedural
generation of adventures can follow once an authored pilot proves engaging.

## Tool-backed turns and latency

Every input that reads or changes the fictional world must pass through a
server-owned action resolver and retrieve an authorised scene evidence
packet. Do not rely on the model voluntarily choosing to retrieve. Help,
UI controls and clarification can use deterministic responses without an
LLM or unnecessary database work.

Suggested action vocabulary: look, inspect, follow, move_to_scene,
revisit, ask_about, show_evidence. These are proposed application actions,
not existing tools. A clicked action already supplies a validated action
type and entity reference. Free text may use a bounded model call to map
onto these actions; the server validates targets and transitions before
changing state. Unrecognised or ambiguous actions preserve state and offer
grounded alternatives. A repeat request must not advance twice.

The common path retrieves the scene packet directly, then makes one
streamed narration call. Natural-language interpretation may add a call;
measure that cost before choosing a combined model/tool protocol. Retain
the existing bounded loop for genuinely multi-step questions, rather than
requiring multiple retrieval decisions for a simple “look”.

Show acknowledged input, the current location/time marker and a truthful
transition indicator immediately. Reuse precomputed or cached scene
openings and authorised action lists; prefetch only reveal-permitted data.
Stream richer narration when ready. Never fabricate ambient story events
as a loading animation. Cache keys must include source revision, scene,
viewpoint/reveal policy and relevant state. Cancel stale responses and
prevent an earlier response from overwriting a newer scene.

## Evidence quality for immersive narration

Verified schema support in `narrative/models.py`: `Location.parent_location`,
`EventPage.scene_sequence` / `sequence_in_scene` / `is_flashback` /
`key_dialogue`, `EventParticipation.goals` / `beliefs` / `observed_status`,
`ObjectInvolvement.status_before_event` / `status_after_event`, and
`LocationInvolvement` atmosphere and environmental fields. Schema presence
does not establish coverage or accuracy for the selected episode.

The inspected Wolf Hall S1E1 export contains these event-level payloads,
but its opening-event description also discusses later developments and
its participation fields contain analytical interpretation. Event-level
filtering therefore cannot by itself establish a safe current-moment view.
Curate the pilot's observable scene descriptions, dialogue and clues against
available source evidence; exclude retrospective commentary. Keep character
interiority distinct from observation and verify each interpretation before
using it as a discovery condition. `key_dialogue` is a set of excerpts,
not a complete conversation or a licence to generate canonical replies.

## Persistent runtime and generated passages

Recommendation: Django/PostgreSQL owns the authoritative playthrough.
Wagtail supplies editorial scenario configuration and review. A narrative
runtime may help author and present branching flow, but should not become
a second independent authority for player progress or graph permissions.

Persist four distinct kinds of information:

| Layer | Contents |
| --- | --- |
| Source world | Versioned canonical entities, event order, relationships and evidence references. |
| Playthrough | Current place/moment, investigation progress, discoveries, visited events and permitted actions. |
| Generated passages | Accepted narration, evidence references, state/reveal context and generation metadata. |
| Turn history | Validated actions, resulting state changes and references to the actual passages shown. |

If the eventual design allows invented interactions or ambient details,
store them in an explicitly separate per-playthrough fictional layer.
They must not modify canonical records or later appear as source evidence.
For the pilot, vary narration and selection among supported leads; invention
that changes objects, access, dialogue or outcomes needs a deliberate policy.

**Generate, accept, persist, reuse.** Visiting the same place at the same
moment with the same relevant discovery state retrieves the accepted
passage. A later event, changed viewpoint or newly relevant discovery may
justify another passage; preserve the original in the visit history.
Any allowed generated detail the player can act on needs a structured
record and stable identity. Do not derive navigable exits or inventory
merely by reparsing descriptive prose.

Suggested records for a bounded pilot: ExplorationScenario, Playthrough,
Turn, GeneratedPassage. A scenario has a published revision; a playthrough
pins that revision and the relevant source snapshot/version. JSON state
can hold small discovery sets initially while canonical entities retain
their normal foreign keys. Save actual accepted generated output and
sampled choices; a random seed alone cannot reproduce remote LLM output.

Use a server-issued session handle for anonymous saves. Browser storage
can cache presentation but cannot supply trusted progress or evidence.
Cross-device saves/account association and retention are separate product
decisions. Two tabs and retried requests need turn identifiers and state
version checks so one action cannot be applied twice.

A turn reads an authoritative state version, validates the action, resolves
evidence and prepares the resulting state. Generate outside long-running
database locks. Commit the accepted passage and its state change together
only if the expected state version still matches. Return a committed turn
ID so a reconnect can retrieve it. For initial navigation, prefer prepared
passages or a short buffer before display; streamed drafts must not activate
exits or discoveries until committed. A failed generation must not leave
the visitor advanced into an unseen scene. Reusing a committed passage
does not incur another model call.

## Middleware candidates checked on 2026-09-05

This is a documentation-level shortlist, not an integration benchmark.

- [Ink](https://github.com/inkle/ink) is an interactive narrative scripting
  language; its runtime supports variables, choices, external functions and
  [JSON state saving/loading](https://github.com/inkle/ink/blob/master/Documentation/RunningYourInk.md).
  [inkjs](https://github.com/y-lohse/inkjs) runs in browsers and Node.js.
  Candidate for authored investigation flow if branching scripts become
  substantial. Using it as the authoritative server runtime would introduce
  a JavaScript execution boundary to this Python deployment; evaluate that
  explicitly rather than duplicating its state machine in Django.
- [Chapbook](https://github.com/klembot/chapbook) is a Twine 2 browser story
  format with separate state, passage display and extension mechanisms.
  Candidate for prototyping the reading/navigation experience.
- [SugarCube](https://github.com/tmedwards/sugarcube-2) is another Twine/Twee
  story format to assess if a Twine authoring workflow is preferred.

Provisional build choice: a small Django action/state service with
Wagtail-authored scenario records and the existing browser interface
adapted for passage navigation. Borrow interaction and save-history ideas;
adopt Ink or a Twine format when a concrete pilot shows it removes more
work than its integration introduces. No dependency was installed or
runtime selected irrevocably in this planning session.

## Source map and historical decisions

- [Original architecture brief](CHAT_INTERACTIVITY_ARCHITECTURE_BRIEF.md),
  2026-07-16: prior-art analysis, grounding, spoiler model, phased build,
  and §6 explicitly open persona/name, spoiler default, budget, ORM/Kuzu,
  and catalog versus marketing placement.
- [Implementation note](CHAT_IMPLEMENTATION.md), 2026-07-25: ORM-only MVP,
  11 tools, streaming widget, full-canon mode; evaluation gate unfinished.
  “What shipped” in this document does not establish production deployment.
- Sister-project feedback:
  `../../bizgov-graph/docs/ask-guv-architecture-review-fabula-2026-07-17.md`.
- Reusable conversation guidance:
  `../../bizgov-graph/docs/guvnor-chat-behaviors.md`.
- Reusable evaluation design:
  `../../bizgov-graph/docs/ask-guv-chat-eval-gate.md`.

The existing code adopts “Ask the Archive” / “the Archivist”, full-canon
access and catalog placement. These are implementation defaults; no
explicit final persona approval was found in the inspected records.

## Verified implementation and deployment state

- `chat/` implements fixed ORM retrieval tools, a bounded eight-iteration
  loop, empty-result exit, deduplication, fixed fallback, OpenRouter
  transport, SSE endpoint, citation cards, chips, and payload size caps.
- `templates/chat/widget.html` and `static/chat/` provide the widget;
  `templates/base.html` mounts it. Settings and root URLs are wired locally.
- All **43 existing chat tests passed** on 2026-09-05 using the local
  `fabula_wagtail` conda environment and a temporary PostgreSQL test DB.
  These tests use scripted responses; no live-model quality evaluation ran.
- Git lists the chat app, assets, templates and both earlier chat documents
  as untracked; wiring files also have local modifications. Preserve other
  working-tree changes when preparing the implementation for deployment.
- Railway CLI reaches project `fabula-web`, with the web service reporting
  SUCCESS. Public `GET /api/chat/suggestions/` returned **404** on this date.
  Local code would return JSON even when disabled. Treat this as evidence
  the planned route is unavailable, not proof of the precise deployed revision.
- No production configuration or deployment was changed in this review.
  Production API-key presence, provider spend cap and model availability
  have not been verified.

## Work required for this experience

1. Build a server-validated exploration state: series, episode, current
   event, reveal boundary and visited events. Current browser state stores
   conversation history per series; it has no exploration cursor.
2. Add an event-scoped retrieval tool exposing participants, objects,
   locations, goals and beliefs, plus deterministic next/previous navigation.
   The data models contain these relationships, but existing tools do not
   expose them as a complete current-scene view; objects are absent from
   `resolve_entity`, and `character_timeline` omits beliefs.
3. Apply the reveal boundary to every retrieval path and response chip.
   An episode-only ordinal ceiling is insufficient for discovering an
   episode progressively: use event order within it. Whole-episode summaries,
   global character descriptions, future connection endpoints and arc titles
   can reveal later events and need exclusion or scoped alternatives.
   Retrieval filtering still needs tests for leakage from model memory.
4. Replace the existing episode chips, including “Who wrote it?”, with
   actions grounded in the current event. Establish narration and evidence
   presentation without implying simulated freedom the graph cannot support.
5. Close the documented grounding gaps: **ISS-027**, unsigned client
   context promoted to trusted prompt evidence; **ISS-028**, unused prose
   URL allowlist. Neither was fixed during this planning review.
6. Build evaluations using the production loop: grounded exploration,
   scene navigation, invented actions/objects, missing data, ambiguous names,
   out-of-world trivia, forged context and spoiler leakage. Set acceptance
   thresholds before the model run; missing or failed evaluation blocks launch.
7. Verify proxy-aware rate limiting and concurrent counters, provider spend
   limits, measured turn latency/cost and a controlled enable/disable path.
   Key presence currently enables chat automatically; separate deployment
   from exposure with an explicit release flag. Account for cached pages.
8. Package the selected changes, run a real-model pilot and browser checks,
   then deploy and verify the route, navigation, evidence links, error states
   and disable path. Keep keys server-side and record actual deployment evidence.

The Django/Wagtail/Railway foundation is available. The immediate design work
is the exploration contract and the scene-level retrieval/state it requires;
Kuzu, vector search and branching simulation are not prerequisites for a
small, well-grounded pilot.


## 6 September 2026: Infocom-informed object loop (T-038)

The prototype now persists containment, manuscript possession and reading,
separates inventory from the journal, and saves accepted parser aliases alongside
written passages. It remains a two-scene investigation with seven bounded prose
slots. The standalone compiler includes the physical rules. The manuscript
substitution reported in ISS-029 is fixed.

[Research findings and the next authoring boundary](INFOCOM_DESIGN_NOTES.md)
distinguish compact geography from puzzle dependencies. The next expansion should
propose behavior definitions with validated references/preconditions/effects and
an achievable scene goal; arbitrary LLM-authored rules are not implemented.
See [prototype verification](STORY_TERMINAL_PROTOTYPE.md#t-038-verification).
