# Goodbye test forensics, Room 214, 2026-10-10 01:00-01:05Z (= 2026-10-09 20:00-20:05 CDT)

Read-only; sources `realtime_diagnostics`, `resident_aria_lease_events`, wake listener journal. Page build in use: `main.98a48c6f.js` (commit e15d59f, silent local end). The next rebuild (ca4a32c) happened after these sessions' predecessor tests; sessions below ran on the first rebuild. No newer session exists after 01:04:09Z.

| Session | Wake detected | Goodbye heard | Goodbye audio | Closed / lease released / listener |
|---|---|---|---|---|
| `rt_7meejjg3_1791594050315` | 01:00:50.30 | 01:01:03.1 "Goodbye." (explicit) | **none** | `session_ended` 01:01:07.87, lease released 01:01:07.874, `mode_listening` 01:01:07.868 |
| `rt_vzqg61fa_1791594123617` | 01:02:03.61 | 01:02:35.7 "Goodbye" | played 01:02:36.2-01:02:38.8 | ended 01:02:39.30, released 01:02:39.302, listening 01:02:39.299 |
| `rt_whcs4b1d_1791594235883` | 01:03:55.88 | 01:04:05.3 "Goodbye." | played 01:04:06.7-01:04:09.4 | ended 01:04:09.81, released 01:04:09.820, listening 01:04:09.814 |

Answers:
1. **Ended?** Yes, every session: `session_ended` + lease `released` + listener `mode_listening` within 10 ms.
2. **end_call / lease?** These ended through the local goodbye path (`local_end` on the transcript "Goodbye."), closed by the hang-up scheduler; leases were released each time.
3. **Closing speech?** Session 1: **not played**. The server's own reply to the utterance was already in flight (`response_created` 12.46 s); the page cancelled it and requested the goodbye at once, the goodbye response (13.08-13.71 s) produced no audio, and the page closed 3 s later: a silent stop (what the owner heard). Sessions 2 and 3: played about 2.6 s, closed 0.4 s after it stopped. The goodbye text was also not recorded in the transcript log (ignored while closing).
4. **Another wake?** Exactly three `wake_detected`, each immediately before a lease claim; none during or after a goodbye.
5. **"Are you still there?"**: session 2 was still ACTIVE (started 01:02:04, no goodbye until 01:02:35). The question at 01:02:28.7 was answered by a live call. Session 1 had ended at 01:01:07 and session 2 started from a new "Hey Aria" at 01:02:03.6 with a greeting ("Good evening, Michael. I'm here."), which is easy to miss. Not a response after an ended call.

## Cause and fix (RQ-058, code only, not live)
Cause of the silent stop: the goodbye request collided with a reply already in flight. Fix: cancel the in-flight reply, request the goodbye only after that reply finishes, retry once if no audio, and if no goodbye audio ever plays, say a local "Goodbye." (browser speech) before closing; record the goodbye transcript; log `call_closed` with `goodbye_audio_played` / `local_fallback_used`.
