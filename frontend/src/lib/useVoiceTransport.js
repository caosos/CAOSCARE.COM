/**
 * How Aria talks on this kiosk: "cascade" (low-cost voice, cascadeTransport.js) or "realtime" (OpenAI Realtime).
 * The room's default is the backend's (GET /aria-voice/config); the kiosk's switch remembers a choice on this
 * device; ?aria_voice=<mode> in the URL overrides both. Without the low-cost voice enabled it is always Realtime.
 */
import { useEffect, useState } from "react";
import { API } from "./api";

const KEY = "caos_kiosk_transport";
const MODES = new Set(["cascade", "realtime"]);

export function chosenTransport(search = typeof window !== "undefined" ? window.location.search : "") {
  const fromUrl = new URLSearchParams(search).get("aria_voice");
  if (MODES.has(fromUrl)) return fromUrl;
  try { const saved = localStorage.getItem(KEY); return MODES.has(saved) ? saved : null; } catch { return null; }
}

export function useVoiceTransport() {
  const [config, setConfig] = useState({ cascade_enabled: false, default_transport: "realtime" });
  const [choice, setChoice] = useState(chosenTransport);
  useEffect(() => {
    fetch(`${API}/aria-voice/config`).then((r) => (r.ok ? r.json() : null)).then((c) => c && setConfig(c)).catch(() => {});
  }, []);
  const transport = config.cascade_enabled ? choice || config.default_transport : "realtime";
  const toggle = () => {
    const next = transport === "cascade" ? "realtime" : "cascade";
    try { localStorage.setItem(KEY, next); } catch { /* the choice lasts for this page only */ }
    setChoice(next);
  };
  return { transport, available: config.cascade_enabled, toggle };
}
