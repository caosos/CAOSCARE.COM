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
| **B — Live conversation** | recent turns, unresolved threads, cross-session continuity | `routes/aria_continuity.py::resolve_continuity` → `render_continuity_block` → appended by `_build_companion_instructions` between baseline and operational state; also `_caos.context.continuity` and `GET /api/aria/continuity` | **DONE 2026-09-08** (Layer B commit). Compact recap of ≤3 prior sessions within an 18 h window from `db.conversations` + `session_ended` reasons. Baseline-not-workflow: recaps what was *said*, never marks a task active, points at Layer E for live status. Room 214 s8→s9→s10 "I thought I just told you" regression covered. |
| **C — Active threads** | what THIS call has developed into; `conversation_active` / `action_in_progress` / `awaiting_required_detail` / `action_completed` / `conversation_resumed` (`actionable_intent_detected` stays a live, unpersisted model classification) | `routes/aria_conversation_state.py::resolve_conversation_state` (keyed by `session_id`) → `render_conversation_state_block(cs, operational_state)` → appended by `_build_companion_instructions` between continuity and operational; also `_caos.context.conversation_state` and `GET /api/aria/conversation-state` | **DONE 2026-09-08** (`a03d5b5`), **review-integrated 2026-09-09**. Session-scoped only — reads `conversations.session_id` + `staff_tasks.conversation_session_id` + `realtime_diagnostics.session_id`, never a facility-wide `resident_id`/`room` query (that is Layer E). Defers to Layer E: the render suppresses "in motion" language when E's snapshot shows the same `task_id` is no longer open. `awaiting_required_detail` needs positive evidence (a `tool_call` this call with no resident turn since) — an empathetic "How are you feeling?" is `conversation_active`, emits nothing. |
| **D — Retrieved durable memory** | older memory relevant to the *current subject*, retrieved on demand | `build_resident_profile_and_memory` loads a fixed block at mint; no subject-triggered retrieval | **partial / TODO** — progressive retrieval when a topic emerges. |
| **E — Current operational reality** | open event + staff requests + calls/alerts, real lifecycle (`open/acknowledged/answered/in_progress/resolved/…`) + who + timestamps + `current` vs `background` | `routes/aria_operational_state.py::resolve_operational_state` → rendered by `routes/realtime_operational_context.py::render_operational_block` → appended to instructions by `_build_companion_instructions`; also on `_caos.context.operational_state` and `GET /api/aria/operational-state` | **DONE 2026-09-08** (this change). Kills Room 214 mechanism #1 (stale state announced as current) and #7 (stale context injected once). |
| **F — Tools / capability truth** | only the relevant tool capability for the emerging work; capability portfolio so Aria claims only `verified_control`/`verified_read` | `realtime_tools.py` / `realtime_tools_operations.py` build the full schema at mint; `docs/ARIA_CAPABILITY_PORTFOLIO.md` / `db.aria_capabilities` exist but `get_capability_summary()` is **not wired into the session** | **TODO** — wire capability truth into context (Room 214 s16 "I can see you through the camera"). |
| **G — Person-specific interpretation continuity** (Terminal 10; NON-NEGOTIABLE per AGENTS.md + `docs/CAOS_CARE_AGENT_ONBOARDING_CONTRACT.md`) | durable heard→understood patterns (phonetic approximations, shorthand, recurring substitutions, confirmed meanings), resident-scoped, retrieved before/during prompt construction, corrections applied without cross-pattern leakage, original wording preserved | `routes/aria_interpretation_patterns.py::resolve/record/find/list/render` → `render_context_tail` → appended by `_build_companion_instructions`; `confirm_interpretation_pattern` Realtime tool (`realtime_interpretation_tools.py` + `realtimeOperationsTools.js`); `_caos.context.interpretation_patterns`, `GET/POST /api/aria/interpretation-patterns[/confirm|/match]` | **DONE 2026-09-10.** Acceptance case "dos savor" → "dos sabores" → "two flavors" proven end-to-end (store, fuzzy match, mint-time render, full-prompt assembly). Own collection (`db.interpretation_patterns`), not a second `db.memories` architecture. |

## Terminal 10 — conversation parity, done 2026-09-10

`commands/TERMINAL_10_CONVERSATION_PARITY.md` (main, `5b48c17`). Executed as
part of this lane per Michael's explicit authorization to pick it up on
`aria/conversation-substrate` rather than a new branch.

1. **Multilingual transcription** — `frontend/src/lib/realtimeSessionUpdate.js`
   hard-coded `input_audio_transcription.language: "en"`, forcing English
   recognition even on Spanish/mixed-language speech. Verified against current
   OpenAI docs before changing anything: a full conversational session
   (`session.type: "realtime"`, ours) only accepts `gpt-4o-transcribe` /
   `gpt-4o-mini-transcribe` / `whisper-1` for input transcription, and those
   use the singular, OPTIONAL `language` hint - the newer multi-language
   `languages` array (`gpt-transcribe`/`gpt-live-transcribe`) is only valid in
   a dedicated `session.type: "transcription"` session, not this one, so the
   model was NOT swapped. Fix: removed the hard-coded hint so the model
   auto-detects the spoken language per turn. `realtimeSessionUpdateLanguage.test.js`.
