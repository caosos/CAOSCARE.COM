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

---

# Addendum 2026-10-08 evening (issue #117 comments 01:00-01:10 UTC): mic relocation, "hay area", ending failures

Instrument sources: listener journal (incl. new `audio_level` lines, present only after the 01:08:14 UTC restart), Mongo `conversations` / `realtime_diagnostics`. Owner statements are labelled as such. Times UTC.

## Sessions in the window (all identity `res_2425767f4a51`; Helen +0)
| Detector wake | Session | What happened | Verdict |
|---|---|---|---|
| 00:57:38 | `rt_y19cdp6r` | normal chat; owner: "Okay, end the conversation." -> end_call **ok:true first try**; closed 3.4 s later | wake HIT; ending "End the conversation" PASS |
| 00:59:10 | `rt_rwwnp61e` | owner: "Good, we're done." -> end_call **ok:true first try** | wake HIT; ending "We're done" PASS |
| 01:04:03 | `rt_7schnxd2` | greeting, "Can you hear me?", Aria began answering | session **killed 3 s in**: `session_ended reason=component_unmount` at 01:04:16.94 |
| (none) | `rt_0rm7tpvq` | new session 01:04:20 with **no wake event** ("Something interrupted you"), ended "That'll be all, Fernando." -> ok:true | follow-on of the unmount, see below |
| 01:06:23 | `rt_zu1x1e37` | **false wake** (owner: "It's over there in that hay area"); garbled turns "Oi", "Фредерик", "Alfredo.", Aria said "Goodnight, Michael. I'll be here whenever you need me." with no end_call; then "Goodnight, goodbye." refused; "Yes, I want to end our conversation." ok:true | see findings 2 and 3 |
| 01:08:52 | `rt_s8dofm9c` | intentional wake; "dim my overhead light to fifty percent" -> "All set - 50 percent"; "That'll be all for now, thank you." -> end_call ok:true | wake HIT |

So the two phrases untested earlier are now tested: **"End the conversation" and "We're done" both ended on the first try.**

## 1. Mid-response cut-out at 01:04 (not the fan, not the network)
`rt_7schnxd2` ended with `component_unmount` 3.6 s after the coordinator's own merge of RQ-040 into the checkout that the Room 214 page is served from (`deviceAmbiguity.js` written 20:04:13.296 CDT = 01:04:13.296 UTC; unmount 01:04:16.94). The page is the CRA **dev server**, so changed files hot-reload and remount the call component, killing the live session; the page then started a new session on its own (`rt_0rm7tpvq`, no wake). Cause: a deployment practice defect (live endpoint served from a hot-reloading dev server), not hardware. Mitigations: do not merge frontend changes while a call is live (the coordinator now checks `resident_aria_leases` first); serve a production build to the Room 214 page (queued RQ-043).

## 2. "hay area" false wake
Detector event 01:06:23.704 (`wake_detected`) -> session opened. The lab predicted this class: with the live setting (threshold 0.05 / score 1.5) the offline adversarial set woke on "hay area" 5 times and "hey area" 6 times out of 952 phrases (score 1.0 would be 3 / 4; same threshold). Owner-observed, 1 instance; no long-duration rate exists. The garbled turns after the wake were the tail of the sentence, not a command. No retune made (owner instruction). Options for the owner to choose between, none applied:
- Score 1.0 at threshold 0.05: fewer "area" wakes (3/4 vs 5/6 of the synthetic set) with recall 70% vs 75% (far-field 63 vs 74 of 132).
- A local second-stage check on a short audio ring buffer (needs temporary local clip storage: owner decision).
- More real-room attempts logged with `mark` so the live miss rate is measured before any change.

## 3. Failures to end the conversation
- First attempted ending in `rt_zu1x1e37`: no `end_call` tool call exists. The transcript of the owner's sentence is garbled ("Alfredo." / "Фредерик" / "Oi"); the model improvised a farewell ("Goodnight, Michael...") without calling the tool, so the session stayed open. Model behaviour on a garbled turn; nothing hung up, so no hang-up claimed.
- Second attempt "Goodnight, goodbye.": `end_call` was called and refused with the suspect-turn message. The turn was classified `uncertain_fragment` (<= 2 words, speech began while Aria was still talking), which triggers the suspect-turn refusal before the phrase list is consulted. The words match the ending list, so this is a guard-ordering defect. Fix queued (RQ-041): accept a turn flagged only `uncertain_fragment` when it matches the ending list; echo-like turns still refuse.
- Third attempt "Yes, I want to end our conversation." ended normally after the model's own confirmation.
- Elsewhere in the window all other endings were first-try (4 of 4).

## 4. Microphone relocation
The `audio_level` logging exists only since 01:08:14 UTC, i.e. after the move; the earlier placement has no level data. After the move the noise floor is -65 to -72 dBFS and speech peaks are -7 to -18 dBFS (strong). There is no instrument comparison of before vs after, so no improvement is claimed. Wake outcomes before/after: owner reported 2 responses from 3 attempts at ~8 ft (logged hits 00:57:38 and 00:59:10; the missed attempt is not in any log); after the move 2 intentional wakes and 1 false wake were logged. Counts are too small to compare.

## Denominators
Instrument-proven: 5 detections in this window (00:57:38, 00:59:10, 01:04:03, 01:06:23, 01:08:52), of which 1 false wake ("hay area", owner-identified). Owner-reported only: 3 attempts at 8 ft, 2 responses. Misses and non-wake utterances ("now we'll try to say Aria") are not counted as missed attempts.
