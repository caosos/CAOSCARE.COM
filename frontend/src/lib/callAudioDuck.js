// While Aria and a resident talk, a room's TV/speaker is turned DOWN (never off) so the mic does not
// take TV voices for the resident, and turned back up by exactly the same amount when the call ends -
// every room, every end path (2026-10-12; replaced "power the TV off at call start", which switched a
// real TV off mid-show and restored it only on cancel).
// Preferred: MUTE - one press at call start, one at call end (Michael 2026-10-12: "it should mute the
// TV"). A toggle pressed twice always returns the TV to how it was, so it is exact on one-way infrared too.
// Else one-way devices step down/up DUCK_STEPS presses; devices with a known numeric volume go down
// DUCK_STEPS and back to the exact prior level.
//
// 2026-10-16 (aria-room-runtime-fixes-001, Room 214 TV left muted): every press that still needs its
// undo is kept in a persisted ledger, entry by entry, so a page reload, unmount or crash between duck and
// restore is undone on the next mount (recover), and a restore can never be sent twice for one duck.
export const DUCK_STEPS = 15;
export const LEDGER_KEY = "caos_call_audio_ledger";

const undoOf = (d, action, value) => ({ device_id: d.device_id, kind: d.kind, action, value });

export async function duckRoomAudio(devices, room, send, onDucked = () => {}) {
  const restore = [];
  for (const d of devices || []) {
    if (d.kind !== "tv" && d.kind !== "speaker") continue;
    const caps = d.capabilities || [];
    let undo = null;
    try {
      if (caps.includes("mute")) {
        await send(room, "mute", true, d.kind, d.device_id);
        undo = undoOf(d, "mute", true);
      } else if (caps.includes("volume_step")) {
        await send(room, "volume_step", -DUCK_STEPS, d.kind, d.device_id);
        undo = undoOf(d, "volume_step", DUCK_STEPS);
      } else if (caps.includes("volume") && d.state?.power === "on" && typeof d.state?.volume === "number") {
        await send(room, "volume", Math.max(0, d.state.volume - DUCK_STEPS), d.kind, d.device_id);
        undo = undoOf(d, "volume", d.state.volume);
      }
    } catch { /* a device that cannot be ducked must not block the call */ }
    if (undo) { restore.push(undo); onDucked(restore); }
  }
  return restore;
}

// Each undo is sent at most once; one retry on a failed send. Returns the undos that still failed.
export async function restoreRoomAudio(restore, room, send, onRestored = () => {}) {
  const pending = [...(restore || [])];
  const failed = [];
  while (pending.length) {
    const r = pending.shift();
    let ok = false;
    for (let attempt = 0; attempt < 2 && !ok; attempt += 1) {
      try { await send(room, r.action, r.value, r.kind, r.device_id); ok = true; } catch { /* retry once */ }
    }
    if (!ok) failed.push(r);
    onRestored([...pending, ...failed]);
  }
  return failed;
}

function ledgerStore(storage) {
  return {
    read() { try { return JSON.parse(storage?.getItem(LEDGER_KEY) || "null"); } catch { return null; } },
    write(entry) {
      try {
        if (entry && entry.restore.length) storage?.setItem(LEDGER_KEY, JSON.stringify(entry));
        else storage?.removeItem(LEDGER_KEY);
      } catch { /* storage unavailable: in-memory state still restores this page's call */ }
    },
  };
}

// One coordinator per kiosk serializes call boundaries. Without this, a
// close can start restoring (+15) while a rapid new wake starts ducking
// (-15), leaving a one-way TV at whichever command happens to finish last.
// The queue guarantees: old duck completes -> old restore completes -> new
// duck begins. It delegates to the same mute/volume-only functions above,
// so call-boundary audio handling never gains a power action.
// begin/end/recover are idempotent: end with nothing ducked does nothing, a
// second end after a restore does nothing, recover only replays what is
// still in the ledger.
export function createCallAudioCoordinator(send, { storage = null, log = () => {} } = {}) {
  let tail = Promise.resolve();
  let active = null;
  const ledger = ledgerStore(storage);

  const enqueue = (work) => {
    const operation = tail.then(work, work);
    tail = operation.catch(() => {});
    return operation;
  };
  const undo = async (entry, reason) => {
    const failed = await restoreRoomAudio(entry.restore, entry.room, send,
      (left) => ledger.write({ room: entry.room, restore: left }));
    ledger.write(null);
    log(failed.length ? "call_audio_restore_failed" : "call_audio_restored",
      { room: entry.room, reason, actions: entry.restore.map((r) => r.action), failed: failed.map((r) => r.action) });
  };

  return {
    begin(devices, room) {
      return enqueue(async () => {
        // Defensive recovery for a duplicate begin without a matching end:
        // restore the prior call before applying the new call's duck.
        if (active) { const prior = active; active = null; await undo(prior, "replaced_by_new_call"); }
        const entry = { room, restore: [] };
        active = entry;
        entry.restore = await duckRoomAudio(devices, room, send, (sofar) => ledger.write({ room, restore: sofar }));
        if (entry.restore.length) log("call_audio_ducked", { room, actions: entry.restore.map((r) => r.action) });
      });
    },
    end(reason = "call_end") {
      return enqueue(async () => {
        if (!active) return;
        const closing = active;
        active = null;
        await undo(closing, reason);
      });
    },
    /** On mount: undo a duck a previous page load never restored (reload, crash, unmount). */
    recover() {
      return enqueue(async () => {
        const left = ledger.read();
        if (active || !left?.restore?.length) return;
        log("call_audio_recovered", { room: left.room, actions: left.restore.map((r) => r.action) });
        await undo(left, "recovered_after_reload");
      });
    },
  };
}
