/**
 * Realtime server-event reaction layer - split out of useRealtimeVoice.js
 * (2026-08-22) to keep that file from growing further, per the standing
 * <300-line rule. Owns tool-call dispatch (executeTool, handleFunctionCall)
 * and the full data-channel message handler. useRealtimeVoice.js owns
 * connection setup (mint, mic, peer connection, session.update/greeting,
 * SDP negotiation) and calls dc.onmessage = onMessage.
 *
 * Trust-boundary invariants this file maintains (Room 202 forensics,
 * 2026-08-22):
 *   - assistantSpeakingRef reflects actual audio PLAYBACK, via
 *     output_audio_buffer.started/stopped/cleared, not response.done
 *     (generation-complete only - was blind while Aria's audio was still
 *     physically playing).
 *   - Every real transcript is saved independently via postTurn() the
 *     moment it's known - no scalar "pending" ref that a later turn could
 *     silently overwrite before the first was ever persisted.
 *   - end_call/end_conversation only actually tear down the connection
 *     when the underlying tool call succeeded (ok:true) - a suspect turn
 *     gets a spoken confirmation instead of silently ending the session.
 */
import { API } from "./api";
import { executeOperationsTool } from "./realtimeOperationsTools";
import { executeDeviceTool } from "./realtimeDeviceTools";
import { logRealtimeEvent, transcriptionConfidence, LOW_CONFIDENCE_THRESHOLD } from "./realtimeDiagnostics";
import { createConversationTempoController } from "./realtimeConversationTempo";

// Dispatches a model-emitted function call to whichever tool module handles
// it (staff/transportation requests, then device/environment/profile
// tools), falling back to "not wired yet" if neither claims the name.
// Designed so a missing room or device fails gracefully (the model says "I
// couldn't reach the AC, I'll let the nurse know") instead of throwing the
// whole session.
// 2026-08-23 (Room 304 forensic report): overlap timing alone falsely
// flagged genuine barge-in as suspect - 7 of ~11 overlap-flagged turns in
// that session were coherent, on-topic resident statements, not echo. A
// resident is allowed to interrupt Aria on purpose. Overlap is now ONE
// piece of evidence, combined with two more that are actually available
// (segment length, textual resemblance to what Aria just said) plus a
// short-term streak of tiny overlapping fragments - not a fabricated
// confidence score, three explicit, traceable checks. Ambient-silence
// phantoms (no overlap at all) are deliberately untouched here - separate,
// still-open issue per the incident report.
function classifyUserTurn({ overlapped, text, lastAssistantText, tinyStreak }) {
  if (!overlapped) return { suspect: false, reason: "no_overlap" };
  const trimmed = (text || "").trim();
  const wordCount = trimmed.split(/\s+/).filter(Boolean).length;
  const isTiny = wordCount <= 2 || !/[a-zA-Z]/.test(trimmed);
  if (!isTiny) {
    // Coherent multi-word statement while Aria was talking - real,
    // deliberate barge-in. Overlap alone isn't reason to distrust it.
    return { suspect: false, reason: "coherent_barge_in" };
  }
  const resemblesAssistant = !!lastAssistantText &&
    lastAssistantText.toLowerCase().includes(trimmed.toLowerCase().replace(/[.,!?]/g, ""));
  if (resemblesAssistant || tinyStreak >= 2) {
    return { suspect: true, reason: resemblesAssistant ? "echo_like" : "repeated_tiny_fragments" };
  }
  return { suspect: true, reason: "uncertain_fragment" };
}

async function executeTool({ name, args, ctx }) {
  try {
    const opsResult = await executeOperationsTool({ name, args, ctx: { room: ctx?.room, residentId: ctx?.resident_id, sessionId: ctx?.session_id, turnSuspect: ctx?.turn_suspect, turnSuspectReason: ctx?.turn_suspect_reason } });
    if (opsResult) return opsResult;
    const deviceResult = await executeDeviceTool({ name, args, ctx });
    if (deviceResult) return deviceResult;
    return { ok: false, message: `tool ${name} is not wired yet.` };
  } catch (e) {
    return { ok: false, message: `tool error: ${e?.message || "unknown"}.` };
  }
}

