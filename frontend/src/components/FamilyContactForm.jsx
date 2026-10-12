import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Checkbox } from "./ui/checkbox";
import { toast } from "sonner";

export const NOTIFY_OPTIONS = [
  { key: "emergency", label: "Emergency" },
  { key: "assist", label: "Assist calls" },
  { key: "wander", label: "Wander / geofence" },
  { key: "daily_summary", label: "Daily summary" },
];
const EMPTY = { resident_id: "", name: "", relationship: "", email: "", phone: "", notify_on: ["emergency", "wander"] };

// One form for adding and editing a family contact. Editing keeps the resident
// fixed (a contact belongs to one resident) and never touches call approval,
// which stays its own admin-only control in the table.
export default function FamilyContactForm({ open, onOpenChange, residents, contact = null, onSaved }) {
  const editing = !!contact;
  const [form, setForm] = useState(EMPTY);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) setForm(editing ? { resident_id: contact.resident_id, name: contact.name || "", relationship: contact.relationship || "",
      email: contact.email || "", phone: contact.phone || "", notify_on: contact.notify_on || [] } : EMPTY);
  }, [open, contact]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (key) => setForm((f) => ({ ...f, notify_on: f.notify_on.includes(key) ? f.notify_on.filter((k) => k !== key) : [...f.notify_on, key] }));
  const resident = (residents || []).find((r) => r.resident_id === form.resident_id);

  const save = async (e) => {
    e.preventDefault();
    if (!form.resident_id) { toast.error("Select a resident"); return; }
    setBusy(true);
    try {
      if (editing) {
        const { resident_id, ...fields } = form;   // eslint-disable-line no-unused-vars
        const { data } = await api.patch(`/family-contacts/${contact.contact_id}`, fields);
        toast.success(data.changed?.length ? "Contact updated" : "No changes to save");
      } else {
        await api.post("/family-contacts", form);
        toast.success("Family contact added");
      }
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save the contact");
    }
    setBusy(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display">{editing ? `Edit ${contact.name}` : "New family contact"}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="space-y-3">
          <div>
            <Label>Resident</Label>
            {editing ? (
              <div className="text-sm py-2" data-testid="fam-resident-fixed">{resident ? `${resident.name} · Room ${resident.room}` : form.resident_id}</div>
            ) : (
              <Select value={form.resident_id} onValueChange={(v) => setForm({ ...form, resident_id: v })}>
                <SelectTrigger data-testid="fam-resident"><SelectValue placeholder="Pick a resident" /></SelectTrigger>
                <SelectContent>
                  {(residents || []).map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Room {r.room}</SelectItem>)}
                </SelectContent>
              </Select>
            )}
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div><Label>Name</Label><Input required data-testid="fam-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Liam O'Brien" /></div>
            <div><Label>Relationship</Label><Input data-testid="fam-rel" value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })} placeholder="son" /></div>
          </div>
          <div>
            <Label>Phone (SMS)</Label>
            <Input data-testid="fam-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+15551234567" />
            {editing && contact.allow_calls && <p className="text-xs text-caos-mute mt-1">This contact is approved for resident calls; only an owner or admin can change the number.</p>}
          </div>
          <div><Label>Email</Label><Input type="email" data-testid="fam-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="family@example.com" /></div>
          <div>
            <Label>Notify on</Label>
            <div className="grid grid-cols-2 gap-2 mt-2">
              {NOTIFY_OPTIONS.map((opt) => (
                <label key={opt.key} className="flex items-center gap-2 cursor-pointer" data-testid={`fam-notify-${opt.key}`}>
                  <Checkbox checked={form.notify_on.includes(opt.key)} onCheckedChange={() => toggle(opt.key)} />
                  <span className="text-sm">{opt.label}</span>
                </label>
              ))}
            </div>
          </div>
          <DialogFooter><Button type="submit" disabled={busy} className="bg-caos-forest" data-testid="fam-save">{busy ? "Saving…" : "Save"}</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