2. **Person-specific interpretation continuity** — Layer G above.
3. **Turn-taking instrumentation** — `routes/aria_turn_taking.py::resolve_turn_taking`
   derives silence-before-response gaps, response durations, barge-in and
   premature-interrupt counts, and long-gap counts from the
   `realtime_diagnostics` events `useRealtimeVoice.js` **already writes**
   (`speech_started/stopped`, `response_created/done`; `assistant_speaking` is
   already populated per event - confirmed against real session history: 250
   of 857 real `speech_started` rows already carry `assistant_speaking=true`,
   i.e. real recorded barge-ins) - no new frontend capture needed. Read-only,
   no transcript text returned. `GET /api/aria/turn-taking/{session_id}`.
4. **Wake word** — documented, not prototyped: `docs/ARIA_WAKE_WORD_ARCHITECTURE.md`.
   Verified NO Level 1 change is needed (`Alert.trigger_source` is already a
   free-form string with `"wake_word"` already named as an anticipated value,
   and `POST /realtime/room/{room}/activate` already accepts any
   `trigger_source`) - a wake-word listener is purely additive. Engine choice
   (openWakeWord custom-trained vs Picovoice Porcupine) and the physical
   in-room listening test are the next steps, not skipped work.

`realtime_companion_prompt.py` grew a 5th context source, so the block-
assembly tail was extracted into `routes/realtime_context_tail.py`
(`render_context_tail`) - net effect was fewer lines in the companion-prompt
file despite adding a capability (285 → 278).

## Layer B — done 2026-09-08

- `routes/aria_time.py` (36) — shared conversational time phrasing
  (`age_phrase`, `parse_dt`); extracted from `aria_operational_state.py` so
  Layer B and Layer E word "how long ago" identically. One source of truth.
- `routes/aria_continuity.py` (197) — `resolve_continuity(resident_id,
  current_session_id, room)` reads `db.conversations` (the existing turn
  store — no parallel history system), groups by `session_id`, keeps ≤3
  prior sessions whose last turn is within `CONTINUITY_WINDOW_HOURS` (18),
  and for each reads its `session_ended` reason from `db.realtime_diagnostics`
  to flag `unfinished` (dropped/timeout, not a resident goodbye).
  `render_continuity_block` compacts it: resident lines verbatim (the
  referent for "that" / "the other one"), assistant lines trimmed and
  de-greeted, biased to the tail, hard-capped at `_TOTAL_CHAR_CAP` (2200).
  Header states plainly it is context not a task, not an opener, and that
  the "What's actually happening right now" (Layer E) section is
  authoritative on live status.
- `_build_companion_instructions(..., continuity=...)` appends the block
  between `profile_and_memory` and the operational block.
- `routes/realtime_resident_session.py::_mint` resolves it best-effort and
  threads it into instructions + `_caos.context.continuity` (rides with the
  Level 1 `_mint` extraction, same as the Layer E wiring).
- `GET /api/aria/continuity` (public, resident/room-scoped) — inspection.
- Tests: `test_aria_continuity.py` (cases 1–8 + economics), plus
  `test_substrate_layers_integration.py` (Layer B + E together: current
  state wins, block order).

Cost: one indexed `db.conversations` query + in-memory trim, no LLM call.
Typical rendered block ≈ 1 000 chars (~250 tokens); worst case bounded at
≈ 2 800 chars (~700 tokens) by the cap.

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

1. **Restart / reload the dev backend** so `GET /api/aria/operational-state` and
   `GET /api/aria/continuity` are live, then un-skip
   `test_operational_state_http_endpoint`. (No reload flag on the running
   process — coordinate, don't do it unprompted mid-other-lane-work.)
2. **Layer B corrections — DONE 2026-09-09.**
   - B-2: `unfinished` now needs positive evidence — `end_reason ∈ _DROPPED_ENDS`.
     A missing / `None` / unknown reason is neither `unfinished` nor
     `clean_close`; the recap header then carries no drop/goodbye tail.
   - B-1: the `db.conversations` continuity index moved to
     `aria_continuity.ensure_indexes()`, called once from `server.py` lifespan;
     `resolve_continuity` no longer does DDL in the request path.
2b. **Layer B on reconnect** (still pending). `resolve_continuity` runs at mint
   only; a mid-call reconnect refresh (incl. the current session's own turns)
   via `session.update` needs a frontend consumer — waits on `useRealtimeVoice.js`.
3. ~~**Layer C — runtime conversation state.**~~ **DONE** (`a03d5b5` +
   review-integration commit). `routes/aria_conversation_state.py`, session-scoped,
   defers to Layer E, positive-evidence `awaiting_required_detail`.
4. ~~**`check_request_status` / `request_staff_help` → speak from Layer E.**~~
   **DONE (backend)** — `routes/aria_request_status.py::request_status_view`
   turns a `staff_tasks` row into `{lifecycle, opened_age, spoken}` using Layer
   E's `task_lifecycle` + shared `age_phrase`; `_resident_safe_view` and the
   `create_resident_request` dedupe branch now return those fields.
   `test_request_tools_speak_from_layer_e.py` proves the tool-facing view and
   `resolve_operational_state` cannot disagree on a task's lifecycle, and that
   no "waiting/unanswered" language survives once resolved. **Remaining:** the
   frontend `realtimeOperationsTools.js` must forward `data.spoken` verbatim
   for `check_request_status` + the dedupe branch (one line each) — frontend
   lane, blocked on the `useRealtimeVoice.js` refactor landing.
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
