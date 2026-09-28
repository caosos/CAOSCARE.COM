import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";

export const SCHEDULE_CATEGORIES = ["activity", "facility_note", "staff_hours"];
export const SCHEDULE_CATEGORY_LABELS = {
  activity: "Activity", facility_note: "Announcement", staff_hours: "Staff note (not shown to residents)",
};

// Add a schedule entry (published at once - the author is the reviewer) or
// correct an existing one (routes/schedule.py::update_schedule_item).
export default function ScheduleItemDialog({ open, onOpenChange, date, item = null, onSaved }) {
  const blank = { date, time_label: "", title: "", description: "", category: "activity" };
  const [form, setForm] = useState(blank);

  useEffect(() => {
    if (!open) return;
    setForm(item
      ? { date: item.date, time_label: item.time_label || "", title: item.title,
          description: item.description || "", category: item.category }
      : { ...blank, date });
  }, [open, item, date]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (e) => {
    e.preventDefault();
    try {
      if (item) await api.patch(`/schedule/${item.schedule_id}`, form);
      else await api.post("/schedule", form);
      toast.success(item?.status === "draft" ? "Saved — still a draft until published" : "Saved — residents see this now");
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader><DialogTitle className="font-display">{item ? "Correct schedule entry" : "New schedule entry"}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Date</Label><Input type="date" required value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="sched-date" /></div>
            <div><Label>Time (optional)</Label><Input placeholder="2:00 PM" value={form.time_label} onChange={(e) => setForm({ ...form, time_label: e.target.value })} data-testid="sched-time" /></div>
          </div>
          <div><Label>Title</Label><Input required placeholder="Bingo" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="sched-title" /></div>
          <div><Label>Where / details (optional)</Label><Textarea placeholder="Main activity room" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="sched-desc" /></div>
          <div>
            <Label>Type</Label>
            <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
              <SelectTrigger data-testid="sched-cat"><SelectValue /></SelectTrigger>
              <SelectContent>{SCHEDULE_CATEGORIES.map((c) => <SelectItem key={c} value={c}>{SCHEDULE_CATEGORY_LABELS[c]}</SelectItem>)}</SelectContent>
            </Select>
          </div>
          <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="sched-save">Save</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
