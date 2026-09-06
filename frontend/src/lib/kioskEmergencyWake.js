/**
 * kioskEmergencyWake — should this active-emergency poll result auto-wake
 * Aria on the mounted kiosk, and what marker should the kiosk remember?
 *
 * Extracted from Kiosk.jsx (2026-09-06 break-test, docs/LEVEL1_BREAKTEST.md).
 * The kiosk used to remember only the last `alert_id` it auto-woke for and
 * never re-engage that id. That was fine while a press after
 * `activation_consumed_at` minted a NEW alert_id. The Level 1 resident-event
 * change made a later pendant press REACTIVATE the same open event (same
 * alert_id, press_count bumped, activation_consumed_at reset to null), so an
 * already-open kiosk tab went permanently deaf to every subsequent press on
 * that event until staff resolved it (invariant 6 — "a later pendant press
 * must reactivate Aria on the same open event").
 *
 * Fix: remember { id, pressCount }. Re-wake when the alert_id is new OR the
 * press_count has grown past the last engaged watermark — a genuine new
 * press always bumps press_count, while a bare re-poll of the same state, or
 * the on-screen X-button ending a call WITHOUT consuming the activation,
 * does not (so there is no relaunch loop). While a call is running the
 * watermark is kept current so presses made mid-call don't trigger a
 * spurious relaunch the instant the call ends.
 */

/**
 * @param {object|null} alert  `data.alert` from GET /kiosks/{id}/active-emergency
 * @param {{id:string,pressCount:number}|null} seen  last engaged marker
 * @param {string} callState  current kiosk call state ("idle" | "chatting" | ...)
 * @returns {{ wake: boolean, seen: {id:string,pressCount:number}|null }}
 */
export function evaluateEmergencyWake(alert, seen, callState) {
  if (!alert || !alert.alert_id) return { wake: false, seen };
  const pressCount = alert.press_count || 0;
  const sameAlert = !!seen && seen.id === alert.alert_id;

  if (callState !== "idle") {
    // A session already owns this event. Never wake a second one; just keep
    // the watermark at/above the current count for the same alert.
    if (sameAlert) {
      return { wake: false, seen: { id: alert.alert_id, pressCount: Math.max(seen.pressCount, pressCount) } };
    }
    return { wake: false, seen };
  }

  const isNewPress = !seen || !sameAlert || pressCount > seen.pressCount;
  if (isNewPress) return { wake: true, seen: { id: alert.alert_id, pressCount } };
  return { wake: false, seen };
}
