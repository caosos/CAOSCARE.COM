import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

const CATEGORIES = ["activity", "facility_note", "staff_hours"];
const CATEGORY_LABELS = { activity: "Activity", facility_note: "Facility note", staff_hours: "Staff hours" };

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function ScheduleTab() {
  const [date, setDate] = useState(todayLocal());
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const empty = { date: todayLocal(), time_label: "", title: "", description: "", category: "activity" };
  const [form, setForm] = useState(empty);

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/schedule", { params: { date } });
      setItems(data);
    } catch {
      toast.error("Could not load schedule");
    }
  };
  useEffect(() => { fetchAll(); }, [date]); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/schedule", form);
      toast.success("Added to schedule");
      setOpen(false);
      setForm({ ...empty, date });
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this schedule item?")) return;
    await api.delete(`/schedule/${id}`);
    toast.success("Deleted");
    fetchAll();
  };

  return (
    <Card className="border-caos-line p-6" data-testid="schedule-tab-root">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Daily schedule</h2>
          <p className="text-caos-mute text-sm mt-1">
            What Aria tells residents when they ask "what's happening today." Only what's listed here is ever spoken — nothing is guessed.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Input
            type="date"
            value={date}
            onChange={(e) => setDate(e.target.value)}
            className="w-auto"
            data-testid="schedule-date-picker"
          />
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-schedule-btn">
                <Plus className="w-4 h-4 mr-2" /> Add
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle className="font-display">New schedule item</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Date</Label><Input type="date" required value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="sched-date" /></div>
                  <div><Label>Time (optional)</Label><Input placeholder="2:00 PM" value={form.time_label} onChange={(e) => setForm({ ...form, time_label: e.target.value })} data-testid="sched-time" /></div>
                </div>
                <div><Label>Title</Label><Input required placeholder="Bingo in the common room" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} data-testid="sched-title" /></div>
                <div><Label>Description (optional)</Label><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="sched-desc" /></div>
                <div>
                  <Label>Category</Label>
                  <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                    <SelectTrigger data-testid="sched-cat"><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{CATEGORY_LABELS[c]}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="sched-save">Add</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time</TableHead><TableHead>Item</TableHead><TableHead>Category</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((i) => (
            <TableRow key={i.schedule_id} data-testid={`sched-row-${i.schedule_id}`}>
              <TableCell className="text-sm tabular-nums">{i.time_label || "—"}</TableCell>
              <TableCell>
                <div className="font-medium">{i.title}</div>
                {i.description && <div className="text-caos-mute text-xs">{i.description}</div>}
              </TableCell>
              <TableCell><Badge variant="outline">{CATEGORY_LABELS[i.category] || i.category}</Badge></TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(i.schedule_id)} data-testid={`del-sched-${i.schedule_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={4} className="text-center text-caos-mute py-6">Nothing scheduled for this date yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </Card>
  );
}
