import React, { useState } from "react";
import { Lightbulb } from "lucide-react";

// Real touch brightness control for a brightness-capable light card - the
// defect this replaces: RoomDevicePanel used to render "Brightness 100%"
// as read-only text with the whole card wired to a single power-toggle
// tap, so a resident could never actually change brightness without
// speaking to Aria. This calls the exact same `onCommand` (Kiosk.jsx's
// sendDeviceCommand -> kioskDeviceControl.js's sendRoomDeviceCommand ->
// POST /devices/public/room/{room}/command) that both the generic device
// grid and Aria's own toggle_light voice tool already use - one command
// path, no UI-only device state. Setting brightness on a real HA light
// turns it on at that level in one call (device_adapters.py's
// action=="brightness" -> light.turn_on with brightness_pct), so a quick-
// percent tap or slider drag works correctly whether the light was
// already on or off - matching the voice tool's own behavior.
const QUICK_PERCENTS = [25, 50, 75, 100];

export default function LightControlCard({ device, name, onCommand }) {
  const isOn = device.state?.power === "on";
  const knownBrightness = typeof device.state?.brightness === "number" ? device.state.brightness : null;
  // No known brightness while off (a real HA read-back drops the
  // attribute once the light is off) - default the slider/quick-buttons'
  // starting point to 100 so "tap 50%" from off still means something
  // sensible rather than showing a misleading stale number.
  const [pending, setPending] = useState(null); // optimistic value while a request is in flight
  const displayBrightness = pending ?? knownBrightness ?? 100;
  const [sliderValue, setSliderValue] = useState(displayBrightness);

  const sendBrightness = async (value) => {
    setPending(value);
    setSliderValue(value);
    try {
      await onCommand("brightness", value, device.kind, device.device_id);
    } finally {
      setPending(null);
    }
  };

  const togglePower = async () => {
    await onCommand("power", isOn ? "off" : "on", device.kind, device.device_id);
  };

  const offline = device.online === false;

  return (
    <div
      data-testid={`kiosk-light-${device.device_id}`}
      className={`rounded-3xl border-2 p-5 flex flex-col gap-4 col-span-2 ${
        offline
          ? "bg-caos-mute/10 text-caos-mute border-caos-line"
          : isOn
          ? "bg-caos-forest text-white border-caos-forest shadow-lg"
          : "bg-white text-caos-forest border-caos-line"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Lightbulb className="w-8 h-8 shrink-0" strokeWidth={2} />
          <span className="font-display text-lg font-semibold leading-tight capitalize truncate">{name}</span>
        </div>
        <button
          type="button"
          data-testid={`kiosk-light-power-${device.device_id}`}
          disabled={offline}
          onClick={togglePower}
          className={`shrink-0 rounded-full px-6 py-3 text-base font-bold uppercase tracking-wider transition-colors ${
            offline
              ? "bg-caos-mute/20 text-caos-mute cursor-not-allowed"
              : isOn
              ? "bg-white text-caos-forest hover:bg-white/90"
              : "bg-caos-forest text-white hover:bg-caos-forest-hover"
          }`}
        >
          {isOn ? "Turn Off" : "Turn On"}
        </button>
      </div>

      {!offline && (
        <div className="space-y-3">
          <div className={`text-sm font-bold uppercase tracking-wider ${isOn ? "text-white/80" : "text-caos-mute"}`}>
            Brightness: {displayBrightness}%
          </div>

          {/* Large, senior-friendly slider - full 0-100 range, big touch
              target. Commits on release (onMouseUp/onTouchEnd/onChange),
              not on every pixel of drag, so it doesn't spam the real
              device with a command per frame. */}
          <input
            type="range"
            min={1}
            max={100}
            step={1}
            value={sliderValue}
            disabled={offline}
            data-testid={`kiosk-light-slider-${device.device_id}`}
            onChange={(e) => setSliderValue(Number(e.target.value))}
            onMouseUp={(e) => sendBrightness(Number(e.target.value))}
            onTouchEnd={(e) => sendBrightness(Number(e.target.value))}
            className="w-full h-10 accent-caos-terracotta cursor-pointer"
            style={{ accentColor: isOn ? "#ffffff" : undefined }}
          />

          <div className="grid grid-cols-4 gap-2">
            {QUICK_PERCENTS.map((pct) => (
              <button
                key={pct}
                type="button"
                data-testid={`kiosk-light-pct-${device.device_id}-${pct}`}
                onClick={() => sendBrightness(pct)}
                className={`rounded-2xl py-4 text-lg font-bold transition-colors ${
                  isOn
                    ? "bg-white/15 text-white hover:bg-white/25"
                    : "bg-caos-ambient text-caos-forest hover:bg-caos-line"
                }`}
              >
                {pct}%
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
