// While Aria and a resident talk, a room's TV/speaker is turned DOWN (never off) so the mic does not
// take TV voices for the resident, and turned back up by exactly the same amount when the call ends -
// every room, every end path (2026-10-12; replaced "power the TV off at call start", which switched a
// real TV off mid-show and restored it only on cancel).
// Preferred: MUTE - one press at call start, one at call end (Michael 2026-10-12: "it should mute the
// TV"). A toggle pressed twice always returns the TV to how it was, so it is exact on one-way infrared too.
// Else one-way devices step down/up DUCK_STEPS presses; devices with a known numeric volume go down
// DUCK_STEPS and back to the exact prior level.
export const DUCK_STEPS = 15;

export async function duckRoomAudio(devices, room, send) {
  const restore = [];
  for (const d of devices || []) {
    if (d.kind !== "tv" && d.kind !== "speaker") continue;
    const caps = d.capabilities || [];
    try {
      if (caps.includes("mute")) {
        await send(room, "mute", true, d.kind, d.device_id);
        restore.push({ device_id: d.device_id, kind: d.kind, action: "mute", value: true });
      } else if (caps.includes("volume_step")) {
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

// One coordinator per kiosk serializes call boundaries. Without this, a
// close can start restoring (+15) while a rapid new wake starts ducking
// (-15), leaving a one-way TV at whichever command happens to finish last.
// The queue guarantees: old duck completes -> old restore completes -> new
// duck begins. It delegates to the same mute/volume-only functions above,
// so call-boundary audio handling never gains a power action.
export function createCallAudioCoordinator(send) {
  let tail = Promise.resolve();
  let active = null;

  const enqueue = (work) => {
    const operation = tail.then(work, work);
    tail = operation.catch(() => {});
    return operation;
  };

  return {
    begin(devices, room) {
      return enqueue(async () => {
        // Defensive recovery for a duplicate begin without a matching end:
        // restore the prior call before applying the new call's duck.
        if (active) await restoreRoomAudio(active.restore, active.room, send);
        active = { room, restore: await duckRoomAudio(devices, room, send) };
      });
    },
    end() {
      return enqueue(async () => {
        if (!active) return;
        const closing = active;
        active = null;
        await restoreRoomAudio(closing.restore, closing.room, send);
      });
    },
  };
}
