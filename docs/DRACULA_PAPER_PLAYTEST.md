# Dracula paper playtest — discovery before construction

Revised 6 September 2026 · **Gate 0 pending: no unfamiliar-reader sessions recorded.**

Test whether a visitor can discover something through Fabula's story records and
wants to act within that world. Run the paper session before building the adapter.
Michael and the assistant can rehearse voice and facilitation; neither supplies
discovery evidence for this gate.

The [packet file](prototypes/dracula-paper-packets.json) contains **23 exact values**
from the February 18, contract v2.3.0 episode YAML: the original 18 plus five for the
fly, nun and crucifix. Every value has a field pointer and SHA-256. These are graph
extractions, including analytical prose and unverified extracted dialogue, not
independently verified screenplay quotations. Player prose below is authored from
those values. Source records, interpretation and invention remain distinct.

## Session protocol and decision

Use **three unfamiliar readers**, separately, with the same dramatic presentation
(Voice B). They must not have seen the prototype, packets or this scene's reveal.
Screen prior familiarity before showing the opening. Record prior knowledge; a
reader who already knows the answer can assess voice but cannot fill a discovery
session. Do not replace readers because they stop early or fail to infer the answer.

Allow up to 20 minutes per reader and 10 minutes for debrief. Cap facilitator source
review at 45 minutes over these 23 values; record actual time. No episode-wide
claim extraction or review. The full episode remains available for bounded manual
lookups of unexpected requests. Log lookup time separately. A second voice and any
invented-dialogue variant belong **after** measured play, so they cannot supply the
answer or influence the action count.

Give only the opening, then respond to commands. Keep response tables, metrics and
future packets out of the reader's sight. “What do you do?” is the neutral prompt.
Do not ask for a hypothesis, hint that blood carries memories, or require readers
to visit every lead. Offer specific suggestions only if asked or stalled; mark
the following command as suggested. Accept ordinary paraphrases. Log the first
hypothesis before giving the response that confirms or contradicts it.

These are small-pilot decision rules, fixed before testing, not statistical claims:

| Signal | Observable record | Pass/decision rule for three sessions |
| --- | --- | --- |
| U — unscripted breadth | A reader's new intent, absent from the response sheet, answered by a previously unselected YAML field. Log exact pointer, raw-value hash, answer and time. A synonym of an existing response does not qualify. | At least one reader does this without a specific suggestion. This establishes that the source offers more than the prepared script. |
| H — early hypothesis | Reader independently proposes that Dracula learned the private memory through blood, before packet 3 or any other response discloses that mechanism. A tentative question qualifies; saying “blood” alone does not. | At least one reader reaches it. Record the route, supporting clues and disclosure turn, including failed/assisted cases. |
| A — requested agency | Per reader, count unsolicited first requests to **DO** versus **LOOK**, including unsupported actions. | At least four eligible commands per reader. If DO > LOOK for at least two readers, the next paper experiment includes consequential actions. If LOOK > DO for at least two, it develops grounded exploration. Otherwise agency is inconclusive. |

DO means an intended change: take, use, comfort, persuade, tell someone something,
protect someone, or alter an outcome. LOOK means acquiring information: inspect,
read, ask for existing facts, recall or navigate to another recorded moment.
Code intent rather than the verb: “ask her to leave” is DO. Record standalone
hypotheses separately, outside A. Exclude help, meta commands, suggested commands,
and repeated attempts at the same intent. Split compound commands only when intents
are clearly separable; otherwise mark ambiguous and exclude from A. Keep raw text
so the coding can be checked. Reader requests count even when the paper cannot
execute them; a refusal must not erase evidence for agency.

**Gate verdict:** U and H passing plus a clear A direction advances to source
verification and a small prototype brief for that direction. This authorizes the
next scoped design step; it does not decide a permanent canon/dialogue policy or
start procedural generation. If U fails, expand the searchable evidence or the
opportunity to explore. If H fails, revise the clue sequence. If A is inconclusive,
revise the agency experiment. Then test with a new unfamiliar cohort before
construction. A second failed round stops this version of the framing for redesign.

Record first lead, lead switching, dead-end recovery and voluntary stopping too.
These diagnose failures: a reader exhausting a tiny scene has not demonstrated
that grounded exploration in general is dull. A pass demonstrates initial breadth,
discovery and an agency direction; repeat play and sustained enjoyment still need
validation in the working prototype. Producing this document cannot pass Gate 0.

## Opening — show the reader

> You are Jonathan Harker. You have escaped Castle Dracula.
> The Count knew a thought about Mina that you had never shared.
> Find out how he knew.
>
> CONVENT ROOM
>
> Sunlight crosses the room. A fly buzzes close to your face.
> A silent nun watches you. Beside Agatha, a bag stands open on the table.
> A crucifix hangs on the wall.
>
> What do you do?

