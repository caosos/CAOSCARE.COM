/**
 * Room-page side of the local "Aria" wake-word protocol
 * (room-node/aria_wake/aria_wake.py). The detector is endpoint-specific
 * (a Python process on the EliteDesk today, a native service on an Android
 * endpoint later); this WebSocket contract is the portable part.
 *
 *   detector -> page  hello | wake | listening (return-to-wake ack)
 *   page -> detector  { type: "state", state: "conversation" | "listening", reason }
 *
 * Reconnects with backoff forever - the detector may start after the page.
 */
export const DEFAULT_WAKE_URL = "ws://127.0.0.1:8765";

/** `?wake=1` (default URL) or `?wake=ws://host:port` on the room page URL
 * enables the listener for this endpoint; absent = feature off. */
export function wakeUrlFromSearch(search) {
  const v = new URLSearchParams(search || "").get("wake");
  if (!v || v === "0") return null;
  return v === "1" ? DEFAULT_WAKE_URL : v;
}

export function connectWakeWord({ url, onMessage, onOpen, onClose, WebSocketImpl = WebSocket }) {
  let ws = null;
  let closed = false;
  let delay = 1000;
  let timer = null;
  let lastState = null;

  const send = (obj) => {
    try { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); } catch { /* reconnect handles it */ }
  };

  const open = () => {
    if (closed) return;
    ws = new WebSocketImpl(url);
    ws.onopen = () => {
      delay = 1000;
      if (lastState) send(lastState);   // re-assert page state after a detector restart
      onOpen?.();
    };
    ws.onmessage = (ev) => {
      try { onMessage?.(JSON.parse(ev.data)); } catch { /* ignore malformed frames */ }
    };
    ws.onclose = () => {
      onClose?.();
      if (closed) return;
      timer = setTimeout(open, delay);
      delay = Math.min(delay * 2, 10000);
    };
  };
  open();

  return {
    setState(state, reason) {
      lastState = { type: "state", state, reason: reason || null };
      send(lastState);
    },
    close() {
      closed = true;
      clearTimeout(timer);
      try { ws?.close(); } catch { /* ignore */ }
    },
  };
}
