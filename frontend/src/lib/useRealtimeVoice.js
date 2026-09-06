/**
 * useRealtimeVoice — full-duplex voice via OpenAI Realtime API + WebRTC.
 *
 * Browser ↔ OpenAI directly stream audio over WebRTC. Backend mints an
 * ephemeral session token and forwards SDP. Audio never touches our server.
 *
 * Connection setup (mint, mic, peer connection, session.update/greeting,
 * SDP negotiation) lives here. Reacting to what OpenAI sends back - tool
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
import { createRealtimeHandlers } from "./realtimeMessageHandler";
import { attachLifecycleDiagnostics } from "./realtimeLifecycleDiagnostics";
import { buildSessionUpdate } from "./realtimeSessionUpdate";

export function useRealtimeVoice({
  voice = "shimmer", residentId, kioskId, room, onEndCall,
  sessionEndpoint = "/realtime/session", sessionPayload, triggerSource, alertId,
} = {}) {
  const pcRef = useRef(null);
  const dcRef = useRef(null);
  const audioElRef = useRef(null);
  const localStreamRef = useRef(null);
  const leaseHeartbeatRef = useRef(null);   // interval id for the room-lease heartbeat, when room-scoped
  const leaseRoomRef = useRef(null);        // room this session actually claimed a lease for, if any
  const startGenRef = useRef(0);            // bumps on every stop() — invalidates in-flight starts
  const ctxRef = useRef({ resident_id: residentId, kiosk_id: kioskId, room, alert_id: alertId });
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
    ctxRef.current = { ...ctxRef.current, resident_id: residentId, kiosk_id: kioskId, room, alert_id: alertId };
  }, [residentId, kioskId, room, alertId]);

  // Best-effort - never blocks the session on a failed POST. `alert_id` is
  // absent for non-alert-linked sessions (e.g. Michael's own operator
  // Aria build via /aria-session), in which case this silently no-ops.
  const postAriaEvent = useCallback((event, utterance) => {
    const id = ctxRef.current?.alert_id;
    if (!id) return;
    fetch(`${API}/alerts/${encodeURIComponent(id)}/aria-event`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, utterance: utterance || null }),
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
  const releaseLease = (targetRoom, targetSession) => {
    fetch(`${API}/realtime/room/${encodeURIComponent(targetRoom)}/release`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: targetSession }),
    }).catch(() => {});
  };

  const REASON_TO_ARIA_EVENT = {
    resident_end_call: "dismissed", resident_end_conversation: "dismissed",
    companion_timeout: "timeout",
  };

  const stop = useCallback((reason = "unspecified") => {
    if (pcRef.current || dcRef.current) logSessionEnded(reason);
    // Level 1 (2026-09-06): only meaningful, resident-caused endings get
    // recorded on the event - a component unmount, config error, or
    // canceled in-flight start isn't a real "Aria dismissed herself" fact.
    if (REASON_TO_ARIA_EVENT[reason]) postAriaEvent(REASON_TO_ARIA_EVENT[reason]);
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
    if (leaseHeartbeatRef.current) { clearInterval(leaseHeartbeatRef.current); leaseHeartbeatRef.current = null; }
    // Free the room immediately rather than waiting out the stale grace
    // period, so the next trigger (pendant/manual) can claim right away.
    if (leaseRoomRef.current) {
      releaseLease(leaseRoomRef.current, sessionIdRef.current);
      leaseRoomRef.current = null;
    }
    setStatus("idle");
    setResting(false);
    setMicLabel(null);
  }, [logSessionEnded]);

  useEffect(() => () => stop("component_unmount"), [stop]);

  const start = useCallback(async () => {
    if (pcRef.current) return;              // already connected
    const myGen = ++startGenRef.current;
    sessionIdRef.current = `rt_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`;
    ctxRef.current = { ...ctxRef.current, session_id: sessionIdRef.current };
    endReasonLoggedRef.current = false;

    setError(null);
    setStatus("connecting");
    let pc = null;
    let stream = null;
    try {
      // 1. Mint ephemeral session — also claims this room's server-side
      // singleton lease (see realtime_room_lease.py). session_id here is
      // reused as the lease's own id, so heartbeat/release below can
      // reference it without a second identifier.
      const sessionRes = await fetch(`${API}${sessionEndpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          sessionPayload || {
            voice,
            resident_id: residentId || null,
            kiosk_id: kioskId || null,
            room: room || null,
            alert_id: alertId || null,
            session_id: sessionIdRef.current,
            trigger_source: triggerSource || "manual_kiosk",
          }
        ),
      });
      if (myGen !== startGenRef.current) return;   // canceled
      if (!sessionRes.ok) {
        // 2026-09-01: a public demo visitor was shown the raw "session 503"
        // Error.message straight in the UI. Real status/detail still goes
        // to diagnostics, just not as the resident-facing text.
        let detail = null;
        try { detail = (await sessionRes.json())?.detail || null; } catch {}
        logRealtimeEvent(sessionIdRef.current, "session_mint_failed", { meta: { status: sessionRes.status, detail } });
        throw new Error("Voice is temporarily unavailable. Try again.");
      }
      const session = await sessionRes.json();
      if (myGen !== startGenRef.current) return;
      const caos = session._caos || {};
      // Room already owned by another live session — never touch the mic.
      // Not an error: reflect it as its own status so the UI can show
      // "already talking with someone" instead of a red error banner.
      if (caos.lease && caos.lease.claimed === false) {
        logRealtimeEvent(sessionIdRef.current, "lease_not_claimed", { meta: caos.lease });
        setStatus("unavailable");
        return;
      }
      if (caos.lease && caos.lease.claimed === true && room) leaseRoomRef.current = room;
      // /realtime/client_secrets (the endpoint the backend calls) returns the
      // ephemeral key as a top-level `value`, not nested under `client_secret`
      // — that older shape belongs to the legacy /realtime/sessions endpoint.
      const ephemeral = session?.value || session?.client_secret?.value;
      if (!ephemeral) throw new Error("no ephemeral key");
      // Backend authority on context — overrides whatever the parent passed
      if (caos.context) ctxRef.current = { ...ctxRef.current, ...caos.context };

      // 2. Mic capture (full-duplex: track stays live for the whole session)
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      if (myGen !== startGenRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        return;
      }
      // Record what the browser actually reports about the mic track (not
      // the OS input-level slider - the Web platform does not expose that
      // at all, so don't pretend to). Diagnostic only, read-only, doesn't
      // touch the audio path.
      // 2026-08-29: getSettings() alone only gives an opaque per-origin
      // deviceId hash - Michael: "the eMeet is great but you can't tell on
      // CAOSCare" - there was no human-readable device name captured
      // anywhere, server or UI. track.label + enumerateDevices() (both
      // available now that permission is granted) close that gap.
      try {
        const track = stream.getAudioTracks()[0];
        const trackSettings = track?.getSettings?.();
        const allInputs = (await navigator.mediaDevices.enumerateDevices())
          .filter((d) => d.kind === "audioinput")
          .map((d) => ({ deviceId: d.deviceId, label: d.label }));
        if (trackSettings) {
          logRealtimeEvent(sessionIdRef.current, "mic_track_settings", {
            meta: { ...trackSettings, label: track?.label || null, available_inputs: allInputs },
          });
        }
        setMicLabel(track?.label || null);
      } catch { /* diagnostic only - never let this affect the call */ }

      // 3. Peer connection. Only commit refs once we know we're not canceled.
      pc = new RTCPeerConnection();
      pc.ontrack = (ev) => {
        const el = audioElRef.current;
        if (el) el.srcObject = ev.streams[0];
      };
      stream.getTracks().forEach((t) => pc.addTrack(t, stream));

      // 4. Data channel — events, transcripts, session.update, tool dispatch
      const dc = pc.createDataChannel("oai-events");

      // Helper: send a JSON event safely
      const send = (obj) => {
        try { dc.send(JSON.stringify(obj)); } catch {}
      };

      // Server-event reaction layer (tool dispatch + the full onmessage
      // handler) lives in realtimeMessageHandler.js - same code, just
      // parameterized over what it closes over, so this file stops
      // growing. dc.onopen (below) stays here since it's connection setup.
      firstSpeechHeardRef.current = false;
      const { onMessage } = createRealtimeHandlers({
        myGen, startGenRef, sessionIdRef, ctxRef, caos, send, stop, onEndCall,
        turnSuspectRef, assistantSpeakingRef, restingRef,
        greetingCreateResponseOffRef,
        setStatus, setResting, setTranscript, setError,
        startAwaitingAnswerTimer,
        onFirstSpeechStarted: () => {
          if (awaitingAnswerTimerRef.current) { clearTimeout(awaitingAnswerTimerRef.current); awaitingAnswerTimerRef.current = null; }
          if (firstSpeechHeardRef.current) return;
          firstSpeechHeardRef.current = true;
          if (inviteSilenceTimerRef.current) { clearTimeout(inviteSilenceTimerRef.current); inviteSilenceTimerRef.current = null; }
        },
      });

      dc.onopen = () => {
        if (myGen !== startGenRef.current) return;
        // FAIL CLOSED: the authoritative persona instructions come from the
        // backend (_caos.instructions). If they're missing, do NOT fall back
        // to a generic unidentified model talking to a resident - refuse to
        // start instead. Wrong-but-talking is worse than unavailable here.
        if (!caos.instructions) {
          setError("Aria configuration could not be loaded.");
          setStatus("error");
          try { stop("config_missing"); } catch {}
          return;
        }
        // Apply the full session config from the backend: instructions,
        // tools, VAD timing. session.update is the canonical way to
        // configure a Realtime session post-mint - see
        // realtimeSessionUpdate.js for the exact shape and the hard-won
        // "confirmed live, not guessed" history behind it.
        // 2026-08-22: the greeting below is forced with an explicit
        // response.create (the model never speaks first on its own). The
        // server's own turn_detection has create_response:true, so if
        // Aria's greeting audio leaks back into the mic (room speaker,
        // imperfect echo cancellation) and VAD mistakes it for speech, the
        // server would auto-fire a SECOND response the moment that leaked
        // "speech" appears to stop - a real double-greeting seen live. Fix:
        // disable create_response for just this one forced turn, then
        // re-enable it (see response.done below) once the greeting's own
        // audio has actually finished, closing the exact window where its
        // own echo could trigger a bogus auto-response. Real interruption
        // still works during this window - interrupt_response is separate
        // from create_response - a genuine "wait, Aria" still cuts her off.
        greetingCreateResponseOffRef.current = true;
        send(buildSessionUpdate({ caos, voice }));
        send({ type: "response.create" });
        setStatus("live");

        // Level 1 resident-assistance event (2026-09-06): companion
        // timeout (default 300s, community-configurable via
        // ResidentAssistanceConfig, threaded through _caos.context by
        // routes/realtime.py) forcibly ends a session that's run long
        // without staff having resolved the underlying event - the event
        // itself stays open, only Aria goes quiet. Invite-silence (default
        // 8s) does NOT end the session - it just records that the resident
        // didn't respond to the opening invite, per the directive ("do not
        // interrogate, stay quietly companionable").
        postAriaEvent("activated");
        const timeoutMs = (ctxRef.current?.aria_companion_timeout_sec ?? 300) * 1000;
        const inviteMs = (ctxRef.current?.invite_silence_sec ?? 8) * 1000;
        companionTimeoutTimerRef.current = setTimeout(() => {
          try { stop("companion_timeout"); } catch {}
        }, timeoutMs);
        inviteSilenceTimerRef.current = setTimeout(() => {
          if (firstSpeechHeardRef.current) return;
          postAriaEvent("silence_after_invite");
        }, inviteMs);
      };

      dc.onmessage = onMessage;

      // 5. SDP exchange (offer → backend → OpenAI → answer)
      // FIXED 2026-08-09 (real bug): this used to negotiate without the
      // ephemeral key at all, so the backend authenticated with its own
      // server key and built a brand-new, generic, instructions-less
      // session - the actual live call never used the Aria/companion
      // instructions minted in step 1. Now forwards the same ephemeral
      // key so the call continues THAT already-configured session.
      // Empirically verified against OpenAI directly (real SDP via
      // aiortc + this exact key -> HTTP 201 with a valid answer) before
      // wiring it in here.
      const offer = await pc.createOffer();
      if (myGen !== startGenRef.current) throw new Error("canceled");
      await pc.setLocalDescription(offer);
      const negRes = await fetch(`${API}/realtime/negotiate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/sdp",
          "X-CAOS-Ephemeral-Key": ephemeral,
        },
        body: offer.sdp,
      });
      if (myGen !== startGenRef.current) throw new Error("canceled");
      if (!negRes.ok) throw new Error(`negotiate ${negRes.status}`);
      const { sdp: answerSdp } = await negRes.json();
      if (myGen !== startGenRef.current) throw new Error("canceled");
      await pc.setRemoteDescription({ type: "answer", sdp: answerSdp });

      // Commit only after success — partial state never sticks
      pcRef.current = pc;
      dcRef.current = dc;
      localStreamRef.current = stream;
      // Read-only lifecycle observability (Room 304: the actual cause of a
      // session ending was previously unknowable) - does not change what
      // happens on a drop, only records why. See realtimeLifecycleDiagnostics.js.
      lifecycleCleanupRef.current = attachLifecycleDiagnostics({
        pc, dc, sessionId: sessionIdRef.current, onTerminal: logSessionEnded,
      });
      // Keep the room lease alive while connected, so a crashed/network-lost
      // tab's lease goes stale (STALE_SECONDS) and self-heals instead of
      // permanently locking the room.
      if (leaseRoomRef.current) {
        const hbRoom = leaseRoomRef.current, hbSession = sessionIdRef.current;
        const beat = () => fetch(`${API}/realtime/room/${encodeURIComponent(hbRoom)}/heartbeat`, {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ session_id: hbSession }),
        }).catch(() => {});
        leaseHeartbeatRef.current = setInterval(beat, 20000);
      }
    } catch (e) {
      // Fully tear down anything we built before the failure
      try { pc?.close(); } catch {}
      try { stream?.getTracks().forEach((t) => t.stop()); } catch {}
      // Failed after claiming the lease (e.g. mic/SDP error) — release it
      // now rather than leaving the room falsely locked until it goes stale.
      if (leaseRoomRef.current) {
        releaseLease(leaseRoomRef.current, sessionIdRef.current);
        leaseRoomRef.current = null;
      }
      if (myGen === startGenRef.current && e?.message !== "canceled") {
        setError(e?.message || "Failed to start voice");
        setStatus("error");
      }
    }
  }, [voice, residentId, kioskId, room, alertId, sessionEndpoint, sessionPayload, triggerSource, logSessionEnded, postAriaEvent, startAwaitingAnswerTimer]);

  return { status, error, transcript, resting, micLabel, start, stop, audioElRef };
}
