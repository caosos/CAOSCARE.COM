# Research provider (RQ-047)

`research_topic` (Aria's lookup tool) calls `POST /api/research`. The backend provider is chosen by environment:

| Variable | Meaning |
|---|---|
| `CAOSCARE_RESEARCH_PROVIDER` | `none` (default, also when unset) or `openai_web_search` |
| `OPENAI_API_KEY` | same key as the rest of the backend |
| `OPENAI_RESEARCH_MODEL` | **required** for `openai_web_search`; no default model is assumed |
| `OPENAI_RESEARCH_TIMEOUT` | optional seconds (default 25) |
| `OPENAI_RESEARCH_REASONING_EFFORT` | optional; sent as `reasoning.effort` only if set |

## Behaviour
- `none`: no live research. With only `OPENAI_API_KEY`, a plain model answers from general knowledge with `live: false`; otherwise HTTP 503. Prompt and tool text tell Aria she cannot look things up. Merging this change alone changes nothing live.
- `openai_web_search`: Responses API with the native `web_search` tool (`tool_choice: required`). `live` is true **only** if the response has at least one `web_search_call` and at least one `url_citation`. Otherwise `live: false` with a `note`. Prompt/tool text flip to "live" only when provider, key and model are all set (`live_research_enabled()`, single source of truth in `routes/realtime_truth_rules.py`).
- Errors: not configured or model missing -> 503 with the reason; provider HTTP error, timeout or malformed response -> 502 (no fallback, no invented text).
- Response fields: `answer`, `citations` (URLs), `citations_detail` ([{url,title}]), `source` (`openai_web_search`), `live`, `note`, `provenance` (model, response_id, search_call_count, retrieved_at).
- Every call writes a `research_lookup` event (`/api/events`): question hash and length (not the text), provider, model, live, citation count, outcome.

## Enabling (owner decision, not done by this change)
Set `CAOSCARE_RESEARCH_PROVIDER=openai_web_search` and `OPENAI_RESEARCH_MODEL=<model>` in `backend/.env`, restart the backend, run one owner-approved live smoke call and confirm the budget (Baseline section 5a). Pricing: per search call plus tokens; look up the provider's current page.

## Rollback
Set `CAOSCARE_RESEARCH_PROVIDER=none` (or unset it) and restart the backend.

## Access guard and rate limit (RQ-049)
- With `openai_web_search` enabled, `POST /api/research` requires `resident_id` + `session_id` of a live Aria room lease (same check as `/memory/realtime-turn`, shared in `routes/session_grounding.py`, with a 60 s grace after release) OR a valid owner token (the owner `/aria` build). Otherwise HTTP 403 and no provider call. With provider `none` there is no guard.
- In-memory rate limit per room (owner: per user) `CAOSCARE_RESEARCH_RATE_PER_MIN` (default 6) -> HTTP 429. Counters reset on restart.
- Every denial writes a `research_lookup` event (status failed, reason). The frontend turns 403/429 into "I can't look that up right now."

## Owner decisions still required (coordinator note, 2026-10-09)
- Which `OPENAI_RESEARCH_MODEL`, one approved smoke call and its spend, then the live switch (set `CAOSCARE_RESEARCH_PROVIDER=openai_web_search`, `OPENAI_RESEARCH_MODEL`, restart with no live lease; rollback: set provider `none`).
