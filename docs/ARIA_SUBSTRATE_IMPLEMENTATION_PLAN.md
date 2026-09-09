# Aria Substrate — Implementation Plan

**Derived from:** `docs/ARIA_CONVERSATION_SUBSTRATE.md` (contract) +
`docs/ROOM_214_CONVERSATION_EVIDENCE_2026-09-08.md` (evidence + mechanism map).
**Branch:** `aria/conversation-substrate`. **Started:** 2026-09-08.

This is the minimum clean architecture, not a rewrite. It layers on top of the
Level 1 event/lease/session-fencing plumbing already in progress on this branch
(one open event per resident, activation-id fencing, RF burst grouping, lease
evidence) — that plumbing is compatible and is reused, not redone.

## Context assembly — layers → modules

Aria assembles the context package; the model only generates turns for it.
`person → Aria conversation layer → context assembly → model adapter → model →
action layer → response`.

| Layer | Contract item | Where it is assembled | Status |
|---|---|---|---|
| **A — Session baseline** | Aria identity, persona, tempo, truth discipline, time/place anchor, resident identity, durable prefs, accessibility, durable memory (reference-not-filler) | `realtime_companion_prompt.py::_build_companion_instructions` + `realtime_companion_memory.build_resident_profile_and_memory` + `realtime_facility._facility_now` | **exists** (pre-substrate). Opener softened 2026-09-08: greeting is presence-first, not "ask what they need". |
| **B — Live conversation** | recent turns, unresolved threads, cross-session continuity | *not assembled* — `conversations` is write-only in the mint path; each `session_id` starts blank | **TODO** — biggest remaining gap. Room 214 s8→s9→s10 "I thought I just told you". |
| **C — Active threads** | what THIS conversation has developed into; `conversation_active` vs `actionable_intent_detected` vs `action_in_progress` vs `awaiting_required_detail` | partial: `aria_state` on the event (`dormant/active/muted_staff/dismissed`); no per-conversation thread/intent state | **TODO** — needs a runtime conversation-state object distinct from event lifecycle. |
| **D — Retrieved durable memory** | older memory relevant to the *current subject*, retrieved on demand | `build_resident_profile_and_memory` loads a fixed block at mint; no subject-triggered retrieval | **partial / TODO** — progressive retrieval when a topic emerges. |
| **E — Current operational reality** | open event + staff requests + calls/alerts, real lifecycle (`open/acknowledged/answered/in_progress/resolved/…`) + who + timestamps + `current` vs `background` | `routes/aria_operational_state.py::resolve_operational_state` → rendered by `routes/realtime_operational_context.py::render_operational_block` → appended to instructions by `_build_companion_instructions`; also on `_caos.context.operational_state` and `GET /api/aria/operational-state` | **DONE 2026-09-08** (this change). Kills Room 214 mechanism #1 (stale state announced as current) and #7 (stale context injected once). |
| **F — Tools / capability truth** | only the relevant tool capability for the emerging work; capability portfolio so Aria claims only `verified_control`/`verified_read` | `realtime_tools.py` / `realtime_tools_operations.py` build the full schema at mint; `docs/ARIA_CAPABILITY_PORTFOLIO.md` / `db.aria_capabilities` exist but `get_capability_summary()` is **not wired into the session** | **TODO** — wire capability truth into context (Room 214 s16 "I can see you through the camera"). |

## Done in this change (2026-09-08)

1. `routes/aria_operational_state.py` (228 ln) — the Layer E authority. Unifies
   `db.alerts` (assistance events) and `db.staff_tasks` (staff requests) into one
   snapshot: normalized `lifecycle`, `handled_by`, `opened_at` + conversational
   `opened_age`, `relevance` (`current` iff it is the `alert_id` Aria was brought
   in on, or the sole open event), `recently_resolved` (≤12 h, history not
   waiting), and `speak_guidance` ("don't read this as a queue").
2. `routes/realtime_operational_context.py` (49 ln) — renders the snapshot into a
   terse `## What's actually happening right now` prompt block; **empty string
   when nothing is open** so a fresh session does not begin inside a workflow.
3. `routes/realtime_companion_prompt.py` — `_build_companion_instructions` takes
   `operational_state`, appends the block; opener changed from "say their name
   and ask what they need" → presence-first, "a greeting is not a transaction".
4. `routes/realtime_resident_session.py::_mint` — resolves operational state
   (best-effort; never blocks the mint) and threads it into both the instructions
   and `_caos.context`.
5. `GET /api/aria/operational-state` (public, resident/room-scoped) + `server.py`
   registration.
6. Tests: `tests/test_aria_operational_state.py`, `tests/test_companion_prompt_substrate.py`.

## Next steps, in order

1. **Restart / reload the dev backend** so `GET /api/aria/operational-state` is
   live, then un-skip `test_operational_state_http_endpoint`. (No reload flag on
   the running process — coordinate, don't do it unprompted mid-other-lane-work.)
2. **Layer B — cross-session continuity.** On mint and on reconnect, load the
   resident's recent turns (last ~N, last ~M minutes, across `session_id`s) +
   any unresolved thread, render a `## Where we were` block. Key by resident +
   recency, never by `session_id`. Regression: the s8→s9→s10 sequence must not
   re-greet from scratch.
3. **Layer C — runtime conversation state.** A per-conversation object holding
   `conversation_active | actionable_intent_detected | action_in_progress |
   awaiting_required_detail | action_completed | conversation_resumed`, set from
   the transcript, separate from `aria_state`. Drives: no task created merely
   because a session exists; tool use returns *into* the conversation, no reset.
4. **`check_request_status` / `request_staff_help` → speak from Layer E.** Their
   result formatters should defer to `resolve_operational_state` (real lifecycle
   + age) instead of the current timestamp-less "already on file / ask #N" text.
5. **`end_call` — honor a clear closing on the first call** (Room 214 mechanism
   #6); keep the confirm only for genuinely ambiguous input. Frontend
   `restingEndCallGuard` + `end_call` handler.
6. **Device-tool discipline** (mechanisms #4, #5): disambiguation returns one
   question to the resident; throttle identical failing calls; confirmation
   sentence generated from the tool result, not the intent.
7. **Layer F — capability truth in context**; empty-args emergency guard
   (mechanism #9).
8. **Portability seam.** Formalize `context assembly → model adapter → model` so
   an adapter swap (GPT/Claude/Qwen/Llama) keeps A–F intact. Today the assembly
   is already provider-neutral (plain text package); the seam just needs naming
   and a second adapter to prove it.

## Invariants any future change must keep

- Empty operational state ⇒ empty block ⇒ no forced workflow at session start.
- `current` vs `background` is decided by the activation Aria was brought in on,
  never by "newest wins".
- Lifecycle words come from real fields (`resolved_at`, `acknowledged_at`,
  `live_line_state`, task `status`), never from a notification string.
- Aria may state *when* something opened (`opened_age`), never invent a clock time.
- This module is read-only; lifecycle transitions stay in `alerts.py` /
  `alert_lifecycle_events.py` / `resident_requests.py`.
