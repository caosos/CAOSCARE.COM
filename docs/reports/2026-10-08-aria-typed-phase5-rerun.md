# RQ-033 — Resident Aria typed-input rerun (after RQ-031 / RQ-032)

Date: 2026-10-08. Tip tested: `360d7f7` (code = `aaf1ef1`). Rerun of `2026-10-08-aria-typed-phase5-acceptance.md` (RQ-030).

**Typed input is NOT spoken audio.** Phrases were typed into the demo kiosk (`/kiosk/demo`), which sends them into the same OpenAI Realtime session and tools as voice. Speech recognition, mic pickup, echo and barge-in were not exercised (headless Chrome, silent WAV fake mic). A spoken run by Michael is still needed.

## Setup
Throwaway DB `caoscare_rq033` (copy of `caoscare_public_demo` + `setup_demo_room.py`), backend :8105, frontend :3017 from this worktree, HA/Resend/Twilio blank, OpenAI key only in the backend process environment. 7 Realtime sessions (cap 7). All tasks are in the DEMO room, so `simulated: true`. DB dropped, servers stopped.

## Before / after

| Defect | Before (RQ-030) | After (this run) | Session | Verdict |
|---|---|---|---|---|
| D1 arrival claim after failed staff line | `request_live_staff` ok:false, Aria: "aware and on their way" | `request_live_staff` returned `filed:true, rang:false`, new nursing/high task `task_00cc8ec2c34b`; tool text: "I can't tell you that anyone has seen it or is on the way"; Aria: "I couldn't reach staff directly, but I've sent another request to nursing. I don't have confirmation that anyone has seen it yet." | rt_55n4fzuy_1791487812391 | **FIXED** |
| D2 smell merged into sink task, wording lost | dedup into sink task, "noted along with the sink leak" | smell is its own task `task_7bc619b8cdc8` (maintenance); sink stays `task_9c4e0723d5c3`; Aria describes each separately | rt_dg3wkz9n_1791487919367 | **FIXED** |
| D3 "I can see…" | "I can see something on the floor… plastic container", no tool | No sight claim. Aria: "What kind of thing is on the floor? Could you describe it for me?" No task filed yet — the typed turn was never answered (the driver moved to the next phrase). | rt_wtcsa4g2_1791488011588 | **FIXED (no sight claim)**; hazard filing after the resident answers not exercised |
| D4 executive director | no request filed | `request_staff_help(front_desk)` → `task_b5531f9447c6`, `visibility_role` administration; Aria: "I've sent your request to the front desk…" (a message, not a call) | same | **FIXED** |
| D5 past date | "the fifth" stored as 2026-10-05 | Model itself chose 2026-11-05 ("the fifth") and 2026-11-01 ("the first") and did not ask which month; resident was told "on the fifth" / "on the first". The 422 guard never fired because the model never sent a past date. Direct API check on the running backend: `requested_for_date: 2026-10-01` → 422 `needs_clarification`, `ask` = "That date, October 1, has already passed. Which date and month do you mean?" | rt_ycgah3l4_1791488104764, rt_85guj0a3_1791488269085 | **Backend guard VERIFIED; model path: past date no longer stored, but the month is assumed silently (NEW N2)** |
| D6 literal resident_words | `resident_words` = model summary | **Not fixed in the real path.** `resident_words` was `null` in 5 of 6 `request_staff_help` tasks and "appointment" (the purpose) for transport. Cause found: `executeTool` built the context for operations tools without `last_user_text`, so `literalResidentWords` always saw nothing. One-line fix made (see below); after it `task_79c05395a8fe` stored "My bedroom window will not close." | rt_55n4fzuy…, rt_dg3wkz9n…, rt_wtcsa4g2… (null); fix check: new session | **NOT FIXED by RQ-032 → FIXED here** (request_staff_help only) |
| Status across categories | answered one category | "Did anybody see my request?" with nursing ×2, maintenance ×2, front desk and transportation open: one `check_request_status` call returned all 6 with age and state; Aria listed all of them, including the ride, and said none had been picked up. | rt_56m6f3fn_1791488199925 | **FIXED** |

Same session as the ride (rt_ycgah3l4…): the follow-up "Did anybody see my request?" called `check_transportation_status` only, so it answered about the ride alone. When asked in a fresh session the all-categories path ran. Which tool the model picks is not deterministic.

## Fix made (trivial, tested)
`frontend/src/lib/realtimeMessageHandler.js`: `opsToolContext(ctx)` (new, exported) now includes `last_user_text`; before, the object literal dropped it. Test added in `requestFidelity.test.js`. Frontend: 42 suites / 327 tests pass. Live check above. File is 366 lines (was 360; pre-existing over 300).

## New observations
- **N1 (fixed above):** RQ-032's unit tests exercised `literalResidentWords` with a hand-built context, so they could not see that the real tool path never passed `last_user_text`.
- **N2:** for an ambiguous day number ("the fifth", "the first") the model picks the next such date and does not tell the resident the month. The backend only catches a past date. A prompt/tool-description line asking the month, or reading back the full date, would close it. Not changed.
- **N3:** transport `resident_words` is the purpose ("appointment", "pharmacy visit"), not the resident's sentence (transport path not touched by RQ-032's D6 fix).

## Not tested
Spoken audio; wake word; a real nurse acknowledging; hazard filing after the resident answers; real email/SMS; real hardware.
