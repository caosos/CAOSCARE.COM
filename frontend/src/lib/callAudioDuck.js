// While Aria and a resident talk, a room's TV/speaker is turned DOWN (never off) so the mic does not
// take TV voices for the resident, and turned back up by exactly the same amount when the call ends -
// every room, every end path (2026-10-12; replaced "power the TV off at call start", which switched a
// real TV off mid-show and restored it only on cancel).
// One-way (infrared) devices step down/up DUCK_STEPS presses - exact and state-independent (an off
// TV ignores both). Devices with a known numeric volume go down DUCK_STEPS and back to the exact prior level.
export const DUCK_STEPS = 15;

export async function duckRoomAudio(devices, room, send) {
  const restore = [];
  for (const d of devices || []) {
    if (d.kind !== "tv" && d.kind !== "speaker") continue;
    const caps = d.capabilities || [];
    try {
      if (caps.includes("volume_step")) {
        await send(room, "volume_step", -DUCK_STEPS, d.kind, d.device_id);
        restore.push({ device_id: d.device_id, kind: d.kind, action: "volume_step", value: DUCK_STEPS });
      } else if (caps.includes("volume") && d.state?.power === "on" && typeof d.state?.volume === "number") {
        await send(room, "volume", Math.max(0, d.state.volume - DUCK_STEPS), d.kind, d.device_id);
        restore.push({ device_id: d.device_id, kind: d.kind, action: "volume", value: d.state.volume });
      }
    } catch { /* a device that cannot be ducked must not block the call */ }
  }
  return restore;
}

export async function restoreRoomAudio(restore, room, send) {
  for (const r of restore || []) {
    try { await send(room, r.action, r.value, r.kind, r.device_id); } catch { /* best effort */ }
  }
}
