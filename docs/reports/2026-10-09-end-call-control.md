# "End the call" must stop Aria (RQ-055, owner P0 da-5fa8c9ef00)

Offline work only: no paid calls, no audio recorded, no service restarted, wake 0.05 / 1.5 and capture settings unchanged.

## 1. What actually happened (session `rt_t07bct8g_1791586152450`, 22:49-22:57 UTC, event-only)
| Time (s) | Transcript the system got | Model action | Result |
|---|---|---|---|
| 231.8 | "Labai ačiū." (Lithuanian) | `end_call` | refused by the transcript guard, Aria asks "are you ready to wrap up?" |
| 241.8 | Arabic text | `end_call` | refused, Aria asks again |
| 250.4 | German text | `end_call` | refused, "we'll keep going" |
| 258 / 435 / 443 | Korean / Japanese / "Emma." | `mark_resting` x3 | asked "go quiet?" each time |
| 451-474 | "The call", "call me", Turkish, Hindi | `end_call` x4 | refused ("Understood. We'll stay right here.") |
| 483.9 | **"Go away."** (correct English) | `end_call` | granted, call ended at 487.7 |

Where it broke: **not** the model (it called `end_call` on every attempt, so it heard the ending), **not** the tool (it worked when the words matched), **not** the teardown (it closed cleanly when granted). The speech-to-text wrote the short English commands as Lithuanian, Arabic, German, Korean, Japanese, Hindi or Turkish. Auto language detection has been on since Terminal 10 (the old pinned `en` was removed so Spanish-learning works). The guard that only allows a hang-up when the **transcript** contains an ending phrase therefore refused 12 genuine requests, and Aria negotiated each time. The older rule "after two refusals, stop asking" made it worse: it told the model to carry on.

## 2. Changes (frontend only, `realtimeMessageHandler.js` + 2 new modules)
1. **Local explicit end intent** (`endIntent.js`): a transcript that is, after filler words, just "end the call", "hang up", "goodbye", "bye", "go away", "end it now", "stop talking", "that's all", "we're done", "good night" (and "adiós", "hasta luego") ends the call in the page, without asking the model to choose a tool. Not triggered by quotes, questions ("Can you end the call?"), negation ("Don't hang up"), "keep talking", sentences longer than four words after filler ("Say goodbye to my wife"), or echo of Aria's own words (`echo_like`, `repeated_tiny_fragments`).
2. **Model corroboration** (`endController.js`): when the transcript is unusable, the model's **second** `end_call` within 90 s on non-echo turns is granted. One lone `end_call` is still questioned once (protects against the 2026-08-22 phantom "and").
3. **One-way ENDING state** (`endController.js`): `endNow()` sends `response.cancel` + `output_audio_buffer.clear`, runs the hook's real `stop()` (data channel, peer connection, microphone tracks, timers, room lease) and the screen's `onEndCall`. It is idempotent. After it, the handler ignores every server event and tool call, so no stale response, greeting or tool can restart the call. A new conversation needs a deliberate new wake ("Hey Aria") or UI start, which builds a new handler. The normal `end_call` path now closes through the same controller.
4. **Owner decision (off by default):** build the page with `REACT_APP_TRANSCRIPTION_LANGUAGE=en` to pin recognition to English. This is the root-cause fix for the gibberish but costs the Spanish-learning case; I did not change the default.

## 3. Verification
Frontend 54 suites / 468 tests; production build compiles. New tests drive the **real** `useRealtimeVoice` hook and the **real** message handler through a faked connection and assert the data channel, peer and microphone tracks are closed:
* a spoken ending closes all three, cancels the response, ignores later events (stale response, tool call, speech);
* repeated stops in one turn and across turns end it once; a UI stop afterwards does nothing more;
* barge-in while Aria speaks still ends; Aria's own goodbye coming back does not;
* quoted / hypothetical / negated / "keep talking" phrases do not end;
* lost transcript: first `end_call` is questioned, second granted, then the 7 s ceiling closes; an immediate third `end_call` is idempotent;
* unmount (page reload) stops the microphone; a new start after an ended call works and the old connection stays dead.
Mutation checks (production code broken, tests must fail): removing the local end call fails 4 tests; removing corroboration fails 1; removing `farewellWatch.onResponseDone` (audit F4) fails 1; removing `claimGuard.onResponseDone` (F2) fails 1. All restored.
Backend untouched (gate not run).

## 4. What still needs the owner
* Rebuild the Room page (`ctl.sh rebuild`, no live lease) to get any of this; nothing changed in the running page.
* One live test, about two minutes: say "Aria, end the call", then "Hey Aria" again and say "goodbye", then say "when I say goodbye you stop" (must NOT end). Also try the pinned-English build if you want the root fix.
* Not covered offline: a real WebRTC disconnect, and the speech-to-text behaviour itself.

## 5. If it ever happens again (no deployment needed)
* On the call screen the **End call** button (top right of the live screen) calls the same `stop()` locally; it works even if the server or the model is unreachable.
* Turn the microphone off at the speakerphone itself if it has a mute switch (not verified here).
* `systemctl --user stop aria-wake.service` stops listening for "Hey Aria" until restarted.
