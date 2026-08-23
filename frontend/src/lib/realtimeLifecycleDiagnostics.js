/**
 * Read-only WebRTC/data-channel lifecycle observability - added 2026-08-23
 * per the Chauncey/Room 304 incident report: that session's actual
 * termination cause was unknowable because nothing logged connection
 * state changes, data-channel close/error, or page teardown - the last
 * diagnostic event was just the final transcript, then silence.
 *
 * Purely diagnostic. Does NOT change connection behavior - no
 * auto-reconnect, no teardown triggered from here. `onTerminal` only logs
 * a reason; useRealtimeVoice.js's own stop() still owns actual teardown.
 */
import { logRealtimeEvent } from "./realtimeDiagnostics";

export function attachLifecycleDiagnostics({ pc, dc, sessionId, onTerminal }) {
  const log = (eventType, meta) => logRealtimeEvent(sessionId, eventType, { meta });

  const onConnState = () => {
    log("pc_connection_state", { state: pc.connectionState });
    if (pc.connectionState === "failed") onTerminal("webrtc_connection_failed");
    else if (pc.connectionState === "closed") onTerminal("webrtc_connection_closed");
  };
  const onIceState = () => {
    log("pc_ice_connection_state", { state: pc.iceConnectionState });
    if (pc.iceConnectionState === "failed") onTerminal("ice_failed");
  };
  const onDcClose = () => { log("datachannel_closed", {}); onTerminal("datachannel_closed"); };
  const onDcError = (ev) => { log("datachannel_error", { message: ev?.error?.message || "unknown" }); onTerminal("datachannel_error"); };
  const onPageHide = () => onTerminal("page_hidden_or_closed");

  pc.addEventListener("connectionstatechange", onConnState);
  pc.addEventListener("iceconnectionstatechange", onIceState);
  dc.addEventListener("close", onDcClose);
  dc.addEventListener("error", onDcError);
  window.addEventListener("pagehide", onPageHide);

  return () => {
    try { pc.removeEventListener("connectionstatechange", onConnState); } catch {}
    try { pc.removeEventListener("iceconnectionstatechange", onIceState); } catch {}
    try { dc.removeEventListener("close", onDcClose); } catch {}
    try { dc.removeEventListener("error", onDcError); } catch {}
    try { window.removeEventListener("pagehide", onPageHide); } catch {}
  };
}
