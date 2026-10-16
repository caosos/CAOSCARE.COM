// Browser wiring for the call-audio coordinator (callAudioDuck.js): the
// persisted ledger lives in localStorage (one room page per browser), and
// duck/restore outcomes go to the activation log as call_audio_* events.
import { logActivationClientEvent } from "./activationClient";

function safeStorage() {
  try { return typeof window !== "undefined" ? window.localStorage : null; } catch { return null; }
}

export function callAudioOptions() {
  return {
    storage: safeStorage(),
    log: (event, data) => logActivationClientEvent(event, { room: data?.room || null, data }),
  };
}
