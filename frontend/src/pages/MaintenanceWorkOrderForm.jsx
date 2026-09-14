import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";

const NONE = "__none";
const PRIORITIES = ["low", "normal", "high", "urgent"];

// Raise a maintenance work order. It is a plain StaffTask - category and
// visibility_role are pinned to "maintenance" so it lands in the Maintenance
// department only (the backend also forces this for a non-admin creator).
// A due date is optional: never invent one just to feed an SLA counter.
export default function MaintenanceWorkOrderForm({ open, onOpenChange, roster, onCreated }) {
  const empty = {
    title: "", description: "", room: "", resident_id: "",
    priority: "normal", assigned_to: "", due_date: "", due_time: "",
  };
  const [form, setForm] = useState(empty);
  const [residents, setResidents] = useState([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm(empty);
    api.get("/residents").then(({ data }) => setResidents(data)).catch(() => setResidents([]));
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const dueAt = () => {
    if (!form.due_date) return undefined;
    const t = form.due_time || "12:00";
    const d = new Date(`${form.due_date}T${t}`);
    return Number.isNaN(d.getTime()) ? undefined : d.toISOString();
  };

  const submit = async (e) => {
    e.preventDefault();
    if (!form.description.trim()) { toast.error("Describe the problem"); return; }
    setSaving(true);
    try {
      const payload = {
        title: (form.title.trim() || form.description.trim()).slice(0, 120),
        description: form.description.trim(),
        category: "maintenance",
        visibility_role: "maintenance",
        priority: form.priority,
      };
      if (form.room.trim()) payload.room = form.room.trim();
      if (form.resident_id) payload.resident_id = form.resident_id;
      if (form.assigned_to) payload.assigned_to = form.assigned_to;
      const due = dueAt();
      if (due) payload.due_at = due;
      await api.post("/tasks", payload);
      toast.success("Work order created");
      onOpenChange(false);
      onCreated?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not create the work order");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto" data-testid="wo-form">
        <DialogHeader><DialogTitle className="font-display">New maintenance work order</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label>Problem / what needs fixing</Label>
            <Textarea required data-testid="wo-description" value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Leaking faucet in the 2nd-floor common bathroom" />
          </div>
          <div>
            <Label>Short title (optional)</Label>
            <Input data-testid="wo-title" value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="Defaults to the problem text" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Room / location</Label>
              <Input data-testid="wo-room" value={form.room}
                onChange={(e) => setForm({ ...form, room: e.target.value })} placeholder="e.g. 214 or Lobby" />
            </div>
            <div>
              <Label>Priority</Label>
              <Select value={form.priority} onValueChange={(v) => setForm({ ...form, priority: v })}>
                <SelectTrigger data-testid="wo-priority"><SelectValue /></SelectTrigger>
                <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Resident (optional)</Label>
              <Select value={form.resident_id || NONE}
                onValueChange={(v) => setForm({ ...form, resident_id: v === NONE ? "" : v })}>
                <SelectTrigger data-testid="wo-resident"><SelectValue placeholder="None" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>None</SelectItem>
                  {residents.map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Rm {r.room}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Assign to (optional)</Label>
              <Select value={form.assigned_to || NONE}
                onValueChange={(v) => setForm({ ...form, assigned_to: v === NONE ? "" : v })}>
                <SelectTrigger data-testid="wo-assignee"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>Unassigned</SelectItem>
                  {(roster || []).map((u) => <SelectItem key={u.user_id} value={u.user_id}>{u.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Due date (optional)</Label>
              <Input type="date" data-testid="wo-due-date" value={form.due_date}
                onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
            </div>
            <div>
              <Label>Due time (optional)</Label>
              <Input type="time" data-testid="wo-due-time" value={form.due_time}
                onChange={(e) => setForm({ ...form, due_time: e.target.value })} disabled={!form.due_date} />
            </div>
          </div>
          <p className="text-xs text-caos-mute">Leave the due date blank if there's no real deadline — don't set a fake one.</p>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
            <Button type="submit" className="bg-caos-forest" disabled={saving} data-testid="wo-save">
              {saving ? "Creating…" : "Create work order"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
