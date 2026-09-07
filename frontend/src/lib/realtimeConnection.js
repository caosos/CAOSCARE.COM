/** One voice connection attempt. Owns setup resources and cancels stale
 * attempts without releasing another attempt's lease. Existing persona,
 * device tools, greeting gate, transcript flow, and SDP shape are retained.
 */
import { API } from "./api";
import { logRealtimeEvent } from "./realtimeDiagnostics";
import { createRealtimeHandlers } from "./realtimeMessageHandler";
import { attachLifecycleDiagnostics } from "./realtimeLifecycleDiagnostics";
import { buildSessionUpdate } from "./realtimeSessionUpdate";
import { createLeaseWatchdog } from "./realtimeLeaseWatchdog";
import { createInactivityTimer } from "./realtimeInactivityTimer";

export async function connectRealtimeVoice({
  attemptRef, voice, residentId, kioskId, room, alertId, activationId, sessionEndpoint,
  sessionPayload, triggerSource, onEndCall, pcRef, dcRef, localStreamRef,
  audioElRef, leaseHeartbeatRef, leaseRoomRef, startGenRef, sessionIdRef,
  ctxRef, endReasonLoggedRef, lifecycleCleanupRef, assistantSpeakingRef,
  turnSuspectRef, greetingCreateResponseOffRef, restingRef, firstSpeechHeardRef,
  awaitingAnswerTimerRef, inviteSilenceTimerRef, companionTimeoutTimerRef,
  setStatus, setError, setMicLabel, setResting, setTranscript,
  stop, releaseLease, postAriaEvent, startAwaitingAnswerTimer, logSessionEnded
}) {
    if (pcRef.current) return;              // already connected
    const myGen = ++startGenRef.current;
    sessionIdRef.current = `rt_${Math.random().toString(36).slice(2, 10)}_${Date.now()}`;
    const sid = sessionIdRef.current;
    const attempt = { cancelReason: null };
    attemptRef.current = attempt;
    const releaseOwnClaim = () => releaseLease(room, sid, {
      alert_id: alertId, activation_id: activationId, reason: attempt.cancelReason,
    });
    const current = () => myGen === startGenRef.current;
    const recover = (reason) => {
      if (!current()) return;
      stop(reason);
      onEndCall?.({ retry: true, reason });
    };
    ctxRef.current = { ...ctxRef.current, session_id: sid };
    endReasonLoggedRef.current = false;

    setError(null);
    setStatus("connecting");
    let pc = null;
    let stream = null;
    let watchdog = null;
    let claimed = false;
    const setupTimer = setTimeout(() => recover("setup_timeout"), 30000);
    try {
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
            activation_id: activationId || null,
            session_id: sessionIdRef.current,
            trigger_source: triggerSource || "manual_kiosk",
          }
        ),
      });
      if (!current()) { clearTimeout(setupTimer); releaseOwnClaim(); return; }
      if (!sessionRes.ok) {
        let detail = null;
        try { detail = (await sessionRes.json())?.detail || null; } catch {}
        logRealtimeEvent(sessionIdRef.current, "session_mint_failed", { meta: { status: sessionRes.status, detail } });
        throw new Error("Voice is temporarily unavailable. Try again.");
      }
      const session = await sessionRes.json();
      if (!current()) { clearTimeout(setupTimer); releaseOwnClaim(); return; }
      const caos = session._caos || {};
      if (caos.lease && caos.lease.claimed === false) {
        logRealtimeEvent(sessionIdRef.current, "lease_not_claimed", { meta: caos.lease });
        clearTimeout(setupTimer);
        setStatus("unavailable");
        return;
      }
      if (caos.lease?.claimed && room) {
        claimed = true;
        leaseRoomRef.current = { room, sessionId: sid };
        watchdog = createLeaseWatchdog({
          heartbeat: async () => {
            const r = await fetch(`${API}/realtime/room/${encodeURIComponent(room)}/heartbeat`, {
              method: "POST", headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ session_id: sid }),
              signal: AbortSignal.timeout(5000),
            });
            if (!r.ok) throw new Error("heartbeat unavailable");
            return (await r.json()).ok === true;
          }, onLost: recover,
        });
        leaseHeartbeatRef.current = watchdog;
        if (!(await watchdog.beat()) || !current()) throw new Error("Room ownership could not be verified");
      }
      const ephemeral = session?.value || session?.client_secret?.value;
      if (!ephemeral) throw new Error("no ephemeral key");
      if (caos.context) ctxRef.current = { ...ctxRef.current, ...caos.context };

      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
      });
      if (myGen !== startGenRef.current) {
        stream.getTracks().forEach((t) => t.stop());
        if (claimed) releaseOwnClaim();
        return;
      }
      localStreamRef.current = stream;
      stream.getAudioTracks().forEach(t => t.addEventListener("ended", () => recover("microphone_ended")));
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

      if (!current()) throw new Error("canceled");
      pc = new RTCPeerConnection();
      pcRef.current = pc;
      pc.ontrack = (ev) => {
        const el = audioElRef.current;
        if (el) el.srcObject = ev.streams[0];
      };
      stream.getTracks().forEach((t) => pc.addTrack(t, stream));

      const dc = pc.createDataChannel("oai-events");
      dcRef.current = dc;

      const send = (obj) => {
        try { dc.send(JSON.stringify(obj)); } catch {}
      };

      firstSpeechHeardRef.current = false;

      // Companion timeout is an INACTIVITY timer, NOT a session-age timer
      // (Level 1 directive 2026-09-07 - Room 214 session rt_mkqn5z8x was
      // cut off at ~302s mid-song by the old one-shot arm). Every speech
      // event (resident or Aria) bumps it; it only fires after a full
      // window of genuine silence. See realtimeInactivityTimer.js.
      const inactivity = createInactivityTimer({
        seconds: ctxRef.current?.aria_companion_timeout_sec ?? 300,
        onTimeout: () => { try { stop("companion_timeout"); onEndCall?.(); } catch {} },
      });
      companionTimeoutTimerRef.current = { close: () => inactivity.cancel() };

      const { onMessage } = createRealtimeHandlers({
        myGen, startGenRef, sessionIdRef, ctxRef, caos, send, stop, onEndCall,
        turnSuspectRef, assistantSpeakingRef, restingRef,
        greetingCreateResponseOffRef,
        setStatus, setResting, setTranscript, setError,
        startAwaitingAnswerTimer,
        onConversationActivity: () => { if (myGen === startGenRef.current) inactivity.bump(); },
        onFirstSpeechStarted: () => {
          if (awaitingAnswerTimerRef.current) { clearTimeout(awaitingAnswerTimerRef.current); awaitingAnswerTimerRef.current = null; }
          if (firstSpeechHeardRef.current) return;
          firstSpeechHeardRef.current = true;
          if (inviteSilenceTimerRef.current) { clearTimeout(inviteSilenceTimerRef.current); inviteSilenceTimerRef.current = null; }
        },
      });

      dc.onopen = () => {
        if (myGen !== startGenRef.current) return;
        clearTimeout(setupTimer);
        if (!caos.instructions) {
          setError("Aria configuration could not be loaded.");
          logSessionEnded("setup_failed");
        setStatus("error");
          try { stop("config_missing"); } catch {}
          return;
        }
        greetingCreateResponseOffRef.current = true;
        send(buildSessionUpdate({ caos, voice }));
        send({ type: "response.create" });
        setStatus("live");

        postAriaEvent("activated");
        // Initial arm: the room is silent until the greeting plays. Every
        // subsequent speech event (realtimeMessageHandler.js -> activity())
        // bumps this to a fresh full window - an active conversation is
        // never terminated by it. Only a full window of real silence fires.
        inactivity.bump();
        const inviteMs = (ctxRef.current?.invite_silence_sec ?? 8) * 1000;
        inviteSilenceTimerRef.current = setTimeout(() => {
          if (firstSpeechHeardRef.current) return;
          postAriaEvent("silence_after_invite");
        }, inviteMs);
      };

      dc.onmessage = onMessage;

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
      if (!current()) throw new Error("canceled");

      pcRef.current = pc;
      dcRef.current = dc;
      localStreamRef.current = stream;
      lifecycleCleanupRef.current = attachLifecycleDiagnostics({
        pc, dc, sessionId: sid, onTerminal: recover,
      });
    } catch (e) {
      clearTimeout(setupTimer);
      try { pc?.close(); } catch {}
      try { stream?.getTracks().forEach((t) => t.stop()); } catch {}
      watchdog?.close();
      if (claimed) releaseOwnClaim();
      if (current()) {
        pcRef.current = null; dcRef.current = null; localStreamRef.current = null;
        leaseRoomRef.current = null; leaseHeartbeatRef.current = null;
      }
      if (myGen === startGenRef.current && e?.message !== "canceled") {
        setError(e?.message || "Failed to start voice");
        logSessionEnded("setup_failed");
        setStatus("error");
      }
    }
}
