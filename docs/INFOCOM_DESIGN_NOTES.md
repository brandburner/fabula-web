# Compact worlds, changing situations

Research and prototype iteration, 6 September 2026, T-038 / ISS-029.

The HHGTTG map supplied in the playtest suggests a useful direction for Fabula:
start with a compact geography and make its objects, people and circumstances
worth revisiting. Room count alone is a poor measure of playable depth.

Review update (T-040 reopened): the [adapter proposal](GRAPH_TO_GAME_ADAPTER.md)
and [paper pilot](DRACULA_PAPER_PLAYTEST.md) reopen the product decision. Generated
dialogue, object behavior and alternate outcomes remain undecided; the observer-only
restriction in the prior design was not adopted. Keep graph provenance separate
from any fictional overlay and prove the authored pilot engaging before broader
generation. These Infocom findings inform that test rather than settle its stance.

## Material examined

All sources below are in the user's local Infocom collection; no game binaries,
scans or manuscript pages have been copied into this repository.

- [HHGTTG solution](</Volumes/Extreme SSD/Dropbox (Personal)/Infocom Collection/The Hitchhikers Guide To The Galaxy (1985)/Manual/THHGttG Solution.txt>): a walkthrough credited to Doug Howell, with additions from Peter van Turennout dated 11 July 1990. This is player documentation, not an original design specification. The Vogon Hold sequence arranges a gown, towel, satchel and junk mail; later sequences revisit circumstances through different characters and collect objects for subsequent tasks. The walkthrough describes short scenarios arriving in random order and dependencies between their results. It supports the observation that much of the game lies in relationships and state rather than additional rooms. It does not establish an exact room count.
- [Zork I manual](</Volumes/Extreme SSD/Dropbox (Personal)/Infocom Collection/Zork 1 - The Great Underground Empire (1981)/Manual/Zork 1.pdf>), printed *Instruction Manual* pp. 14–16, 18 and 20: direct and indirect objects, ambiguity questions, containers, separate inventory, saving, and distinct parser complaints. The introductory mailbox/leaflet exercise includes implicit taking when reading. Page 15 also explicitly distinguishes descriptive scenery from recognized interactive nouns: even Infocom did not implement everything it mentioned.
- [Down From the Top of Its Game: The Story of Infocom, Inc.](</Volumes/Extreme SSD/Dropbox (Personal)/Infocom Collection/The Story of Infocom - paper.pdf>), Briceno et al., 15 December 2000, printed pp. 16–18: retrospective discussion of implementation, puzzle outcomes and testing, including a reproduction of Stu Galley's Implementor's Creed. This is secondary historical material, not a technical engine manual.
- [HHGTTG gallery PDF](</Volumes/Extreme SSD/Dropbox (Personal)/Infocom Collection/The Hitchhikers Guide To The Galaxy (1985)/Manual/hitchhike.pdf>): inspected its extracted text and the demolition-order scan on PDF page 7. This file is chiefly packaging/feelies, despite its Manual directory. It is useful as an example of world framing; it was not treated as a parser specification.

## Design implications for Fabula

| Observation | Application |
| --- | --- |
| Objects are related to other objects. | Persist containment and possession separately from prose. A closed bag changes which interactions can succeed. |
| A return visit can involve different knowledge or circumstances. | The playable position includes location, event/memory context, discoveries and physical flags. Nested location data supplies geography; event order alone does not supply puzzle dependencies or walkable exits. |
| Commands distinguish intentions and referents. | Preserve `verb + target`; report a blocked action without silently performing a different one. Ask for clarification when ambiguity cannot be resolved. |
| Short scenes contribute to later tasks. | Give each scene a question, a useful change and a reason to return. Seed dependencies from events, then author and test a solvable path through them. |
| The interface is part of the experience. | Keep the prompt and suggested actions grounded in what the player is doing. Loading feedback should acknowledge an action without claiming it has succeeded before commit. |
| Some scenery is descriptive. | Prioritize objects that suggest action or bear on the current goal. Do not promise that every generated noun is usable; a proposed interactive object needs an identity and executable behavior before its prose advertises that behavior. |

For this prototype, the motivating question remains how Dracula knew Jonathan's
private memory. The manuscript is now a thing the player can consult and return;
Agatha responds differently after it has been read and after the mirror encounter
has been recalled. This is a small physical/conversational loop inside two scenes.
It does not yet amount to an Infocom-scale puzzle network.

The walkthrough also contains timing constraints and dependencies that can
require replay. Those are not automatically good defaults for an embedded web
experience. This iteration keeps the investigation recoverable and uses no
real-time countdown or irreversible inventory loss.

## Implemented in this iteration

- Three source-seeded children of Agatha's bag: manuscript, wooden stake, hammer.
  Each has persistent examination/detail prose. The manuscript additionally has
  a saved `read` passage, an adapted summary rather than invented screenplay quotations.
- Open/closed bag, manuscript possession and a persistent reading flag. Reading
  implicitly takes the accessible manuscript for consultation. Returning it keeps
  what the player learned. Closing the bag does not hide a manuscript already held.
- Separate inventory and journal. The stake and hammer remain Agatha's tools;
  taking them gives a specific refusal. Reading a hammer does not open the journal.
- Explicit room scoping. Entering the castle is a recollection; it does not
  transport the manuscript into the past.
- Target/verb filtering before optional LLM interpretation, typed allowed action
  descriptors, and saved accepted aliases scoped to the scene. Unsupported verbs,
  unknown targets and closed-container refusals do not need model calls.
- Seven finite prose slots and 80 compiled combinations of scene, discoveries and
  physical flags. The standalone edition uses the same Python transition outputs.
  Learned aliases are revalidated when reused and exported; freeze stops new
  interpretation while retaining accepted phrases.
- Backward-compatible defaults for existing saves. Restart resets physical and
  investigation progress while keeping written passages and learned vocabulary.

The manuscript's identity and role come from the already pinned interview event,
`cand_evt_scene_547a363fb2331333_01`, including its involvement record for
`object_5de8e37e880c`. The broader objects export was also inspected; its retrospective
corruption/revelation material is deliberately excluded from the author context.
Permission to consult/return the manuscript and the bag interaction rules are
editorial adaptations, not claims about exact screenplay actions.

## Where the author boundary remains

The engine owns the rules. The LLM currently fills description, detail and the
readable object's reading passage, and interprets unfamiliar grounded phrasing.
It cannot submit new exits, objects, inventory effects or discoveries in its
accepted schema. Saved prose and accepted aliases become deterministic for that
playthrough, including in the exported HTML.

Prompt instructions are softer than schema/rule checks. Live testing produced
unsupported leather-cover and page details despite instructions to keep sparse
facts sparse. Those details could not change the game state, but they show that
saved prose is not automatically faithful canon. Another live check initially
rejected `peruse manuscript`; the prompt needed an explicit distinction between
valid synonyms and substituting a different action. Strict referent checks remain
in code. Free-language semantic interpretation is not formally proven by them.

The next authoring capability should be **proposals from a small behavior
vocabulary**, for example inspectable, readable, container, portable, or an
interaction gated by a discovered fact. A proposal must include stable IDs,
source references, preconditions, effects and prose for success/blocking; validate
references, reachability, reversibility and the route to the scene goal before
publishing it into the playthrough. Store the accepted definition and its
provenance, then reuse it. Arbitrary generated code and automatic promotion into
the shared source graph are not implemented.
