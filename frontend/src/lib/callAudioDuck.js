// While Aria and a resident talk, a room's TV/speaker is turned DOWN (never off) so the mic does not
// take TV voices for the resident, and turned back up by exactly the same amount when the call ends -
// every room, every end path (2026-10-12; replaced "power the TV off at call start", which switched a
// real TV off mid-show and restored it only on cancel).
// One-way (infrared) devices step down/up DUCK_STEPS presses. That is best-effort and unverified:
// at a volume boundary, the same number of up presses may not restore the original level. Only a
// verified, state-reporting media player is eligible for exact numeric dip/restore.
export const DUCK_STEPS = 15;
const volumeChoices = new Map(); // device_id -> { baseline, chosen, ducked }

// Missing means enabled so kiosks created before the preference was added keep
// their existing behavior. Only an explicit per-room opt-out disables it.
export function shouldDuckRoomAudio(kiosk) {
  return kiosk?.tv_audio_duck !== false;
}

export function residentVolumeReference(deviceId, fallback) {
  const state = volumeChoices.get(deviceId);
  if (typeof state?.chosen === "number") return state.chosen;
  return typeof state?.baseline === "number" ? state.baseline : fallback;
}

export function noteResidentVolumeChoice(deviceId, volume) {
  const state = volumeChoices.get(deviceId) || {};
  volumeChoices.set(deviceId, { ...state, chosen: volume });
}

export function conversationVolumeTarget(deviceId, desired) {
  const state = volumeChoices.get(deviceId);
  return Math.max(0, Math.min(100, desired - (state?.ducked ? DUCK_STEPS : 0)));
}

export function isStateReportingVolumeDevice(device) {
  return device?.protocol === "home_assistant" &&
    String(device?.endpoint || "").startsWith("media_player.") &&
    (device?.capabilities || []).includes("volume") &&
    typeof device?.state?.volume === "number";
}

export function resetResidentVolumeChoices() { volumeChoices.clear(); }

export async function duckRoomAudio(devices, room, send) {
  const restore = [];
  for (const d of devices || []) {
    if (d.kind !== "tv" && d.kind !== "speaker") continue;
    volumeChoices.delete(d.device_id);
    const caps = d.capabilities || [];
    try {
      if (caps.includes("volume_step")) {
        await send(room, "volume_step", -DUCK_STEPS, d.kind, d.device_id);
        restore.push({ device_id: d.device_id, kind: d.kind, action: "volume_step", value: DUCK_STEPS });
      } else if (isStateReportingVolumeDevice(d) && d.state?.power === "on") {
        volumeChoices.set(d.device_id, { baseline: d.state.volume, chosen: null, ducked: true });
        await send(room, "volume", Math.max(0, d.state.volume - DUCK_STEPS), d.kind, d.device_id);
        restore.push({ device_id: d.device_id, kind: d.kind, action: "volume", value: d.state.volume });
      }
    } catch { /* a device that cannot be ducked must not block the call */ }
  }
  return restore;
}

export async function restoreRoomAudio(restore, room, send) {
  for (const r of restore || []) {
    const choice = volumeChoices.get(r.device_id);
    const value = r.action === "volume" && typeof choice?.chosen === "number" ? choice.chosen : r.value;
    try { await send(room, r.action, value, r.kind, r.device_id); } catch { /* best effort */ }
    volumeChoices.delete(r.device_id);
  }
}
