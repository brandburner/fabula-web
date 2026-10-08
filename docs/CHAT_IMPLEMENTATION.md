# Ask the Archive — Chat Implementation

**Date:** 2026-07-25
**Implements:** `docs/CHAT_INTERACTIVITY_ARCHITECTURE_BRIEF.md` (Phase 2 MVP,
trimmed per open question #4: ORM-only, no Kuzu)
**App:** `chat/` · **Endpoint:** `POST /api/chat/` · **Widget:** every catalog
page via `templates/base.html`

## What shipped vs the brief

| Brief element | Status |
|---|---|
| Bounded tool loop (8 iterations, 2-empty exit, same-turn dedup, anti-echo, honesty fallback) | ✅ ported wholesale (`chat/tool_loop.py`) |
| Fixed tool surface, series-scoped, LLM never writes queries | ✅ 11 tools (`chat/tools.py`, `chat/registry.py`) |
| `connection_path` graph traversal | ✅ in-memory BFS over the series' connection rows — no graph engine needed at this scale (~2k edges/series) |
| Stateless server + sanitized client-echoed `tool_context` | ✅ (`chat/sanitize.py`) |
| SSE typed event protocol (content / tool_start / rich_links / followups / metadata / error / [DONE]) | ✅ (`chat/views.py`) |
| Deterministic rich-link citation cards | ✅ (`chat/rich_links.py`) |
| Deterministic welcome + response-aware follow-up chips | ✅ (`chat/chips.py`) — response-aware from day one, per §4.4 |
| Layered grounded system prompt (training knowledge is not a source; delete-before-send; proud provenance) | ✅ (`chat/prompts.py`) |
| Rate limiting from day one | ✅ dual-window per-IP on the default cache (`chat/ratelimit.py`) — prod's DatabaseCache makes it cross-worker |
| Page-context entry points (character page opens with entity pre-resolved) | ✅ (`chat/templatetags/chat_tags.py`) |
| Widget | ✅ vanilla JS + design-token CSS, both themes (`static/chat/`) |
| Spoiler-safe mode (`max_ordinal` ceilings) | ⏳ Phase 3 — full-canon only, but chips/welcome stay spoiler-conservative and the prompt bans volunteering late-canon reveals |
| pgvector semantic layer / embeddings sidecar | ⏳ Phase 3 (`resolve_entity` uses name/alias/role matching meanwhile) |
| Eval harness + fail-closed gate | ⏳ **launch gate, not yet built** — see below |
| "Explain this connection" cached elaborations (Phase 1) | ⏳ not built (chat was the ask); the OpenRouter plumbing it needed now exists |

## Configuration

| Env var | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | — | Setting it enables chat |
| `CHAT_LLM_BACKEND` | `openrouter` | `fake` = scripted no-key backend (tests, local widget dev) |
| `CHAT_MODEL` | `google/gemini-2.5-flash` | Any OpenRouter model id |
| `CHAT_MAX_TOKENS` / `CHAT_TEMPERATURE` | 2048 / 0.5 | Generation caps |
| `CHAT_RATE_LIMIT_PER_MINUTE` / `_HOUR` | 10 / 60 | Per-IP fixed windows |

With no key and no fake backend, `CHAT_ENABLED` is False: the widget doesn't
render and the endpoint returns 503. Local dev without a key:

```bash
CHAT_LLM_BACKEND=fake DJANGO_SETTINGS_MODULE=fabula_web.settings.dev python manage.py runserver
```

## Architecture notes

- **Stateless turns.** The client resends trimmed history (≤8) and the
  previous `metadata.tool_context` echo each request; both are sanitized
  (whitelisted tool names/keys, hard size caps) because they're
  client-controlled.
- **Grounding is structural + prompt.** Tools only return series-scoped rows;
  the prompt's coverage block is computed from the DB (cached 10 min) so
  scope-honest refusals name real holdings; rich-link cards are extracted
  server-side from tool results, never model output. The widget renders
  model-text links only for internal `/` paths.
- **Tool payload discipline.** Every list is capped (timeline 40, connections
  25/direction, search 20, path 6 hops) and prose is truncated — tool results
  feed straight into model context.
- **CSRF-exempt endpoint** — deliberate: anonymous, no auth cookies to ride,
  rate-limited.

## Operational cautions

- **Set the OpenRouter per-key spend cap BEFORE the endpoint is public**
  (brief §4.6 — the sister project shipped an open billing pipe and had to
  hotfix). 402/429 from OpenRouter render as a friendly over-capacity
  message.
- **`cache_page` interaction:** character/theme/arc/storyline detail views
  are cached for 24h. Toggling `CHAT_ENABLED` (first deploy with a key, or
  removing one) leaves already-cached pages with the old widget state until
  the cache clears (`import_fabula` clears it; or clear `django_cache`
  manually). This bit the test suite; it will bite the first prod enable.
- Chat responses are **not** cached; every turn costs LLM tokens. The rate
  limits and `max_tokens` are the cost ceiling.

## Before public launch (the brief's gates)

1. **Eval suites** (brief §4.7): ground truth per pilot series, parametric
   bait (the model knows these shows — pass = scope-honest refusal), and a
   faithfulness judge. The `fake` backend + `chat/tests/test_loop.py`
   ScriptedClient show the injection pattern for a harness.
2. Spoiler-leak suite once spoiler-safe mode (Phase 3) exists.
3. Consider Redis for the rate-limit cache if traffic outgrows DatabaseCache.

## Tests

`python manage.py test chat` — 43 tests: tool correctness + series-scoping
isolation on a two-series fixture graph, all four loop guards with a
scripted client, SSE framing, rate limiting, sanitization round-trips,
chips/rich-links determinism, widget mount/absence.
