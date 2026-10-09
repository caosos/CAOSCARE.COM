# Room 214 call forensics: session `rt_3ctpadu5_1791588223558` (owner item da-d668d86fd0)

Read-only. Sources: `db.realtime_diagnostics` (event-only), `db.resident_aria_lease_events`, `db.resident_aria_leases`, wake listener journal (`aria-wake.service`), the built Room page in `~/.cache/aria-wake/build`. No audio, no raw recording; transcripts only as already stored by the system. Times are CDT (UTC-5).

## Which call
The owner's test (about 18:20-18:25 CDT) is this session: wake "Hey Aria" at **18:23:43**, connected 18:23:44, ended **18:27:26**. The earlier `rt_t07bct8g` (17:49-17:57) is a different call. `rt_3ctpadu5` is the only session between 17:57 and now.

## Timeline (seconds from connect; source: realtime_diagnostics)
| t | Event |
|---|---|
| 0.9 | peer + ICE connected; Aria greets |
| 11.7 | owner's words transcribed as Arabic text; Aria: "not sure I caught that" |
| 68-71 | transcript "issue." (a misheard goodbye is the likely reading, unproven). Aria SAYS "Understood. I'll end the call now. Take care" then calls `end_call`; the guard **refused** it (`ok:false`, transcript had no ending phrase). |
| 73-76 | Aria: "I want to make sure I understood", then "no problem, I'll stay right here" |
| 171 | "Are you still there, Aria?" -> "I'm right here" (call ACTIVE and listening) |
| 183-188 | owner says "Aria." repeatedly. Twice `response_created` then `response_done` with **no transcript and no audio**; each time a new `speech_started` landed 0.2 s later. The reply was cancelled by his next speech, so he heard nothing ("you didn't say anything"). |
| 204 | `request_staff_help` created an administration request (the investigation request) |
| 217.3 | "That'll be all for now." transcribed correctly -> `end_call` granted -> goodbye spoken |
| 221.6 | `session_ended` reason `resident_end_call` (18:27:26) |
After: lease event `released` 18:27:26; `resident_aria_leases` is empty now; listener journal `mode_listening (call_state_idle)` 18:27:26. Final state: **ENDED**, wake listener re-armed (verified from those three records). Mic-track stop is not logged separately; it runs inside the same `stop()` that wrote `session_ended` (inferred).

## Findings
1. The call really was open from 18:23:43 until 18:27:26, so the owner's observation was right. It ended only when a phrase happened to transcribe correctly. Same root cause as before (mis-transcribed short commands refused by the transcript guard), plus a new bad behavior: Aria **announced "I'll end the call now"** while the tool was refused.
2. "Aria" alone not answering is not "not listening": the call was live (171 s answer). Two replies were created and cancelled by the owner's next utterance. "Aria" alone also does not re-wake a finished call (only "Hey Aria"); that is by design.
3. **The live Room page does not have the fix.** The served bundle `main.6c585537.js` was built 2026-10-08 23:07 CDT (commit 1eb5395). It contains 0 occurrences of `local_end` / `end_call_corroborated` (RQ-055, merged 2026-10-09 18:04, `60dfb80`). Nothing has rebuilt the page since, so tonight's behavior is the old code. This session ended through the old path only.
4. Not verified: what the owner actually said at 68 s ("issue." is only the transcript); WebRTC torn-connection and watchdog events (none logged); mic stop as a separate record.

## What the new code would have done here
* a clear "Goodbye"/"End the call" transcript: ends at once (local); "issue." is Latin script with no ending phrase, so the first model `end_call` is still questioned, the second (within 90 s) is granted; an Arabic/Korean-script transcript (like the 11.7 s one) is granted on the first. Spoken "I'll end the call now" before a refused tool call is not changed (prompt-level, open).

## Next safe step
Rebuild + restart-page of the Room page needs the owner's one-time authorization: `docs/ROOM_PAGE_REBUILD_RUNBOOK.md`. Not done.
