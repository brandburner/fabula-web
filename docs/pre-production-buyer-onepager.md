# Fabula for Pre-Production — Buyer One-Pager

*Working desk-research artifact (T-004, 2026-05). Tag claims with
[verified] when the user closes an interview that confirms them;
everything else is hypothesis.*

---

## Who buys

Three production roles own budget lines Fabula can plug into.
Ranked by how cleanly the value-prop matches an existing line
item:

1. **Line Producer / UPM** *(primary target)*
   Owns the script-breakdown budget. Today: pays for Movie
   Magic Scheduling licenses, hires a breakdown coordinator for
   ~$1.5–3k/week per show, and absorbs the cost of every missed
   element that cascades into a re-shoot.
   *Fabula angle*: the narrative graph IS a pre-computed
   breakdown — every Event already lists location, participants,
   props (via ObjectInvolvement), and continuity dependencies
   (NarrativeConnection edges).

2. **VFX Supervisor / VFX Producer** *(strongest scope-validation
   match)*
   Owns vendor bidding. Today: assembles shot lists by reading
   scripts + watching reference cuts, then bids to vendor shops
   in Excel. Missing-shot scope is the #1 budget blowout source.
   *Fabula angle*: connection types `THEMATIC_PARALLEL`,
   `SYMBOLIC_PARALLEL`, and `CALLBACK` surface continuity
   requirements the script doesn't make explicit. Pre-computed
   scene-by-scene participant lists eliminate the "did we
   actually see this character in scene 47?" question.

3. **Showrunner / Writers' Room assistant** *(natural fit, not a
   buyer)*
   Most natural product fit — keeps the show bible. But:
   showrunners don't sign cheques for software, and Writers'
   Assistants are below the budget-authority line. Treat this
   persona as a **user influencer**, not a buyer.

## What buyers pay for today

| Need                          | Today's tool                                        | Approx 2026 spend per series |
|-------------------------------|-----------------------------------------------------|------------------------------|
| Script breakdown              | Movie Magic Scheduling + human breakdown coordinator | $40–80k labour, $1–3k tooling |
| VFX bidding                   | Spreadsheet + Frame.io + Excel scope sheets         | $10–25k labour, vendor-side |
| Continuity bible              | Notion / Airtable / custom doc                      | $0–5k tooling, hidden labour |
| Reference / lookbook          | Milanote, Frame.io, Google Drive                    | $1–5k tooling |
| Story planning (writers' room)| Final Draft + whiteboards + Notion                  | $5–10k tooling |

Numbers are desk estimates — flag as `[open]` until user verifies
via interviews.

## Where Fabula slots in

Fabula's narrative graph is a **pre-computed, machine-readable
script breakdown plus continuity validation layer**:

- **Each Event** carries location, participating characters,
  emotional state, objects involved, and scene sequence — the
  raw material of a breakdown sheet.
- **Each NarrativeConnection** is a typed continuity claim
  (CAUSAL, FORESHADOWING, CALLBACK, …) the human breakdown
  coordinator currently has to surface by reading and
  cross-referencing.
- **Each EventParticipation** carries the character's emotional
  state and goals at that beat — useful for VFX scope and shot
  selection, useless for traditional breakdown software.

Concretely: a UPM running Fabula on a script-in-progress gets a
breakdown sheet on day zero of pre-production instead of week
three, and the continuity claims a coordinator would manually
surface are already in the graph as `NarrativeConnection` edges.

A VFX producer gets a scene-by-scene participant + location list
plus the continuity edges that imply implicit shots (e.g. a
SYMBOLIC_PARALLEL connection that requires matching cinematography
in two scenes shot months apart).

## The Netflix signal

Netflix's 2024 AI Breakdown Assistant internal talk publicly
framed automated script breakdown as worth in-house investment at
one of the largest studios on earth. That's competitive
validation: the world's most data-mature studio decided this is a
budget item.

The Fabula pitch lands a fork above that: **buy the capability
instead of building it.** Most independent / mid-market shows
don't have a Netflix-scale internal AI engineering org but they
have the same breakdown problem.

## What this one-pager is NOT

- **Not pricing.** Pricing is a per-show conversation that depends
  on whether the buyer is a studio (Netflix, MGM, A24), a
  production company (Bad Robot, Plan B), or a vendor shop (DNEG,
  WĒTĀ).
- **Not screenshots.** Demo material is downstream of buyer
  validation.
- **Not a sales script.** This is the first-touch artifact a
  warm inbound from `/for-production` should receive — concrete
  enough that the right buyer self-IDs, vague enough that it
  doesn't presume the workflow.

## Open questions for primary research

These are the falsifiable claims the user should pressure-test in
the first 5–10 interviews:

1. Does the **Line Producer / UPM persona** actually sign the
   cheque for breakdown tooling, or does the production company
   own the AP relationship and the UPM just specifies?
2. **VFX bidding budget cycle** — how much of the bid scope
   work happens before vs. after the vendor is selected? If
   most is post-selection, Fabula needs a vendor-side product.
3. What's the **realistic willingness-to-pay** for a per-show
   subscription at the mid-market tier? Anchor against Movie
   Magic Scheduling pricing.
4. How does **Showrunner enthusiasm** translate (or fail to
   translate) into UPM or production-company purchase?
5. What's the **first feature** a buyer would need to see in
   week one to keep using Fabula? (If they say "another
   spreadsheet view of the breakdown", that's a different
   product than the narrative graph pitch.)

Answers feed the next revision of this one-pager; a 2026-09 dated
v2 should replace this draft once 10 interviews are in.

## Related

- `docs/pre-production-interview-guide.md` — the interview guide
  paired with this one-pager.
- `templates/marketing/for_production_page.html` — the current
  marketing copy this one-pager is meant to back up.
- `MEMORY.md` → `feedback_production_framing.md` — the user-memory
  note that drove this ticket's framing.
