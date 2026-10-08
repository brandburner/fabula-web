# Chat & Interactivity Architecture Brief — "Ask the Archive"

**Date:** 2026-07-16
**Status:** Proposal for discussion
**Companion:** `docs/STORYLINE_ARCHITECTURE_BRIEF.md` (2026-07-16) — the chat consumes the same imported data that brief specifies
**Prior art analysed:** `/Users/michaelatherton/bizgov-graph` — the "Ask Guv" hybrid-graph LLM chat on Guvnor

---

## 1. Purpose

fabula_wagtail publishes the narrative knowledge graph as a densely-linked but **static** catalog: there is currently no way to interrogate the graph conversationally, no LLM dependency, no JS interactivity beyond navigation (verified: zero chat/htmx/websocket surface in `narrative/` or `marketing/`; `requirements.txt` has no LLM or vector packages). Meanwhile the sister project bizgov-graph has shipped a production LLM chat ("Ask Guv") over its compliance knowledge graph, with a hardened orchestration loop, grounding discipline, and an eval harness — all running on the same Railway + Django + Postgres stack this site uses.

This brief does three things:

1. **Distils the prior art** — what Ask Guv actually is, verified in source, and which parts are load-bearing.
2. **Contrasts the use cases** — compliance Q&A and narrative exploration differ in ways that invert two of Ask Guv's core assumptions.
3. **Sketches the target architecture** — an on-site conversational layer that makes the narrative world come to life, with phasing, guardrails, and eval plan.

---

## 2. Prior art: what Ask Guv actually is

All file references below are into `/Users/michaelatherton/bizgov-graph`. Key facts verified directly in source; the rest from a full code sweep.

### 2.1 The headline: no vectors anywhere

Despite the "hybrid-graph" label, **Ask Guv has no embeddings, no vector store, and no semantic retrieval**. "Hybrid" means: graph traversal (embedded KuzuDB) + relational keyword search (Postgres/Django ORM), both behind a fixed tool set. Synonymy is handled by prompt-level abbreviation tables and hand-tuned keyword scorers (`project/chat/utils.py:3718` — a multi-phase AND/OR scorer with graph-taxonomy boosts). The repo's own notes flag this as the biggest structural gap and the reason the system prompt and eval harness grew so large.

**Fabula starts ahead here**: every canonical entity is already embedded in ChromaDB (per-series collections, OpenAI embeddings — the same vectors the GER dedup detector uses). The chat design below adds the semantic recall layer bizgov lacks.

### 2.2 The retrieval mechanism: fixed function-calling tools, never text-to-Cypher

The LLM chooses from **16 fixed tools** (`project/chat/tools.py`) with OpenAI-style schemas — `lookup_structured_data`, `search_legislation`, `trace_obligation`, `get_compliance_profile`, etc. Each tool executes a **fixed, parameterized Cypher template** server-side (e.g. `_search_provisions_graph`, `utils.py:2265`); the LLM never writes queries. Tool descriptions carry heavy routing intelligence (which tool for which question shape) — prompt engineering lives in the tool docstrings as much as the system prompt.

Each graph tool is **graph-first with an ORM fallback**: if KuzuDB is down or rebuilding, `graph.query()` returns `[]` (never raises) and the tool degrades to a Django-ORM text query. Chat stays up during graph rebuilds, with a "knowledge base limited" notice injected into the prompt.

### 2.3 The deployment answer fabula needs: embedded graph, rebuilt on deploy

Production has **no graph server**. The graph is an **embedded KuzuDB** (SQLite-for-graphs, `kuzu>=0.7.0`), living at `data/compliance_graph`, **rebuilt from PostgreSQL on every Railway deploy** by a backgrounded `deploy_startup` command. Postgres is the source of truth; Kuzu is a derived read model. A generation-token file lets long-lived workers reopen the new graph after a rebuild (`knowledge_graph/kuzu_client.py:152-199`).

