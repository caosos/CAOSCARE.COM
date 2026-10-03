import React, { useState } from "react";
import { toast } from "sonner";
import { Send, RotateCcw } from "lucide-react";
import { API } from "../../../lib/api";

// Demo kiosk controls: type to Aria (same conversation as voice - see
// realtimeTypedTurn.js) and DEMO RESET (routes/demo_kiosk.py).
// `onSend(text)` returns true when the text reached Aria.
export function DemoTypedInput({ onSend, placeholder = "Type to Aria, e.g. “Turn the light on.”" }) {
  const [text, setText] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    const ok = await onSend(value);
    if (ok) setText("");
    else toast.error("Aria isn't connected yet. Try again in a moment.");
  };
  return (
    <form onSubmit={submit} className="flex gap-2 w-full" data-testid="demo-typed-form">
      <input
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder={placeholder}
        aria-label="Type a message to Aria"
        data-testid="demo-typed-input"
        className="flex-1 min-w-0 rounded-full border-2 border-caos-line bg-white px-5 py-3 text-lg focus:outline-none focus:border-caos-forest"
      />
      <button type="submit" data-testid="demo-typed-send"
        className="shrink-0 rounded-full bg-caos-forest text-white px-5 py-3 font-semibold flex items-center gap-2 hover:bg-caos-forest-hover">
        <Send className="w-5 h-5" /> Send
      </button>
    </form>
  );
}

export function DemoResetButton({ onDone }) {
  const [busy, setBusy] = useState(false);
  const reset = async () => {
    setBusy(true);
    try {
      const r = await fetch(`${API}/demo/reset`, { method: "POST" });
      const body = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(body.detail || `reset failed (${r.status})`);
      toast.success(`Demo reset: room ${body.room} back to baseline${body.requests_closed ? `, ${body.requests_closed} request(s) closed` : ""}.`);
      onDone?.(body);
    } catch (e) {
      toast.error(e.message || "Demo reset failed.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <button type="button" onClick={reset} disabled={busy} data-testid="demo-reset-btn"
      className="rounded-full border-2 border-caos-mute text-caos-mute px-4 py-2 text-sm font-bold uppercase tracking-widest flex items-center gap-2 hover:border-caos-forest hover:text-caos-forest disabled:opacity-50">
      <RotateCcw className="w-4 h-4" /> {busy ? "Resetting…" : "Demo reset"}
    </button>
  );
}
