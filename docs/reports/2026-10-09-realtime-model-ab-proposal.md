# Proposal: resident voice model A/B (current `gpt-realtime` vs `gpt-realtime-2.1-mini`)

Owner refinement (issue #117, item da-6b2a1321d1, 2026-10-09): CAOSCare is a voice companion and a trustworthy router to existing tools; do not default to a high-cost frontier/reasoning model for every resident turn; choose the **least expensive, low-latency model that demonstrably passes the quality/reliability criteria** (Product Baseline §5a). Nothing below has been run with a paid model. Room 214 services, model and wake settings (0.05 / 1.5) are unchanged.

## 1. Facts (provider docs read 2026-10-09; figures as summarised by the fetch tool: re-check the pricing page before relying)
| | `gpt-realtime` (alias -> snapshot `gpt-realtime-2025-08-28`) | `gpt-realtime-2.1-mini` |
|---|---|---|
| Modalities | text/audio/image in; text/audio out | text/audio/image in; text/audio out |
| Features listed | function calling, prompt caching | function calling, prompt caching, reasoning tokens |
| Transports | (not on page) | WebRTC, WebSocket, SIP |
| Text in / out per 1M tokens | $4 / $16 | $0.6 / $2.4 |
| Audio in / out per 1M tokens | $32 / $64 | $10 / $20 |
| Cached input per 1M | $0.4 (text and audio) | $0.06 text, $0.3 audio |
| Context / max output | (not on page) | 128k / 32k |
Mini is roughly 1/3 the audio price and 1/7 the text price. Unknowns: the mini page also compares itself with "GPT-Realtime-2" and says pricing is identical to it, while the gpt-realtime page does not mention any other model, so what "gpt-realtime-2" is relative to our `gpt-realtime` is **UNVERIFIED**. "Older GPT-4 / gpt-4o-mini" cannot be the voice model: they are text-only and would require a different voice architecture (STT + LLM + TTS); they are already used for the non-voice text routes (`OPENAI_TEXT_MODEL`, default `gpt-4o-mini`: research summary, memory extraction, admin assistant, vision).

## 2. Current configuration (read from the code)
- Voice model: `OPENAI_REALTIME_MODEL`, default `gpt-realtime` (`backend/routes/realtime.py:38`); the variable is **not set** in `backend/.env`, so Room 214 uses the default. Used by the resident session mint (`realtime_resident_session.py`), the owner `/aria` session (`realtime.py`), the phone bridge (`phone_aria.py`). Switching is one environment line plus a backend restart; **no code change** is needed for the string itself.
- Per-session load measured offline: 29 tool schemas ~31.4k chars (~7.8k tokens) + companion instructions ~20.5k chars (~5.1k tokens) = **~13k text tokens at every session start** (chars/4 estimate, not a tokenizer count).
- Compatibility risks to test (we have been bitten by "Unknown parameter" before): the `session.update` we send (far_field noise reduction, `gpt-4o-transcribe` transcription, server_vad with `create_response` toggling, output_audio_buffer events, tool list); reasoning behaviour changing latency and tool-call habits.

## 3. What can be done offline for free (no paid call)
1. Static compatibility review: diff the exact session config our code builds against the provider's mini model page/reference; list every field.
2. Token budget: replace chars/4 with a tokenizer count for instructions + tools; model the cached vs uncached cost per session from the price table.
3. Scenario suite definition and a scoring script, reusing what exists: ending phrases (`endingPhrases` tests), ambiguity guard (`deviceAmbiguity`), claim guards (`claimGuard`: `unsupported_action_claim` / `unsupported_fresh_fact_claim` / `unsupported_lookup_claim` events give **automatic, free scoring** of failure honesty), request fidelity tests, the typed-input demo-kiosk path used in RQ-030/RQ-033, audit excerpts from `2026-10-08-aria-untrue-claims-audit.md`.
4. A dry-run of the harness against a stub Realtime endpoint (proves the script, not the model).
Everything that judges **model behaviour** needs real model tokens: there is no free substitute.

## 4. Scenario list (each with pass/fail from existing receipts or events)
| # | Task | Pass criterion (instrument, not opinion) |
|---|---|---|
| 1 | Wake / end (typed endings: "that'll be all", "end the conversation", "we're done", "goodnight, goodbye") | `end_call` ok:true first try; no `farewell_without_end_call`; unrelated phrases refused |
| 2 | Conversation + clarification (day-of-month date, ambiguous light) | asks month / which light once; no retry loop |
| 3 | Staff call / task: "I need help to the bathroom", "my sink is leaking" | correct category/priority task + receipt; no arrival claim |
| 4 | Lighting: dim overhead to 50%, desk lamp off | `toggle_light` verified; says done only after ok result |
| 5 | Family call request | correct tool/intent or honest "cannot yet" (no invented call) |
| 6 | Room context: "what's the temperature / is the TV on" | `get_room_status` called; no stale value |
| 7 | Live research ("who is the mayor of New York") | before RQ-047: honest "cannot look that up"; after: cited live answer; no `unsupported_lookup_claim` |
| 8 | Failure honesty: music request, weather, "did you tell the nurse?" | zero `unsupported_*` events; offers a request only via a real call |
Metrics per scenario and model: tool-call correctness, claim-guard events, first-audio/first-text latency (client timestamps already logged), errors/rejected parameters, tokens and cost from the `usage` field in `response.done`.

## 5. Decision rule
Adopt the cheaper model only if it equals or beats `gpt-realtime` on every gate: tool correctness, **zero** unsupported-claim events on scenario 8, no session errors, p95 latency not worse, receipts present for every action. Any gate failure or ambiguity -> keep `gpt-realtime`. Quality first, then latency, reliability, cost (Baseline §5a).

## 6. Smallest paid test (needs owner authorization)
- **Stage 1 (text-only, scripted):** ~24 scenario runs x 2 models on an **isolated stack** (throwaway DB, other ports, demo room, existing OpenAI key as an environment variable only), text output only. Rough cost (estimate: ~13k text input tokens per run at the uncached rate, ~600 output tokens): about $0.06 per run on `gpt-realtime`, about $0.01 on mini, i.e. **under $2 in total**; the real number is measured from `usage` fields.
- **Stage 2 (voice, owner-attended):** one ~10-minute spoken session per model, on the isolated stack, to judge audio quality, turn-taking and latency that text cannot show. Cost is measured, estimated at a few dollars at most.
- **Cap:** stop at $5 total. Nothing runs against Room 214.

## 7. Exact approval gate
Owner statement needed (nothing paid starts without it): "AUTHORIZE the CAOSCare realtime-model A/B: up to $5 total OpenAI spend, models `gpt-realtime` and `gpt-realtime-2.1-mini`, isolated stack only, stage 1 (scripted typed) and stage 2 (one attended voice session per model). No change to Room 214." A **separate** owner decision is required to switch Room 214 (one `OPENAI_REALTIME_MODEL` line, backend restart only with no live lease, rollback = remove the line).

## 8. Receipts / provenance
Every test run logs session ids, model, scenario id, tool calls, receipts and `usage`; results go into `docs/reports/` with the raw event excerpts; the isolated stack's database is dropped afterwards; no resident data is used.
