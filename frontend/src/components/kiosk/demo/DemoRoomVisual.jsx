import React, { useCallback, useEffect, useState } from "react";
import { API } from "../../../lib/api";
import { DEMO_POLL_MS, demoRoomView, demoRoomCaption } from "../../../lib/demoRoom";

// Live picture of the demo room. Reads the same device list Aria's tools
// change (GET /devices/public/by-room/{room}) once a second, so a spoken or
// typed command shows up here without a page refresh - and only once the
// device store actually holds the new state.
export function useDemoRoomDevices(room) {
  const [devices, setDevices] = useState([]);
  const refresh = useCallback(async () => {
    if (!room) return;
    try {
      const r = await fetch(`${API}/devices/public/by-room/${encodeURIComponent(room)}`);
      if (r.ok) setDevices(await r.json());
    } catch { /* keep the last known picture */ }
  }, [room]);
  useEffect(() => {
    refresh();
    const t = setInterval(refresh, DEMO_POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);
  return { devices, refresh };
}

const Missing = ({ label }) => (
  <div className="text-xs text-white/50 italic">{label} not set up</div>
);

export default function DemoRoomVisual({ room, compact = false }) {
  const { devices } = useDemoRoomDevices(room);
  const view = demoRoomView(devices);
  const { light, thermostat, tv, blinds } = view;
  const glow = light?.on ? 0.25 + (light.brightness / 100) * 0.6 : 0;
  const slats = blinds ? Math.round(((100 - blinds.position) / 100) * 8) : 8;

  return (
    <section className="w-full rounded-3xl overflow-hidden border border-caos-line shadow-sm" data-testid="demo-room-visual">
      <div
        className={`relative ${compact ? "h-56" : "h-72 md:h-80"} transition-colors duration-500`}
        style={{ background: light?.on ? `rgba(40,36,28,${1 - glow * 0.5})` : "#16181c" }}
      >
        {/* light glow over the whole room */}
        <div className="absolute inset-0 pointer-events-none transition-opacity duration-500"
          style={{ opacity: glow, background: "radial-gradient(circle at 22% 18%, rgba(255,214,140,0.95), rgba(255,200,120,0.15) 55%, transparent 75%)" }} />

        {/* window + blinds */}
        <div className="absolute left-[8%] top-[12%] w-[26%] h-[48%] rounded-md border-4 border-[#6b5b45] bg-gradient-to-b from-sky-300 to-sky-100 overflow-hidden"
          data-testid="demo-blinds" data-position={blinds ? blinds.position : ""}>
          {blinds ? Array.from({ length: slats }).map((_, i) => (
            <div key={i} className="h-[12.5%] border-b border-[#b9a98f] bg-[#e8dcc6] transition-all duration-500" />
          )) : <div className="p-2"><Missing label="Blinds" /></div>}
        </div>

        {/* lamp */}
        <div className="absolute left-[40%] top-[10%] flex flex-col items-center" data-testid="demo-light" data-state={light ? (light.on ? "on" : "off") : "missing"}>
          <div className="w-0.5 h-8 bg-[#8a7b63]" />
          <div className="w-16 h-8 rounded-t-full border-2 border-[#8a7b63] transition-colors duration-500"
            style={{ background: light?.on ? "#ffd68a" : "#4a4640", boxShadow: light?.on ? `0 12px 40px ${10 + light.brightness / 2}px rgba(255,210,130,${glow})` : "none" }} />
          {!light && <Missing label="Light" />}
        </div>

        {/* TV */}
        <div className="absolute right-[8%] top-[16%] w-[36%] h-[40%] rounded-lg border-4 border-[#2a2a2a] flex items-center justify-center transition-colors duration-500"
          style={{ background: tv?.on ? "linear-gradient(135deg,#3b82f6,#22d3ee)" : "#0b0b0c" }}
          data-testid="demo-tv" data-state={tv ? (tv.on ? "on" : "off") : "missing"}>
          {tv?.on && (
            <div className="text-white text-center font-semibold drop-shadow">
              <div className="text-lg">{tv.input && tv.input !== "TV" ? tv.input : `CH ${tv.channel ?? "-"}`}</div>
              <div className="text-xs opacity-90">VOL {tv.volume ?? "-"}</div>
            </div>
          )}
          {!tv && <Missing label="TV" />}
        </div>

        {/* thermostat */}
        <div className="absolute right-[8%] bottom-[10%] w-20 h-20 rounded-full border-4 border-[#9aa3ad] bg-[#1f2a33] flex items-center justify-center"
          data-testid="demo-thermostat" data-temperature={thermostat?.temperature ?? ""}>
          {thermostat ? (
            <span className={`font-bold ${thermostat.on ? "text-emerald-300 text-xl" : "text-white/40 text-sm"}`}>
              {thermostat.on && thermostat.temperature != null ? `${thermostat.temperature}°` : "OFF"}
            </span>
          ) : <Missing label="Thermostat" />}
        </div>

        {/* floor */}
        <div className="absolute bottom-0 inset-x-0 h-[18%] bg-[#5a4a38]/80" />
      </div>
      <div className="bg-white px-4 py-3 text-sm text-caos-ink flex flex-wrap gap-x-4 gap-y-1" data-testid="demo-room-caption">
        <span className="text-xs font-bold uppercase tracking-widest text-caos-mute mr-2">Demo room · simulated devices</span>
        {demoRoomCaption(view).map((c) => <span key={c}>{c}</span>)}
      </div>
    </section>
  );
}
