/**
 * activationClient — kiosk-side breadcrumbs for the activation observability
 * stream (Level 1 observability requirement, 2026-09-07).
 *
 * The kiosk is the one participant with no server record of when it was
 * actually present. These helpers let it post lightweight, allow-listed
 * state-transition breadcrumbs to POST /activation-events/client so
 * "when was the kiosk mounted / polling / did it accept this alert and why"
 * is answerable from evidence.
 *
 * - `clientInstanceId()` is fixed for one full page load (a new value ⇒ a
 *   reload). Stable across React re-renders / StrictMode.
 * - `logActivationClientEvent()` batches (~800ms) and flushes with
 *   fetch keepalive; flushes immediately on pagehide/visibility-hidden via
 *   sendBeacon so an unmount/close is not lost.
 * - Fire-and-forget: never throws, never blocks the caller.
 */
import { API } from "./api";

let _id = null;
export function clientInstanceId() {
  if (_id) return _id;
  try {
    _id = (crypto?.randomUUID && crypto.randomUUID()) ||
      `ci_${Math.random().toString(36).slice(2)}_${Date.now()}`;
  } catch {
    _id = `ci_${Math.random().toString(36).slice(2)}_${Date.now()}`;
  }
  return _id;
}

let _buf = [];
let _timer = null;

function _flush(useBeacon = false) {
  if (_timer) { clearTimeout(_timer); _timer = null; }
  if (!_buf.length) return;
  const events = _buf;
  _buf = [];
  const body = JSON.stringify({ events });
  try {
    if (useBeacon && navigator.sendBeacon) {
      navigator.sendBeacon(`${API}/activation-events/client`, new Blob([body], { type: "application/json" }));
      return;
    }
    fetch(`${API}/activation-events/client`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    }).catch(() => {});
  } catch { /* never let telemetry touch the kiosk */ }
}

/**
 * @param {string} event  one of the server allow-list (kiosk_mounted,
 *   kiosk_unmounted, page_hidden, page_visible, poll_started, poll_stopped,
 *   alert_first_seen, alert_cleared, wake_accepted, wake_rejected,
 *   mic_requested, mic_acquired, mic_failed, session_mint_started,
 *   session_ended_client)
 * @param {object} fields  { room, kiosk_id, resident_id, alert_id,
 *   activation_id, session_id, data }
 */
export function logActivationClientEvent(event, fields = {}) {
  try {
    _buf.push({
      event,
      client_instance_id: clientInstanceId(),
      ts_client: new Date().toISOString(),
      room: fields.room ?? null,
      kiosk_id: fields.kiosk_id ?? null,
      resident_id: fields.resident_id ?? null,
      alert_id: fields.alert_id ?? null,
      activation_id: fields.activation_id ?? null,
      session_id: fields.session_id ?? null,
      data: fields.data ?? null,
    });
    if (!_timer) _timer = setTimeout(() => _flush(false), 800);
  } catch { /* ignore */ }
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") _flush(true);
  });
  window.addEventListener("pagehide", () => _flush(true));
}
