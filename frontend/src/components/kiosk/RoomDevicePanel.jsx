import React from "react";
import { Lightbulb, Fan, Thermometer, Tv, Volume2, Power, WifiOff } from "lucide-react";
import { nearestColorName, colorTempLabel } from "../../lib/realtimeLightControl";
import LightControlCard from "./LightControlCard";

const DEVICE_ICON = {
  light: Lightbulb, fan: Fan, heater: Thermometer, ac: Thermometer, thermostat: Thermometer,
  tv: Tv, speaker: Volume2, blinds: Power, outlet: Power,
};

// Capability-driven, not kind-hardcoded - a device declares what it
// supports (models.py's DeviceCapability list) and this renders exactly
// that, so a new device kind (a ceiling fan, blinds) shows sensible state
// lines without a code change here. Same state the /devices endpoints and
// Aria's tools read - one contract, not a separate UI-only model (see
// 2026-08-27 report, "same device state for screen and Aria").
function stateLines(d) {
  const s = d.state || {};
  const caps = d.capabilities || [];
  const lines = [];
  if (caps.includes("power")) lines.push(s.power === "on" ? "On" : "Off");
  if (caps.includes("hvac_mode") && s.hvac_mode && s.hvac_mode !== "off") lines.push(s.hvac_mode[0].toUpperCase() + s.hvac_mode.slice(1));
  if (caps.includes("temperature") && typeof s.temperature === "number") lines.push(`Set: ${s.temperature}°F`);
  if (typeof s.current_temperature === "number") lines.push(`Room: ${s.current_temperature}°F`);
  if (caps.includes("input") && s.input) lines.push(`Input: ${s.input}`);
  if (caps.includes("volume") && typeof s.volume === "number" && s.power === "on") lines.push(`Volume ${s.volume}`);
  if (caps.includes("brightness") && typeof s.brightness === "number" && s.power === "on") lines.push(`Brightness ${s.brightness}%`);
  if (caps.includes("color") && s.color && s.power === "on") {
    const name = nearestColorName(s.color);
    if (name) lines.push(name[0].toUpperCase() + name.slice(1));
  }
  if (caps.includes("color_temp") && s.color_temp && s.power === "on") {
    const label = colorTempLabel(s.color_temp);
    if (label) lines.push(label[0].toUpperCase() + label.slice(1));
  }
  if (caps.includes("fan_speed") && s.fan_speed != null) lines.push(`Fan ${s.fan_speed}`);
  if (caps.includes("position") && s.position != null) lines.push(`Position ${s.position}`);
  return lines;
}

// `onCommand` is Kiosk.jsx's own sendDeviceCommand(action, value, kind,
// deviceId) - the exact same function the old single-button toggle
// already called and the exact same POST /devices/public/room/{room}/
// command path Aria's voice tools use (kioskDeviceControl.js /
// realtimeDeviceTools.js). Passed straight through to LightControlCard
// for brightness taps/slider drags too - one command path, never a
// separate UI-only device state.
export default function RoomDevicePanel({ devices, room, onCommand }) {
  if (!devices?.length) return null;
  return (
    <div className="w-full max-w-4xl mx-auto" data-testid="kiosk-device-panel">
      <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute mb-4">Your room</p>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {devices.map((d) => {
          const name = d.label.replace(`Room ${room} `, "");
          // Brightness-capable lights get real touch controls (power +
          // brightness slider/quick-percents), not a bare power toggle -
          // each device's own identity (Desk lamp / Overhead light) stays
          // distinct since `name` comes from that device's own label, not
          // a generic "Light" fallback.
          if ((d.capabilities || []).includes("brightness")) {
            return <LightControlCard key={d.device_id} device={d} name={name} onCommand={onCommand} />;
          }
          const Icon = DEVICE_ICON[d.kind] || Power;
          const offline = d.online === false;
          const isOn = d.state?.power === "on";
          const lines = offline ? ["Offline"] : stateLines(d);
          return (
            <button
              key={d.device_id}
              data-testid={`kiosk-dev-${d.device_id}`}
              disabled={offline}
              onClick={() => !offline && onCommand("power", isOn ? "off" : "on", d.kind, d.device_id)}
              className={`rounded-3xl border-2 p-5 flex flex-col items-start gap-2 text-left transition-all ${
                offline
                  ? "bg-caos-mute/10 text-caos-mute border-caos-line cursor-not-allowed"
                  : isOn
                  ? "bg-caos-forest text-white border-caos-forest shadow-lg"
                  : "bg-white text-caos-forest border-caos-line hover:border-caos-forest"
              }`}
            >
              {offline ? <WifiOff className="w-8 h-8" strokeWidth={2} /> : <Icon className="w-8 h-8" strokeWidth={2} />}
              <span className="font-display text-lg font-semibold leading-tight capitalize">
                {name}
              </span>
              <span className={`text-xs font-bold uppercase tracking-wider ${isOn ? "text-white/80" : "text-caos-mute"}`}>
                {lines.join(" · ")}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
