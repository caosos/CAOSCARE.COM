# "Hey Aria" EliteDesk endpoint: physical-test evidence reconciliation (2026-10-08)

Source: owner dispatch issue #117. Read-only: `journalctl --user -u aria-wake.service`, local Mongo `caoscare` (`conversations`, `realtime_diagnostics`, `staff_tasks`, `receipts`, `notifications`), the marks file. Identity for every session below is `res_2425767f4a51` (Michael Chambers, Room 214 home test); Helen Torres (`res_81b72be1e8b5`) received no new turns.

## Setting under test
`aria-wake.env`: threshold 0.05, score 1.5 (was 0.15 / 1.0 until 2026-10-08 18:04 CDT), eMeet source, host idle (offline sweep paused). Left unchanged.

## Detector events (UTC; CDT = UTC-5)
| Detector time | Event | Session | Notes |
|---|---|---|---|
| 21:04:01, 21:05:32, 21:09:18, 21:11:13 | 4 wakes | 4 sessions | earlier test, old setting 0.15 / 1.0 (see `docs/PROJECT_STATE.md` audit) |
| 23:21:46 | wake | `rt_ox3y0lgu` | |
| 23:31:02 | wake | `rt_kcudm13j` | |
| 23:31:33 | detection_suppressed | (inside kcudm13j) | said while connected: by design, not a miss |
| 23:32:04 | wake | `rt_10vga4q6` | |
| 23:32:54 | wake | `rt_ftc0wtb1` | |
| 23:33:13 | detection_suppressed | (inside ftc0wtb1) | same |
| 23:33:34 | wake | `rt_91ppuwlf` | |
| 00:22:20 | wake | `rt_i0u1r9r0` | |

With the new setting: **6 logged wakes, each starting exactly one session**, plus 2 suppressed detections made while a call was already open.

## Owner's 5-of-6 report: what the logs support
- Owner statements recorded in his own saved turns: 23:31:40 "you woke up one of two times that I said Hey Aria"; 23:33:19 "four out of five times".
- The detector log proves **6 detections** in this window. It cannot count spoken attempts that produced no event. **No miss was recorded** with `wake_stats.py mark` (marks file absent), so the one missed attempt is **owner-reported only, not verified**. The 5-of-6 figure is therefore a UNVERIFIED owner count, consistent with, not proven by, the log (5 wakes between 23:21 and 23:33 plus the later 00:22 one).
- **False wakes: none shown.** Every logged wake was followed by a session in which Michael spoke on topic; the two suppressed detections occurred during open calls. Not a formal long-duration false-wake rate: no timed quiet-TV soak has been run on the live setting.

## Endings (end_call tool results)
| Session | Resident's closing words | end_call | Goodbye audio | Audio stop to close |
|---|---|---|---|---|
| ox3y0lgu | "That will be all for now. Goodbye." | ok:true first try | 3344 ms | 404 ms |
| kcudm13j | (model called end_call after a non-ending utterance) refused ok:false; then "Yes, this call" | follow-up accepted ok:true | 2482 ms | 403 ms |
| 10vga4q6 | "That'll be all for now, goodbye." | ok:true first try | 3754 ms | 403 ms |
| ftc0wtb1 | (model called end_call after "four out of five times" ) refused; then "Yes, goodbye." | follow-up accepted | 3051 ms | 401 ms |
| 91ppuwlf | "Good, that'll be all, goodbye." | ok:true first try | 2846 ms | 403 ms |
| i0u1r9r0 | "That'll be it, thank you." | ok:true first try | 2775 ms | 401 ms |

- Hang-up behaviour verified in all 6: the full goodbye plays, the session closes ~0.4 s after the audio stops, listening resumes right after.
- The two refusals were correct: the model had called `end_call` on utterances that were not endings (a model behaviour; the guard held).
- **Named phrases actually tested:** "That'll be it" (yes, call 6), "That will be all, goodbye" (yes, three variants), "Goodbye" (yes, via the follow-up "Yes, goodbye"). **NOT tested: "End the conversation now" and "We're done".** No PASS is claimed for those two (unit-tested only).
- Transcription noise seen: "Glaðséttur", "Times." (noise/silence transcribed by the model).

## Test side effect: kitchen request
`task_8658f91058a7` (kitchen, pending, priority normal): created 23:22:30 UTC in session `rt_ox3y0lgu` when Michael answered "That would be lovely" to Aria's offer to ask the kitchen about supper.
- Under Michael's test identity (`res_2425767f4a51`), `simulated:false`, source `aria_voice`, `resident_words` "That would be lovely." (the model summary holds the content).
- Receipt: `resident_request_created`, identity basis `unverified_room_claim`, authority `public_resident_bus`.
- Notification: one email record, **status `logged`**, to the demo kitchen staff address (`iris.kwan@demo.caoscare`): **nothing was sent**, nobody dispatched.
- Left open and untouched. Closing it is Michael's call through the normal staff action (receipted), not deletion.

## Verdict
- Wake: 6 logged detections / 6 sessions, 0 observed false wakes, miss count owner-reported (UNVERIFIED). Not a PASS on a miss rate until misses are marked or an attempt counter exists.
- Endings: phrases tested above PASS; two named phrases remain untested (WAITING_OWNER).
- Hang-up: PASS (6/6).

## Remaining owner steps (only these)
1. Say "End the conversation now" and "We're done" once each in separate calls.
2. For wake rate, run `wake_stats.py mark miss --note ...` at each unanswered attempt (or tell me the counts) and one quiet 10-minute TV period without speaking to Aria.
