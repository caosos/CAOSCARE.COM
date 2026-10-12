import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { toast } from "sonner";

// How and when to call someone back on a front-desk callback request
// (careops-frontdesk-callback-contact-fields-001). Staff-only: the resident
// screen and Aria never show it. Saving goes through the same PATCH and
// receipted details step as the other request details; it records a number
// and a time to call, not that a call happened.
export default function CallbackContactEditor({ task, canEdit, onSaved }) {
  const [phone, setPhone] = useState("");
  const [when, setWhen] = useState("");
  const [saving, setSaving] = useState(false);
  useEffect(() => { setPhone(task?.callback_phone || ""); setWhen(task?.callback_window || ""); }, [task]);

  if (!task) return null;
  if (!canEdit) {
    if (!task.callback_phone && !task.callback_window) return null;
    return (
      <div className="mb-4 text-sm" data-testid="callback-readonly">
        <span className="text-caos-mute">Call back (staff only)</span>
        <div>{[task.callback_phone, task.callback_window].filter(Boolean).join(" · ")}</div>
      </div>
    );
  }
  const save = async () => {
    setSaving(true);
    try {
      await api.patch(`/tasks/${task.task_id}`, { callback_phone: phone.trim(), callback_window: when.trim() });
      toast.success("Callback details saved");
      onSaved?.();
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(Array.isArray(d) ? d.map((x) => String(x.msg || "").replace(/^Value error, /, "")).join(" ") : d || "Could not save");
    }
    setSaving(false);
  };
  return (
    <div className="mb-6 rounded-xl border border-caos-line p-3" data-testid="callback-editor">
      <div className="text-caos-mute text-xs uppercase tracking-widest mb-2">Call back (staff only — not shown to the resident or Aria)</div>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-2">
        <Input type="tel" placeholder="Phone to call back (optional)" maxLength={40} value={phone} onChange={(e) => setPhone(e.target.value)} data-testid="callback-phone" />
        <Input placeholder="Best time (e.g. after 2 pm)" maxLength={80} value={when} onChange={(e) => setWhen(e.target.value)} data-testid="callback-window" />
      </div>
      <Button size="sm" variant="outline" className="border-2" disabled={saving} onClick={save} data-testid="callback-save">Save callback details</Button>
    </div>
  );
}
