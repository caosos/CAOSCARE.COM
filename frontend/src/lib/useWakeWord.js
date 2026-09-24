/**
 * Connects the room page to the local "Aria" wake-word detector and keeps
 * it in step with the page's own call state:
 *   idle        -> detector listens for "Aria"
 *   any call    -> detector suppressed (Aria's own voice can't re-trigger it)
 * A wake while idle calls onWake(), which starts the existing Realtime
 * conversation path with trigger_source "wake_word" - no resident event is
 * opened, no lease is claimed here. Every step is breadcrumbed through the
 * existing activation-events log so a wake can be traced to its session.
 */
import { useEffect, useRef } from "react";
import { API } from "./api";
import { connectWakeWord } from "./wakeWordClient";
import { logActivationClientEvent } from "./activationClient";

async function micPermission() {
  try {
    const p = await navigator.permissions.query({ name: "microphone" });
    return p.state;
  } catch {
    return "unknown";
  }
}

// The session is minted by the existing path a moment after onWake(); the
// room lease it claims records trigger_source, which is what ties this wake
// to that session id without adding anything to the mint payload.
async function bindSession({ room, wakeId, detectedAt, base }) {
  const since = Date.parse(detectedAt) - 2000;
  for (let i = 0; i < 15; i++) {
    await new Promise((r) => setTimeout(r, 1000));
    try {
      const r = await fetch(`${API}/realtime/room/${encodeURIComponent(room)}/status`);
      const lease = (await r.json())?.lease;
      if (lease?.trigger_source === "wake_word" && Date.parse(lease.created_at) >= since) {
        logActivationClientEvent("wake_word_session_bound", {
          ...base, session_id: lease.session_id, data: { wake_id: wakeId, lease_status: lease.status },
        });
        return;
      }
    } catch { /* keep trying */ }
  }
  logActivationClientEvent("wake_word_session_bound", { ...base, data: { wake_id: wakeId, session_id: null, reason: "no_wake_word_lease_seen" } });
}

export function useWakeWord({ url, callState, kiosk, residentId, onWake }) {
  const clientRef = useRef(null);
  const live = useRef({});
  live.current = { callState, residentId, onWake };

  useEffect(() => {
    if (!url || !kiosk?.kiosk_id) return undefined;
    const base = () => ({ room: kiosk.room, kiosk_id: kiosk.kiosk_id, resident_id: live.current.residentId });
    let connected = false;
    const client = connectWakeWord({
      url,
      onOpen: () => { connected = true; logActivationClientEvent("wake_listener_connected", { ...base(), data: { url } }); },
      onClose: () => {
        if (connected) logActivationClientEvent("wake_listener_disconnected", { ...base(), data: { url } });
        connected = false;
      },
      onMessage: async (msg) => {
        if (msg.type === "listening") {
          logActivationClientEvent("wake_listening_resumed", { ...base(), data: { reason: msg.reason, at: msg.at } });
          return;
        }
        if (msg.type !== "wake") return;
        const detection = {
          wake_id: msg.wake_id, keyword: msg.keyword, detected_at: msg.detected_at, confidence: msg.confidence,
          detector: msg.detector, model: msg.model, keywords_threshold: msg.keywords_threshold,
          audio_input_device: msg.audio_input_device,
        };
        if (live.current.callState !== "idle") {
          logActivationClientEvent("wake_word_ignored", { ...base(), data: { ...detection, reason: "in_call" } });
          client.setState("conversation", "wake_while_in_call");
          return;
        }
        const perm = await micPermission();
        if (perm !== "granted" && perm !== "unknown") {
          logActivationClientEvent("wake_word_ignored", { ...base(), data: { ...detection, reason: `mic_permission_${perm}` } });
          client.setState("listening", "mic_permission_missing");
          return;
        }
        logActivationClientEvent("wake_word_detected", { ...base(), data: detection });
        live.current.onWake?.();
        bindSession({ room: kiosk.room, wakeId: msg.wake_id, detectedAt: msg.detected_at, base: base() });
      },
    });
    clientRef.current = client;
    return () => { client.close(); clientRef.current = null; };
  }, [url, kiosk?.kiosk_id, kiosk?.room]);

  useEffect(() => {
    clientRef.current?.setState(callState === "idle" ? "listening" : "conversation", `call_state_${callState}`);
  }, [callState, url, kiosk?.kiosk_id]);
}