Basis: `interview.room`, `interview.fly_sound`, `interview.fly_on_harker`,
`interview.nun_reaction`, `interview.bag`, `interview.crucifix`; the private thought
is supported by `bedroom.harker` and `return.private_memory`. Escape and the task
are the authored framing premise. Before/after object fields are not a shared
clock; this is a selected presentation of the recorded interview.

## Packet 1 — two leads and a bounded dead end

Event: `cand_evt_scene_547a363fb2331333_01`. Start on either lead, switch or revisit
freely, or go straight to the bedroom. Neither lead is a key required to unlock
packet 2. They answer different questions and leave different findings in the
reader's notes; they are not two labels for the same response.

| Lead / request (facilitator only) | Player response | Evidence / branch consequence |
| --- | --- | --- |
| **Nun → fly:** watch the nun | “Her eyes turn away. She says nothing. When the fly crawls across your face and into your eye, she shows visible horror.” | `interview.nun_reaction`. Reveals what she reacts to; the fly is a followable lead. |
| Follow the fly / notice your own reaction | “You track the fly without blinking. Her horror has no counterpart in your eerie calm.” | `interview.fly_on_harker`, `interview.nun_reaction`. Finding: the mismatch between your reaction and hers. Does not prove you are undead. |
| Why is the nun here? | “She is here as chaperone. She is distressed, but stays silent.” | `interview.nun_role`, `interview.nun_reaction`. Ends this local inquiry; reader can pursue Agatha or the memory. |
| **Bag → intention:** examine the bag, hammer or stake | “Agatha's bag contains a wooden stake and a hammer. She has brought more than the means to take down your story.” | `interview.bag`, `interview.stake`, `interview.hammer`. Reveals the tools; Agatha's purpose is a separate follow-up. |
| What does Agatha want / why the tools? | “She wants the full truth of your time with Dracula. She is also trying to establish whether you are still human.” | `interview.agatha_goal`, `interview.agatha_assessment`. Finding: your examiner is assessing you as well as your account. Paraphrase of attributed goals, not invented dialogue. |
| **Dead end:** inspect the crucifix | “The crucifix hangs on the wall, untouched. There is no further clue here in the available record.” | `interview.crucifix`. Bounded source-coverage dead end. Do not infer that crosses are powerless, invent a reaction or hide a key behind it. Reader can return to either lead. |
| Recall / think about the castle bedroom; tell Agatha about Mina | Show packet 2. | Editorial transition, not a NarrativeConnection edge. A telling intent counts as DO even though this paper route only supplies the recorded recollection. |
| Read the manuscript, if independently requested | “Your account lies open for Agatha's interview. The record supplies no passage from its pages to read.” | `interview.manuscript`. Log the coverage failure. Never advertise this as the first interaction or invent readable contents. |

Do not print branch labels, findings or evidence IDs in the reader's opening.
If asked for a hint, mention the nun, bag or castle memory; log the suggestion.
The crucifix is visible so readers can discover the dead end naturally. Do not
force a detour for the sake of the test.

**Identity limit (UP-008):** bag, stake and hammer share `object_24bccae12e12`.
Their distinct row descriptions support noun-specific views, not three verified
entities. A request to take/use a tool is valuable DO evidence. Log it, explain
briefly that its consequence is not written in this paper test, and let the reader
continue or stop. Do not present that implementation limit as a permanent refusal
policy. Ask about intended consequences in the debrief, after counting is complete.

## Packet 2 — the bedroom recalled

Event: `cand_evt_scene_fbdfed5d901968f6_03`.

> CASTLE BEDROOM · RECALLED
>
> Mina's photograph is on the dresser. The shaving mirror lies broken.
> The Count knew how you remembered her hair in sunlight.
> You had never shared that thought.
>
> What do you do?

Basis: `bedroom.photograph`, `bedroom.mirror`, `bedroom.mina_memory`,
`bedroom.harker`. Let the reader make the photograph/mirror comparison. Do not
front-load blood or suggest its mechanism. The mirror's recorded aftermath is not
an action the reader performed and does not establish a generic event phase.

| Request | Player response | Basis |
| --- | --- | --- |
| Examine photograph | “You placed the photograph on the dresser. The private thought the Count described was one you had never shared aloud.” | `bedroom.photograph`, `bedroom.harker`. Juxtaposition, not an asserted photograph→blood edge. |
| Examine mirror | “The Count shattered the glass. A fragment cut your thumb. His attention fixed on your blood.” | `bedroom.mirror`. Concrete action selected from analytical description. |
| Recall his words | “He spoke of your memory of Mina's hair in sunlight. He also said: blood is lives.” | `bedroom.mina_memory`, `bedroom.blood_words`; extracted dialogue remains unverified. |
| He learned it through my blood / could my blood carry the memory? | Log H **before** responding, then show packet 3. | Independent mechanism, if no answer disclosure or leading hint preceded it. |
| Ask Agatha about blood / return to Agatha / how did he know? | Show packet 3 immediately. | No forced clue sequence. These requests alone are not H. A shortcut is a legitimate outcome. |