This solves fabula_wagtail's central constraint directly: **Neo4j exists only on the local machine** (`narrative/ger_client.py` speaks bolt to localhost — production can never use it). The site's Postgres already holds the imported graph (events, connections, entities, themes/arcs — richer still once the storyline brief's v2.4.0 import lands); a `sync_narrative_graph` command can project it into an embedded Kuzu file at deploy time, exactly as bizgov does.

### 2.4 The orchestration loop (the crown jewel)

A bounded agentic loop shared verbatim between streaming, blocking, and eval paths (`project/chat/_tool_loop.py`):

- `MAX_TOOL_ITERATIONS = 8` — hard cap on LLM round-trips per turn
- `MAX_CONSECUTIVE_EMPTY_ITERATIONS = 2` — early exit when the agent is flailing (cost guard)
- **Same-turn dedup** — repeated `(tool, args)` returns the cached result instead of re-querying
- **Anti-echo directive** appended to empty tool results so the model doesn't repeat user-fabricated entity names back as if real
- **Non-convergence honesty fallback** — if the loop maxes out, the server does NOT let the LLM summarize near-miss retrievals; it returns a fixed "I don't have that" template plus any retrieved URLs as link cards. A clean refusal beats a confident wrong answer stitched from the nearest match.

### 2.5 Request lifecycle and state

- Single endpoint `POST /api/chat/` (`views.py:567`), **stateless server-side** — the client resends history (trimmed to 8 messages) each turn.
- Cross-turn grounding via **client-echoed `tool_context`**: the server returns `collected_tool_results` in a final metadata event; the client sends them back next turn; the server **sanitises** them (whitelisted keys, known tool names, size caps) because they're client-controlled.
- Layered per-turn message assembly: system prompt → degraded-mode notice → current date → user profile (from session cookie) → **page context** (which guide the chat was opened from) → intent-routing hint → sanitised tool_context → trimmed history.
- **SSE with a typed event protocol**: `content` / `tool_start` / `followups` / `rich_links` / `metadata` / `error` / `[DONE]`. Frontend is React 18 + Vite consuming the stream via `fetch()` + `ReadableStream` (POST body rules out EventSource), with a vanilla-JS fallback.

### 2.6 Grounding discipline (the ~700-line system prompt, v2.9)

Layered: Security → Identity → Tool routing → Reasoning tiers → Response shape → Conversation, plus ~15 worked examples. The load-bearing core (`system_prompt.py:126-136`):

> Every factual claim must be traceable to a specific field in a tool_result from THIS turn. … Internal-knowledge facts from training data are NEVER grounded, even when you are confident they are correct. … Before finishing, scan every numeric value, named scheme, and section reference. Ask: "Did the tool_result text in THIS turn actually contain this?" If no, **delete the sentence**.

Supporting mechanics: a deterministic keyword **intent pre-classifier** (<1ms, no LLM) that emits a routing hint and boosts search ranking; **server-side citation extraction** (`rich_links.py` — walks tool results deterministically, emits verified URL cards, no LLM); a **stream sanitizer** that strips hallucinated internal links against a published-slug allowlist; and a changelog header where nearly every prompt rule traces to a specific eval-failure ticket.

There is also a full conversational-behaviors design spec (`docs/guvnor-chat-behaviors.md`): intent routing (Inquire/Do/Feel), lede/body/tail response shape, three-axis follow-up chips (Role × Voicing × Intent), chitchat handling, sensitive-content registers. Notably, that spec descends from an audit of a **video assistant with playhead-awareness and no-spoiler rules** — Guvnor adapted those into "journey stage" and "no premature alarm". For fabula, the concepts port back to their native habitat: watch position *is* the playhead, and spoilers *are* spoilers.

### 2.7 Guardrails, cost, eval

- **Rate limiting**: `django-ratelimit` per-IP, dual `10/m` + `30/h` on chat (caveat: default LocMemCache makes limits per-gunicorn-worker, ~2× nominal).
- **Cost kill-switch**: the OpenRouter dashboard per-key spend cap; 402/429 surfaces as a friendly over-capacity message. Token controls: max_tokens 2048, cheap default model (`google/gemini-2.5-flash`, temp 0.3), history cap, iteration caps. LLM completions are not cached.
- **Prompt-injection defenses**: in-prompt override detection, refused-exchange stripping (anti session-poisoning), tool_context sanitisation, output hygiene.
- **Eval harness** (the maturity asset): golden question sets with expected tools/facts/anti-facts, an LLM-as-judge (BAML) scoring faithfulness/correctness/relevance/helpfulness on an asymmetric rubric, red-team (53 attacks) and defenses (127 tests) suites, a **fail-closed CI gate** with locked thresholds (ground truth ≥80%, red-team ≥95% with critical band 100%), and strategy isolation (`graph_only`/`django_only`/`full` via mock.patch) to measure each retrieval layer separately.
- **Historical lesson**: the 2026-05-15 wiring audit (`docs/ask-guv-wiring-audit.md`) found the chat had shipped with **zero rate limiting and no cost caps** — "the classic open billing pipe" — filed as critical issues and fixed later. Fabula should launch with both from day one rather than re-learning this.

---

## 3. Use-case analysis: compliance Q&A vs narrative exploration

The architecture transplants well; the *content assumptions* mostly don't. Two of them invert outright.

### 3.1 The contrast table

| Dimension | Ask Guv (compliance) | Fabula (narrative) |
|---|---|---|
| User state | Anxious, task-driven: "am I on the hook?" | Curious, exploratory: "how does this world fit together?" |
| Session goal | Get the answer, get out — fast exit is success | Wander productively — a longer, deeper session is success |
| Truth model | Statutory fact; one right answer | Canon-as-ingested plus Fabula's *analytical claims* (arcs, connections, BDI states) — the analysis is the product |
| Harm model | Wrong answer costs money / legal exposure (YMYL) | Spoilers; misattributed events; invented canon |
| Citation target | GOV.UK, legislation.gov.uk, regulator services | The catalog itself — every entity, event, episode, connection has a URL |
| Refusal shape | "Consult an employment solicitor" (professional handoff) | "That's beyond your watch position" / "the graph doesn't cover that season" |
| Register | Calm, precise, never chummy | Companionable archivist — knowledgeable, warm, enthusiastic about the material without gushing |
| Tone risks | Sounding like legal advice | Sounding like a fan wiki (undifferentiated) or a spoiler cannon |

### 3.2 Inversion 1 — spoilers are fabula's YMYL

Guvnor's tiered sensitivity model (routine fact / conditional / professional-judgement) is the load-bearing safety structure of its prompt. Fabula's equivalent is **watch position**. The mapping is direct — and structurally *stronger* in fabula's favour:

- Everything in the graph is episode-anchored (`PART_OF_EPISODE`, `BELONGS_TO_EPISODE`), and the storyline work established a total ordering: `sort_ordinal = season_number * 100 + episode_number`.
- Therefore spoiler safety can be enforced **at the retrieval layer, not the prompt layer**: every tool takes an optional `max_ordinal` parameter compiled into the query template (`WHERE ep.sort_ordinal <= $max_ordinal`). Facts beyond the ceiling never enter the LLM's context, so they *cannot* leak — a guarantee no prompt rule can give.
- Guvnor's "no premature alarm" rule (never volunteer penalties unprompted) becomes "never volunteer late-canon facts unprompted" for chips and welcome surfaces, even in full-canon mode.

**One honest complication**: entity profile prose (`foundational_description`, arc summaries, season profiles) is synthesized from whole seasons and is not decomposable by ordinal — a Series-4 fact can be baked into a character's description text. Structural filtering is sound for *events, connections, arcs, and episode-scoped fields*; for prose, spoiler-safe mode must prefer **episode-scoped substrates** — which is exactly what `AgentEpisodeProfile` provides (per-episode character state, currently built-but-dark in wagtail per the storyline brief). Spoiler-safe mode is thus a strong argument for finally importing that data: it becomes the spoiler-safe answer substrate.

### 3.3 Inversion 2 — parametric knowledge flips from gap to hazard

Ask Guv's grounding problem: the model knows *little* UK statutory detail, so ungrounded output is **fabrication** — plausible-sounding, wrong. The prompt exists to stop the model papering over retrieval gaps.

Fabula's grounding problem is the mirror image: the model knows Doctor Who, TNG, and The West Wing **deeply** from training. Ungrounded output will often be *factually correct fan knowledge* — and that's still a failure, for three reasons:

1. **It bypasses the product.** The chat exists to demonstrate the knowledge graph's analysis — per-entity arcs, BDI states, cross-episode connections with reasoning. An answer from the model's memory is an answer any chatbot could give.
2. **It breaks scope honesty.** The graph covers ingested seasons only (West Wing S1–S4, TNG S1–S3…). The model happily knows S5+; answering from memory silently misrepresents what the archive contains.
3. **It can smuggle spoilers past the structural filter.** The retrieval-layer ordinal ceiling is watertight for tool results — but useless if the model answers from training data. Spoiler-safe mode is only as strong as the grounding discipline.

So Guvnor's core rule transplants with *sharpened* force: **"Your training knowledge of this series is not a source. If the graph didn't return it this turn, it doesn't go in the answer."** The eval plan below adds a **parametric-bait suite** specifically for this: questions the model can answer from training but the graph cannot (un-ingested seasons, real-world production trivia absent from the graph) — the correct behavior is a scope-honest refusal naming what the archive does cover.

### 3.4 What has no compliance analogue (new design territory)

- **Contested interpretation.** "Is the Doctor actually dead?" / "Did CJ betray the President?" — narrative questions with in-text ambiguity. Handle like Guvnor's contested-non-YMYL pattern: attribution framing ("the graph records these events…; the FORESHADOWING connection to X suggests…") — present evidence, never render an authorial verdict beyond what the graph asserts.
- **In-world vs production register.** Users ask both "why did Bartlet hide his MS?" (in-world) and "who wrote this episode?" (production — writing credits are in the graph). The assistant should move between registers explicitly rather than blending them.
- **Proud provenance — the anti-Guvnor stance.** Guvnor *hides* its architecture ("never say knowledge graph / database / tool names"). Fabula should do the opposite: the graph is the selling point. "There are 228 connections bridging seasons 1 and 2 in the archive; here are the three strongest" is the voice of the product. Surface mechanics as delight, not plumbing.
- **Disambiguation across series.** "The Doctor" spans 26 seasons and multiple incarnations; "Enterprise" is a ship, an org, and a location. Entity resolution needs series scoping and candidate confirmation as a first-class conversational move, not an error path.

### 3.5 What transplants nearly verbatim

The bounded loop and all four guards (§2.4); statelessness + sanitised `tool_context`; the SSE event protocol and stream reader; deterministic rich-link extraction; the intent pre-classifier pattern; the layered prompt structure and delete-before-send; the chips model (Deepen / Apply→**Explore** / Pivot / Outward — where Outward means "to the catalog page"); rate limiting + spend-cap posture; the eval-first iteration culture and fail-closed gate.

---

## 4. Target architecture

### 4.1 Shape

```
Railway (production)
  Django/Wagtail + Postgres  ←  YAML import (v2.4.0 storyline contract)  ←  fabula_v2 Neo4j (local)
    ├── narrative_graph/          embedded KuzuDB, rebuilt from Postgres on deploy   (bizgov pattern)
    ├── pgvector (or vector blobs) entity + event embeddings, shipped in the export  (fabula's edge)
    ├── /api/chat/                stateless SSE endpoint, bounded tool loop           (port of Ask Guv)
    │     └── ~12 fixed narrative tools → Kuzu templates + ORM fallback
    │           every tool: required series scope, optional max_ordinal (spoiler ceiling)
    ├── /api/chat/suggestions/    deterministic per-page-type chips (no LLM)
    └── chat widget               React or vanilla, fetch+ReadableStream, mounted on catalog pages
```

Postgres remains the single source of truth; Kuzu and vectors are derived read models regenerated at deploy/import time. No Neo4j in production, ever.

### 4.2 The semantic layer (improving on the prior art)

bizgov's biggest gap is fabula's cheapest win:

- **Ship embeddings in the export.** fabula_v2 already holds OpenAI embeddings for every canonical entity in ChromaDB. Extend the export contract (v2.4.0 → v2.5.0, or a sidecar `.parquet`) to carry entity vectors; add an event-description embedding pass at export time (events aren't currently embedded). The site never pays to re-embed its corpus.
- **Store in pgvector** on Railway Postgres (one extension, no new service). Query-time: one cheap embedding API call per user question, cosine search scoped by series.
- **Use vectors for *resolution*, not for answers.** The failure mode to avoid is generic RAG — retrieving prose chunks and paraphrasing them. Vectors resolve "the guy with the cigarette holder" → `agent_toby_ziegler` (plus trigram/alias matching as in the GER matcher); the *graph tools* then produce the grounded answer. Retrieval recall, graph precision.

### 4.3 Tool surface (~12 fixed tools, sketch)

Every tool: `series` required; `max_ordinal` optional (spoiler ceiling, enforced in the query template). Descriptions carry routing guidance, per the bizgov lesson.

| Tool | Backing | Purpose |
|---|---|---|
| `resolve_entity` | pgvector + trigram/alias | Fuzzy description/name → candidate entities with confidence; the disambiguation entry point |
| `get_entity` | ORM | Profile, aliases, traits, affiliations, season appearances, arc summary |
| `entity_timeline` | Kuzu/ORM | Events an entity participated in, ordinal order, with episode anchors and roles |
| `entity_network` | Kuzu | Neighbors and relationship types; "who is X connected to and how" |
| `relationship_history` | Kuzu | Two entities: co-participated events over time — "how did X and Y's relationship evolve" |
| `get_episode` | ORM | Episode summary, acts, scenes, credits |
| `list_storylines` | ORM | Themes + conflict arcs for a series, with evidence counts |
| `get_arc` | ORM | One arc: description, type, member events with `PART_OF_ARC` roles (START/CLIMAX/RESOLUTION), involved characters |
| `connections_for_event` | ORM | The Event→Event narrative-connection edges (type, strength, `inferred_by`, `cross_episode_reasoning`) |
| `connection_path` | Kuzu | Path between two events/entities through the connection layer — "what links A to B" |
| `search_events` | pgvector + FTS | Semantic + keyword over event descriptions and `key_dialogue` |
| `graph_stats` | ORM | Counts per series — powers the proud-provenance voice and scope honesty |

Phase-2 addition: `cross_series_identity` (GER data, once exported) for Whoniverse-style questions.

Note the deep symmetry with the existing `fabula-neo4j` plugin tools (`fabula_entity_lookup`, `fabula_entity_network`, `fabula_top_entities`…) — that plugin is effectively the prototype of this tool surface, and the project has already recorded the lesson that *agent-walks-graph beats pre-marshalled payloads* for graph judgment. This is that lesson, productionized for the public.

### 4.4 Orchestration, prompt, presentation

- **Loop**: port `_tool_loop.py` semantics wholesale — 8 iterations, 2-empty-streak exit, same-turn dedup, anti-echo, honesty fallback ("The archive doesn't cover that — it currently holds Seasons 1–4 of The West Wing. Within those, I can…").
- **LLM**: OpenRouter, cheap default (Gemini Flash class), temp modestly higher than bizgov's 0.3 (~0.5) — narrative prose should breathe; facts stay grounded by the tool discipline, not the temperature.
- **System prompt**: layered per Guvnor — Security/Grounding → Identity/persona → Tool routing → **Spoiler discipline** → Response shape (lede/body/tail) → Conversation. Grounding core: every narrative claim traceable to a tool result this turn; training knowledge of the series is never a source; delete-before-send. Drop: YMYL tiers, professional handoffs, register-fidelity (must/should/could), architecture non-disclosure (inverted — see §3.4).
- **Citations**: deterministic rich-link extraction → entity/episode/connection **cards deep-linking into the catalog**. Every claim the chat makes should be one click from its evidence page. This, more than anything, is what makes the site feel alive — chat as a guide *through* the catalog, not a replacement for it.
- **Entry points**: chat panel on every catalog page with page context injected (character page → the entity pre-resolved; connection page → both endpoints pre-loaded). Deterministic welcome chips per page type (entity / episode / arc / connection / series home), spoiler-conservative by default.
- **Follow-up chips**: deterministic generator seeded from tool results *and* the response text (bizgov's own identified gap — build the response-aware version from the start). Roles: Deepen ("what happens between them next?"), Explore ("show Toby's season-2 arc"), Pivot ("other arcs Leo is involved in"), Outward ("open the episode page").
- **A cheap non-chat win — "explain this connection."** Every `NarrativeConnection` detail page gets a one-shot, fully-grounded LLM elaboration of the edge (endpoints + reasoning + surrounding context), generated on first request and **cached in Postgres forever**. Zero per-user cost after first view, no loop, no injection surface, and it directly upgrades the pages the PRD already made addressable. This can ship before the chat and prove the OpenRouter plumbing.

### 4.5 Spoiler model

- Per-series **watch position** in the session (mirroring bizgov's session-cookie business profile): "I've watched up to S2E10" → `max_ordinal = 210`.
- **Default: full-canon mode** with a visible "spoiler-safe" toggle — the catalog itself is unfiltered today, so a filtered-by-default chat would be inconsistent. When set: `max_ordinal` flows into every tool call (structural guarantee), prose answers prefer episode-scoped substrates (`AgentEpisodeProfile`), and the prompt adds presentation discipline (no teasing "something big happens in S3…").
- Chips and welcome surfaces are spoiler-conservative even in full-canon mode (never volunteer a late-season revelation unprompted — the "no premature alarm" transplant).

### 4.6 Guardrails and cost (launch-blocking, learned from the sister's audit)

- `django-ratelimit` per-IP dual-window from day one, backed by a **shared cache** (Railway Redis or DB cache) to avoid bizgov's per-worker limitation.
- **OpenRouter per-key spend cap set before the endpoint is public**; over-capacity handled as a friendly message.
- max_tokens ~2048, history cap 8, tool_context sanitisation ported as-is, published-URL allowlist for output hygiene.
- The connection-explainer feature (§4.4) is cached and thus immune to cost abuse; the chat is where all the controls concentrate.

### 4.7 Eval plan (before public exposure, not after)

Port the harness shape: golden YAML sets + LLM-judge + fail-closed gate.

| Suite | Content |
|---|---|
| Ground truth | Per-pilot-series questions with graph-verifiable answers ("who participated in X?", "when do A and B first share a scene?", "what connects event X to event Y?"), expected tools, expected/forbidden facts |
| **Spoiler leak** (fabula's red team) | Adversarial attempts to extract beyond-ceiling facts in spoiler-safe mode — direct, indirect ("why is S3 sad?"), and injection-style. Critical band = 100%, fail-closed |
| **Parametric bait** | Questions answerable from training but not the graph (un-ingested seasons, off-graph trivia). Pass = scope-honest refusal naming actual coverage |
| Faithfulness judge | "Grounded in the ingested graph, no invented events, no misattributed participants" — bizgov's asymmetric rubric with narrative content |
| Follow-ups | Chip anchoring and role-mix checks, per the behaviors spec |

Strategy isolation (`graph_only` / `orm_only` / `full`) ports directly and will show what the Kuzu layer actually buys over plain ORM.

---

## 5. Phasing

| Phase | Scope | Gate |
|---|---|---|
| **0 — Prerequisite** | Storyline import lands (v2.4.0 contract, companion brief) — the chat's best material *is* that data. Extend contract with embeddings sidecar (v2.5.0). Pilot series: **wolfhall** (gold-standard connection data: 1,814 event-layer edges, zero direction violations, 228 season bridges; small enough to eval exhaustively) | Import verified |
| **1 — Grounded generation, no conversation** | "Explain this connection" cached elaborations on connection pages; OpenRouter plumbing, spend cap, output hygiene proven at near-zero risk | Spot-check + cost telemetry |
| **2 — Chat MVP** | `sync_narrative_graph` (Postgres→Kuzu), 8 core tools, ported loop + prompt, SSE endpoint + minimal widget, rate limits, single series, full-canon mode only | Eval gate green (ground truth + parametric bait) |
| **3 — Semantic + spoilers** | pgvector layer + `resolve_entity` + `search_events`; spoiler-safe mode + `AgentEpisodeProfile` import; multi-series | Spoiler-leak suite at 100% critical band |
| **4 — Cross-series + surfaces** | GER-backed `cross_series_identity` (Whoniverse), arc-walkthrough pages, page-embedded contextual questions everywhere | — |

Phases 0–1 are independent of each other and can start immediately; Phase 1 requires no new data at all.

---

## 6. Open questions (Michael's calls)

1. **Persona and name.** "Ask the Archive"? A named archivist character? The Guvnor experience says the identity contract shapes everything downstream — worth deciding early. (A per-series in-world persona is tempting but multiplies prompt maintenance; one archivist voice across series is the maintainable default.)
2. **Spoiler default** — full-canon with opt-in safety (recommended above, consistent with the unfiltered catalog) vs safe-by-default (kinder to newcomers, but most catalog visitors have already watched).
3. **Model + budget posture** — Gemini-Flash-class economics vs a stronger model for the flagship experience; and whether Phase 1's cached explainers should use the stronger model (one-time cost per connection, permanent asset).
4. **Kuzu from Phase 2, or ORM-only MVP?** Most tools are 1–2 hops the ORM handles fine; `connection_path` and `entity_network` genuinely want a graph engine. The bizgov code makes Kuzu cheap to adopt, but an ORM-only MVP is defensible if Phase 2 needs trimming.
5. **Where does chat appear** — catalog pages only, or also the marketing tier as a demo surface?

---

## 7. fabula_v2 follow-ups (ticketable)

1. **Embeddings sidecar in the export contract** (entity vectors from ChromaDB; new event-description embedding pass) — extends the storyline brief's v2.4.0 work.
2. **Event `key_dialogue` and description completeness check** at export time — these fields become chat-visible verbatim; worth a hygiene pass on the pilot series.
3. (Already filed in the storyline brief: `arc_uuid` stamping on arc-guided enrichment edges — directly improves `get_arc`/`connections_for_event` answers.)
