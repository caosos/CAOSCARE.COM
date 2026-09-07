/**
 * useRealtimeVoice — full-duplex voice via OpenAI Realtime API + WebRTC.
 *
 * Browser ↔ OpenAI directly stream audio over WebRTC. Backend mints an
 * ephemeral session token and forwards SDP. Audio never touches our server.
 *
 * Connection setup (mint, mic, peer connection, session.update/greeting,
 * SDP negotiation) lives in realtimeConnection.js. Reacting to what OpenAI sends back - tool
 * calls, transcripts, VAD events - lives in realtimeMessageHandler.js
 * (dc.onmessage = onMessage below). Split 2026-08-22 to keep this file
 * under the repo's 300-line cap as it grew.
 *
 * StrictMode-safe: every start() carries a generation token. If a teardown
 * happens mid-flight (StrictMode mount→unmount→remount, or user end-call
 * during connect), we bump the generation and the in-flight start exits
 * cleanly without leaving orphan peer connections — that's what caused the
 * earlier "two voices back-to-back" bug.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { API } from "../lib/api";
import { logRealtimeEvent } from "./realtimeDiagnostics";
import { connectRealtimeVoice } from "./realtimeConnection";

const REASON_TO_ARIA_EVENT = {
    resident_end_call: "dismissed", resident_end_conversation: "dismissed",
    companion_timeout: "timeout", ui_end_call_button: "dismissed",
  };

export function useRealtimeVoice({
  voice = "shimmer", residentId, kioskId, room, onEndCall,
  sessionEndpoint = "/realtime/session", sessionPayload, triggerSource, alertId, activationId,
} = {}) {
  const attemptRef = useRef(null);
  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const audioElRef = useRef(null);
  const localStreamRef = useRef(null);
  const leaseHeartbeatRef = useRef(null);   // cooperative room-lease watchdog
  const leaseRoomRef = useRef(null);        // exact room/session claim owned by this attempt
  const startGenRef = useRef(0);            // bumps on every stop() — invalidates in-flight starts
  const ctxRef = useRef({ resident_id: residentId, kiosk_id: kioskId, room, alert_id: alertId, activation_id: activationId });
  // true while Aria's audio is actually playing - driven by output_audio_buffer
  // events (real playback lifecycle), not response.done (generation-complete
  // only) - see realtimeMessageHandler.js.
  const assistantSpeakingRef = useRef(false);
  // Raw overlap bool while a turn is in flight; realtimeMessageHandler.js's
  // classifyUserTurn() replaces it with { suspect, reason } once the
  // transcript resolves - overlap is one signal, not the verdict.
  const turnSuspectRef = useRef(false);
  const greetingCreateResponseOffRef = useRef(false); // true while the initial forced greeting is in flight
  const restingRef = useRef(false);         // live mirror of `resting` state - onMessage's closure can't see live state
  const lifecycleCleanupRef = useRef(null);   // detaches attachLifecycleDiagnostics' listeners
  const endReasonLoggedRef = useRef(false);   // one termination reason per session, first cause wins
  const sessionIdRef = useRef(`rt_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`);
  // Level 1 resident-assistance event (2026-09-06): the open Alert this
  // session belongs to, if any (kiosk passes it from its active-emergency
  // poll's a.alert_id). Lets Aria's lifecycle transitions - activated,
  // dismissed, timeout, silence-after-invite - be recorded on the SAME
  // event repeat presses attach to (routes/resident_activation.py).
  const companionTimeoutTimerRef = useRef(null);
  const inviteSilenceTimerRef = useRef(null);
  const firstSpeechHeardRef = useRef(false);
  // Generic "ring if the resident says nothing before this fires" watch -
  // used for the live-line routing question's own silence timeout
  // (realtimeCareControl.js), separate from the once-per-session invite
  // timer above since it can be (re)armed mid-conversation.
  const awaitingAnswerTimerRef = useRef(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState(null);
  const [transcript, setTranscript] = useState([]);
  const [resting, setResting] = useState(false);
  const [micLabel, setMicLabel] = useState(null);   // human-readable input device name, once known

  // Keep tool-call context fresh if the parent passes new props mid-call
  useEffect(() => {
    ctxRef.current = { ...ctxRef.current, resident_id: residentId, kiosk_id: kioskId, room, alert_id: alertId, activation_id: activationId };
  }, [residentId, kioskId, room, alertId, activationId]);

  // Best-effort - never blocks the session on a failed POST. `alert_id` is
  // absent for non-alert-linked sessions (e.g. Michael's own operator
  // Aria build via /aria-session), in which case this silently no-ops.
  const postAriaEvent = useCallback((event, utterance) => {
    const id = ctxRef.current?.alert_id;
    if (!id) return;
    return fetch(`${API}/alerts/${encodeURIComponent(id)}/aria-event`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      keepalive: true,
      body: JSON.stringify({ event, utterance: utterance || null,
        session_id: ctxRef.current.session_id, activation_id: ctxRef.current.activation_id }),
    }).catch(() => {});
  }, []);

  const clearLifecycleTimers = () => {
    if (companionTimeoutTimerRef.current) { clearTimeout(companionTimeoutTimerRef.current); companionTimeoutTimerRef.current = null; }
    if (inviteSilenceTimerRef.current) { clearTimeout(inviteSilenceTimerRef.current); inviteSilenceTimerRef.current = null; }
    if (awaitingAnswerTimerRef.current) { clearTimeout(awaitingAnswerTimerRef.current); awaitingAnswerTimerRef.current = null; }
  };

  // Passed down to realtimeMessageHandler.js so the live-line routing
  // question (realtimeCareControl.js) can arm "ring if they don't answer."
  // Cleared by ANY subsequent speech, not just the session's first.
  const startAwaitingAnswerTimer = useCallback((seconds, onTimeout) => {
    if (awaitingAnswerTimerRef.current) clearTimeout(awaitingAnswerTimerRef.current);
    awaitingAnswerTimerRef.current = setTimeout(() => {
      awaitingAnswerTimerRef.current = null;
      onTimeout();
    }, (seconds ?? 30) * 1000);
  }, []);

  // 2026-08-23: every session now ends with a known reason, logged once
  // (first cause wins) - "unknown" only when the platform genuinely gives
  // no evidence. Shared between stop() itself and the read-only lifecycle
  // listeners below, so an unexpected drop gets a real cause even when
  // nobody explicitly called stop().
  const logSessionEnded = useCallback((reason) => {
    if (endReasonLoggedRef.current) return;
    endReasonLoggedRef.current = true;
    logRealtimeEvent(sessionIdRef.current, "session_ended", { meta: { reason } });
  }, []);

  // Shared by stop() and start()'s failure path — best-effort, never blocks.
  const releaseLease = (targetRoom, targetSession, context = {}) => {
    if (!targetRoom || !targetSession) return;
    fetch(`${API}/realtime/room/${encodeURIComponent(targetRoom)}/release`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: targetSession, ...context }), keepalive: true,
    }).catch(() => {});
  };

  const stop = useCallback((reason = "unspecified") => {
    if (pcRef.current || dcRef.current) logSessionEnded(reason);
    // Level 1 (2026-09-06): only meaningful, resident-caused endings get
    // recorded on the event - a component unmount, config error, or
    // canceled in-flight start isn't a real "Aria dismissed herself" fact.
    if (attemptRef.current) attemptRef.current.cancelReason = reason;
    const ended = REASON_TO_ARIA_EVENT[reason] ? postAriaEvent(REASON_TO_ARIA_EVENT[reason]) : null;
    clearLifecycleTimers();
    try { lifecycleCleanupRef.current?.(); } catch {}
    lifecycleCleanupRef.current = null;
    startGenRef.current += 1;               // cancel any pending start()
    try { dcRef.current?.close(); } catch {}
    try { pcRef.current?.getSenders().forEach((s) => s.track && s.track.stop()); } catch {}
    try { pcRef.current?.close(); } catch {}
    try { localStreamRef.current?.getTracks().forEach((t) => t.stop()); } catch {}
    try { if (audioElRef.current) audioElRef.current.srcObject = null; } catch {}
    pcRef.current = null;
    dcRef.current = null;
    localStreamRef.current = null;
    if (leaseHeartbeatRef.current) { leaseHeartbeatRef.current.close(); leaseHeartbeatRef.current = null; }
    // Free the room immediately rather than waiting out the stale grace
    // period, so the next trigger (pendant/manual) can claim right away.
    if (leaseRoomRef.current) {
      const claim = leaseRoomRef.current;
      const context = { alert_id: ctxRef.current.alert_id, activation_id: ctxRef.current.activation_id, reason };
      Promise.resolve(ended).then(() => releaseLease(claim.room, claim.sessionId, context));
      leaseRoomRef.current = null;
    }
    setStatus("idle");
    setResting(false);
    setMicLabel(null);
  }, [logSessionEnded, postAriaEvent]);

  useEffect(() => () => stop("component_unmount"), [stop]);

  const start = useCallback(() => connectRealtimeVoice({
    attemptRef, voice, residentId, kioskId, room, alertId, activationId, sessionEndpoint,
  sessionPayload, triggerSource, onEndCall, pcRef, dcRef, localStreamRef,
  audioElRef, leaseHeartbeatRef, leaseRoomRef, startGenRef, sessionIdRef,
  ctxRef, endReasonLoggedRef, lifecycleCleanupRef, assistantSpeakingRef,
  turnSuspectRef, greetingCreateResponseOffRef, restingRef, firstSpeechHeardRef,
  awaitingAnswerTimerRef, inviteSilenceTimerRef, companionTimeoutTimerRef,
  setStatus, setError, setMicLabel, setResting, setTranscript,
  stop, releaseLease, postAriaEvent, startAwaitingAnswerTimer, logSessionEnded
  }), [voice, residentId, kioskId, room, alertId, activationId, sessionEndpoint,
    sessionPayload, triggerSource, onEndCall, stop, postAriaEvent, logSessionEnded, startAwaitingAnswerTimer]);

  return { status, error, transcript, resting, micLabel, start, stop, audioElRef };
}