**Source defect (UP-009):** `/events/26/participations/1/observed_status` inserts
Agatha's “Lives?” reaction into the castle event, whose `is_flashback` is false.
This fuses the framing interview and recollection. The “event at a place” model
fails here; neither the participation row nor the flag can locate everyone in one
room/time. The explicit recollection label is an authored repair for this paper
presentation, not corrected graph data. Do not place Agatha physically in the
bedroom or invent a second event identity. The [upstream journal](UPSTREAM_ISSUES.md)
and [audit](prototypes/dracula-adapter-data-audit.json) track the defect and required
source verification.

## Packet 3 — the proposed connection

Event: `cand_evt_scene_a4860661882bc3e2_01`. Mark **answer disclosed** when any of
this packet is shown. H can no longer be earned after that turn.

> CONVENT ROOM
>
> Agatha returns to the Count's choice of words: lives, not life.
> Perhaps stories can be read through blood. Perhaps your private memory was
> part of what he took.

Basis: `return.correction`, `return.hypothesis`, `return.private_memory`. Preserve
“perhaps.” The reader has reached Agatha's hypothesis, not proved a supernatural
law or discovered an explicit graph edge.

| Request | Player response |
| --- | --- |
| Is that certain? | “It is the possibility Agatha raises. These records do not independently prove the mechanism.” |
| Evidence | Show the exact `return.hypothesis`, `return.private_memory` and `bedroom.mirror` values and their pointers. Record disclosure if requested earlier. |
| What next? | “You can revisit either interview lead, or leave the account here.” Do not invent another mystery to inflate session length. |

End whenever the reader chooses, or at the time cap. Ask what they had hoped to do
next and where the experience lost or gained their attention. Reaching the last
packet is not by itself engagement evidence.

## Unexpected commands — test the source beyond the sheet

For an unsolicited intent not covered above, the facilitator searches the **actual
episode YAML**, starting with the current event, then the rest of the episode.
Spend at most two minutes per lookup; record timeouts and unsupported requests.
This is a manual retrieval experiment, not a claim that a live adapter exists.

For a supported answer, capture the field's JSON pointer, exact raw value, SHA-256
of its UTF-8 text and the faithful reply. Use the same source file hash as the
packet fixture. Confirm that the field wasn't already selected and the intent
isn't a synonym of a scripted answer before awarding U. New pointers enter the
session log as evidence, never as invented canonical facts. Do not prepare a list
of “unexpected” questions and feed it to the readers.

Dense analysis, conflicting frames and missing identities need honest limits.
Do not resolve a contradiction through invented facts. Do not withhold a supported
answer just to preserve the puzzle: if retrieval exposes the mechanism early, mark
that disclosure and count U if it qualifies, but no later H. Evidence mode may
likewise disclose the answer; log it. Unsupported world-changing requests remain
DO observations and unanswered branches, not evidence that the graph supports them.

## Recording sheet and post-session voice comparison

Use the blank [turn log](prototypes/dracula-paper-session-log.csv). One row per
intent; record the reply as well as the command. Record branch as `nun`, `bag`,
`crucifix`, `bedroom` or `return`. `prompted` means a specific suggestion, not the
neutral “What do you do?” prompt. `answer_disclosed` marks any response exposing
the blood→memory mechanism. No reader results have been entered.

| Reader | Eligible / prior knowledge | First lead / switching | U (pointer) | H (turn, before disclosure) | DO / LOOK / excluded | Stop reason / dead-end recovery |
| --- | --- | --- | --- | --- | --- | --- |
| R1 | Pending | | | | | |
| R2 | Pending | | | | | |
| R3 | Pending | | | | | |

Record preparation minutes: pending. Source lookup minutes: pending.
Gate verdict and next experiment: **pending reader evidence**.

After measured play, show this attributed **Voice A** version of packet 2 for a
writing comparison only:

> The bedroom record places Mina's photograph on your dresser. It describes
> the Count breaking your shaving mirror and the glass cutting your thumb.
> You insist that the memory he describes is one you never shared aloud.

It maintains second person throughout. Any preference after learning the answer
is a voice preference, not a new discovery result. An optional invented line—Agatha:
“Your account tells me what you remember. I need to know what came back.”—must be
labelled new authored dialogue and shown only here. It cannot become source
evidence or settle the wider policy for generated dialogue and changed outcomes.

The earlier assistant walkthrough found the manuscript weak and the photograph /
mirror contrast promising. That was an editorial rehearsal of the previous linear
version. It is not a completed test of this forked version or a substitute for the
three unfamiliar readers now required by Gate 0.