export function createRealtimeHandlers({
  myGen, startGenRef, sessionIdRef, ctxRef, send, stop, onEndCall,
  turnSuspectRef, assistantSpeakingRef,
  greetingCreateResponseOffRef,
  setStatus, setResting, setTranscript, setError,
}) {
  // Closure-local, not refs - createRealtimeHandlers runs once per
  // connection and these handlers persist for its lifetime, same as any
  // ref would, without threading more state through useRealtimeVoice.js.
  let lastAssistantText = "";
  let tinyFragmentStreak = 0;
  // 2026-08-24 (Room 404 forensics, Issue #22): diagnostic-only timing -
  // VAD segment duration and time since Aria's audio genuinely stopped.
  // Logged only, no classification behavior change.
  let lastSpeechStartedAt = null;
  let lastSpeechSegmentMs = null;
  let lastPlaybackStoppedAt = null;
  const turnTempo = createConversationTempoController({ send, sessionIdRef, ctxRef });

  // Saves one turn immediately, independently - no pairing, no waiting on
  // the other side of the exchange. See RealtimeTurnIngest's docstring
  // (routes/realtime_memory_ingest.py) for the real data-loss bug this
  // replaced: a scalar "pending" ref could be overwritten by a second
  // user segment before the first was ever saved.
  const postTurn = (role, text, itemId, trusted) => {
    if (!text) return;
    const rid = ctxRef.current?.resident_id;
    const ownerId = ctxRef.current?.owner_user_id;
    if (rid) {
      fetch(`${API}/memory/realtime-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          resident_id: rid, session_id: sessionIdRef.current, role, text,
          trusted, item_id: itemId || null,
          room: ctxRef.current?.room || null, kiosk_id: ctxRef.current?.kiosk_id || null,
        }),
      }).catch(() => {});
    } else if (ownerId) {
      // Aria's own (operator) sessions - same immediate per-turn pattern.
      fetch(`${API}/aria/conversation-turn`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ owner_user_id: ownerId, session_id: sessionIdRef.current, role, content: text }),
      }).catch(() => {});
    }
  };

  // Helper: dispatch a tool call coming from the model
  const handleFunctionCall = async (fn) => {
    let parsed = {};
    try { parsed = fn.arguments ? JSON.parse(fn.arguments) : {}; } catch {}
    logRealtimeEvent(sessionIdRef.current, "tool_call", { meta: { name: fn.name } });
    const cls = turnSuspectRef.current || { suspect: false, reason: "no_overlap" };
    const result = await executeTool({ name: fn.name, args: parsed, ctx: { ...ctxRef.current, turn_suspect: cls.suspect, turn_suspect_reason: cls.reason } });
    if (myGen !== startGenRef.current) return;
    // Tell the model what happened. The output goes onto the conversation
    // as a `function_call_output` item, then we ask the model to respond.
    send({
      type: "conversation.item.create",
      item: {
        type: "function_call_output",
        call_id: fn.call_id,
        output: JSON.stringify(result),
      },
    });
    if (fn.name === "mark_resting") {
      // Resident asked us to be quiet. Don't trigger a new spoken response;
      // the model will stay silent until VAD detects fresh speech.
      setResting(true);
    } else if (fn.name === "end_call" || fn.name === "end_conversation") {
      // 2026-08-22 (real bug, confirmed live): a phantom echo turn ("and")
      // reached this branch and hung up on the resident mid-session.
      // end_call/end_conversation are NOT emergency actions, so only tear
      // down when the tool actually succeeded - realtimeDeviceTools.js now
      // refuses (ok:false, asks for confirmation instead) when the
      // triggering turn was flagged suspect.
      send({ type: "response.create" });
      if (result.ok) {
        setTimeout(() => {
          try { stop(fn.name === "end_call" ? "resident_end_call" : "resident_end_conversation"); } catch {}
          try { onEndCall?.(); } catch {}
        }, 2500);
      }
    } else {
      // Ask the model to speak its short confirmation, drawing on the tool result.
      send({ type: "response.create" });
    }
  };

  const onMessage = (ev) => {
    if (myGen !== startGenRef.current) return;
    let msg;
    try { msg = JSON.parse(ev.data); } catch { return; }

    if (msg.type === "input_audio_buffer.speech_started") {
      setStatus("listening");
      setResting(false);   // resident spoke again → wake from rest
      // Raw overlap signal - did this segment start while Aria's audio was
      // still playing? One piece of evidence, not the verdict - see
      // classifyUserTurn() above, applied once the transcript resolves.
      turnSuspectRef.current = assistantSpeakingRef.current;
      turnTempo.speechStarted({ itemId: msg.item_id });
      lastSpeechStartedAt = Date.now();
      logRealtimeEvent(sessionIdRef.current, "speech_started", { assistantSpeaking: assistantSpeakingRef.current });
    }
    if (msg.type === "input_audio_buffer.speech_stopped") {
      setStatus("live");
      lastSpeechSegmentMs = lastSpeechStartedAt ? Date.now() - lastSpeechStartedAt : null;
      turnTempo.speechStopped({ itemId: msg.item_id, overlapped: turnSuspectRef.current === true });
      logRealtimeEvent(sessionIdRef.current, "speech_stopped", { assistantSpeaking: assistantSpeakingRef.current });
    }
    if (msg.type === "response.audio.delta") {
      setStatus("speaking");
    }
    // 2026-08-22 (real bug, confirmed live via Room 202 forensics):
    // assistantSpeakingRef used to flip false on response.done, which is
    // generation-complete, not audio-playback-complete. A multi-second
    // reply keeps physically playing through the speaker well after
    // response.done fires, so the trust boundary was blind during that
    // window - three of five phantom turns in one session started 1-1.4s
    // after response.done, almost certainly while Aria's own audio was
    // still audible. output_audio_buffer.started/stopped/cleared are real
    // server events sent specifically for WebRTC/SIP connections (verified
    // against an OpenAI team member's direct confirmation, not guessed -
    // they do NOT exist on plain WebSocket, which is why this was missed
    // before) and track actual playback lifecycle, not generation.
    if (msg.type === "output_audio_buffer.started") {
      assistantSpeakingRef.current = true;
      // Logged standalone (2026-08-24) - was only folded into other events.
      logRealtimeEvent(sessionIdRef.current, "output_audio_buffer_started", {});
    }
    if (msg.type === "output_audio_buffer.stopped" || msg.type === "output_audio_buffer.cleared") {
      // .cleared covers a genuine interruption cutting playback short -
      // either way, Aria's audio is no longer physically playing.
      assistantSpeakingRef.current = false;
      lastPlaybackStoppedAt = Date.now();
      logRealtimeEvent(sessionIdRef.current, "output_audio_buffer_stopped", { meta: { cleared: msg.type === "output_audio_buffer.cleared" } });
      // create_response stays false for the whole call now; the tempo
      // controller decides when the user has actually yielded the floor.
      if (greetingCreateResponseOffRef.current) greetingCreateResponseOffRef.current = false;
    }
    if (msg.type === "response.done") {
      setStatus("live");
      logRealtimeEvent(sessionIdRef.current, "response_done", { responseId: msg.response?.id });
    }
    if (msg.type === "response.created") {
      turnTempo.responseCreated();
      logRealtimeEvent(sessionIdRef.current, "response_created", { responseId: msg.response?.id });
    }
    if (msg.type === "conversation.item.input_audio_transcription.completed") {
      const userText = msg.transcript || "";
      setTranscript((t) => [...t, { role: "user", text: userText, ts: Date.now() }]);
      // logprobs -> confidence, when the API actually returns them (it
      // currently doesn't over this path - Room 304 showed 0/34 turns with
      // a non-null value - so this safely no-ops until that changes).
      const confidence = transcriptionConfidence(msg.logprobs);
      const lowConfidence = confidence !== null && confidence < LOW_CONFIDENCE_THRESHOLD;
      const overlapped = turnTempo.wasOverlapped(msg.item_id) || lowConfidence;
      const cls = classifyUserTurn({ overlapped, text: userText, lastAssistantText, tinyStreak: tinyFragmentStreak });
      tinyFragmentStreak = (cls.reason === "echo_like" || cls.reason === "uncertain_fragment" || cls.reason === "repeated_tiny_fragments") ? tinyFragmentStreak + 1 : 0;
      if (turnTempo.isLatest(msg.item_id)) turnSuspectRef.current = cls;
      turnTempo.classified({ ...cls, itemId: msg.item_id });
      // 2026-08-22 (real bug, confirmed live): saved IMMEDIATELY now, not
      // stashed in a scalar "pending" ref to wait for the assistant reply.
      // A real ~15-second resident correction was silently lost when a
      // second, quicker segment overwrote that ref before the first was
      // ever persisted. Every real turn is now durably saved the moment
      // it's known, independent of whatever arrives next.
      postTurn("user", userText, msg.item_id, !cls.suspect);
      logRealtimeEvent(sessionIdRef.current, "user_transcript", {
        text: userText, assistantSpeaking: cls.suspect,
        meta: {
          confidence, low_confidence: lowConfidence, turn_class_reason: cls.reason,
          speech_segment_ms: lastSpeechSegmentMs,
          ms_since_assistant_stopped: lastPlaybackStoppedAt ? Date.now() - lastPlaybackStoppedAt : null,
        },
      });
    }
    // FIXED 2026-08-09 (real, confirmed bug): the current Realtime API
    // emits this as response.output_audio_transcript.done, not
    // response.audio_transcript.done. Under the old name, Aria's own
    // spoken responses never landed in transcript state at all - only
    // user turns did, which is exactly why a real screenshot showed
    // every transcript line labeled "you" (there simply were no
    // "assistant" entries being added). Found via a full real WebRTC
    // connection test that logged every actual event type/name OpenAI
    // sent, not by guessing.
    if (msg.type === "response.output_audio_transcript.done") {
      const aiText = msg.transcript || "";
      setTranscript((t) => [...t, { role: "assistant", text: aiText, ts: Date.now() }]);
      logRealtimeEvent(sessionIdRef.current, "assistant_transcript", { text: aiText });
      lastAssistantText = aiText; // for classifyUserTurn()'s echo-resemblance check
      // Saved immediately and independently - see the matching comment on
      // the user-transcript handler above for why pairing was removed.
      postTurn("assistant", aiText, msg.item_id);
    }
    // Tool call dispatch — the OpenAI Realtime API streams arguments and
    // emits a single `done` event when the call is fully assembled.
    if (msg.type === "response.function_call_arguments.done") {
      handleFunctionCall({
        call_id: msg.call_id,
        name: msg.name,
        arguments: msg.arguments,
      });
    }
    if (msg.type === "error") {
      // A rejected session.update (bad config) must not leave the UI
      // reading "Live · idle" while a real error is showing - that's
      // exactly the misleading state a real acceptance test caught.
      // Downgrading status here doesn't end the call (audio may still
      // be flowing); it just stops the UI claiming full health.
      setError(msg.error?.message || "Realtime error");
      setStatus("error");
      // 2026-08-24: previously UI-only, invisible to any later DB query.
      logRealtimeEvent(sessionIdRef.current, "realtime_error", { text: msg.error?.message || "unknown" });
    }
  };

  return { handleFunctionCall, onMessage };
}
