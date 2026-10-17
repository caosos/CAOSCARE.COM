/**
 * How Aria talks in this kiosk's room: "cascade" (low-cost voice, cascadeTransport.js) or "realtime". The setting
 * and the voice live on the Kiosk record (backend routes/aria_voice_prefs.py), so a change made from any screen -
 * the room's own page or the owner's laptop - switches the room. ?aria_voice=<mode> overrides for one test page.
 */
import { useCallback, useEffect, useState } from "react";
import { API } from "./api";

const MODES = new Set(["cascade", "realtime"]);

export function urlTransport(search = typeof window !== "undefined" ? window.location.search : "") {
  const m = new URLSearchParams(search).get("aria_voice");
  return MODES.has(m) ? m : null;
}

export function useVoiceTransport(kioskId) {
  const [config, setConfig] = useState({ cascade_enabled: false, transport: "realtime", voice: null });
  const load = useCallback((c) => c && setConfig(c), []);
  useEffect(() => {
    const q = kioskId ? `?kiosk_id=${encodeURIComponent(kioskId)}` : "";
    fetch(`${API}/aria-voice/config${q}`).then((r) => (r.ok ? r.json() : null)).then(load).catch(() => {});
  }, [kioskId, load]);
  const save = useCallback((prefs) => {
    if (!kioskId) return;
    fetch(`${API}/aria-voice/kiosks/${encodeURIComponent(kioskId)}/prefs`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(prefs),
    }).then((r) => (r.ok ? r.json() : null)).then(load).catch(() => {});
  }, [kioskId, load]);
  const transport = urlTransport() || config.transport;
  return {
    transport,
    voice: config.voice,
    available: config.cascade_enabled,
    toggle: () => save({ transport: transport === "cascade" ? "realtime" : "cascade" }),
    setVoice: (voice) => config.cascade_enabled && save({ voice }),
  };
}
