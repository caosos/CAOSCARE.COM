import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Checkbox } from "../components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Plus, Trash2, Pill } from "lucide-react";
import { toast } from "sonner";

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];

export default function MedicationsTab({ residents }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const empty = { resident_id: "", title: "", time_hhmm: "08:00", dose_notes: "", days: DAYS, active: true };
  const [form, setForm] = useState(empty);

  const fetchAll = async () => {
    try { const { data } = await api.get("/medications"); setItems(data); }
    catch { toast.error("Could not load reminders"); }
  };
  useEffect(() => { fetchAll(); }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      await api.post("/medications", form);
      toast.success("Reminder added");
      setOpen(false);
      setForm(empty);
      fetchAll();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this reminder?")) return;
    await api.delete(`/medications/${id}`);
    toast.success("Deleted");
    fetchAll();
  };

  const toggleDay = (d) => {
    setForm((f) => ({ ...f, days: f.days.includes(d) ? f.days.filter((x) => x !== d) : [...f.days, d] }));
  };

  return (
    <Card className="border-caos-line p-6" data-testid="medications-tab-root">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest flex items-center gap-2">
            <Pill className="w-5 h-5" /> Medication reminders
          </h2>
          <p className="text-caos-mute text-sm mt-1">
            Scheduled voice prompts. The room kiosk speaks each reminder at the chosen minute, then logs the
            acknowledgement so it doesn't repeat.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-med-btn">
              <Plus className="w-4 h-4 mr-2" /> New reminder
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-display">New medication reminder</DialogTitle></DialogHeader>
            <form onSubmit={save} className="space-y-3">
              <div>
                <Label>Resident</Label>
                <Select value={form.resident_id} onValueChange={(v) => setForm({ ...form, resident_id: v })}>
                  <SelectTrigger data-testid="med-resident"><SelectValue placeholder="Select resident" /></SelectTrigger>
                  <SelectContent>
                    {(residents || []).map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Rm {r.room}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Title</Label><Input required data-testid="med-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} placeholder="Blood pressure pill" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Time (HH:MM, 24h)</Label><Input required pattern="[0-2][0-9]:[0-5][0-9]" data-testid="med-time" value={form.time_hhmm} onChange={(e) => setForm({ ...form, time_hhmm: e.target.value })} /></div>
                <div><Label>Dose notes</Label><Input data-testid="med-notes" value={form.dose_notes} onChange={(e) => setForm({ ...form, dose_notes: e.target.value })} placeholder="One white tablet" /></div>
              </div>
              <div>
                <Label>Days</Label>
                <div className="flex gap-1 mt-1 flex-wrap">
                  {DAYS.map((d) => (
                    <button
                      type="button"
                      key={d}
                      onClick={() => toggleDay(d)}
                      data-testid={`med-day-${d}`}
                      className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border-2 transition-colors ${
                        form.days.includes(d) ? "bg-caos-forest text-white border-caos-forest" : "bg-white text-caos-mute border-caos-line"
                      }`}
                    >{d}</button>
                  ))}
                </div>
              </div>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="med-active">
                <Checkbox checked={form.active} onCheckedChange={(v) => setForm({ ...form, active: !!v })} />
                <span className="text-sm font-semibold text-caos-forest">Active</span>
              </label>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="med-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Table>
        <TableHeader><TableRow>
          <TableHead>Resident</TableHead><TableHead>Medication</TableHead><TableHead>Time</TableHead>
          <TableHead>Days</TableHead><TableHead>Active</TableHead><TableHead></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {items.map((m) => (
            <TableRow key={m.reminder_id} data-testid={`med-row-${m.reminder_id}`}>
              <TableCell>
                <div className="font-medium">{m.resident_name}</div>
                <div className="text-caos-mute text-xs">Room {m.room || "—"}</div>
              </TableCell>
              <TableCell>
                <div className="font-medium">{m.title}</div>
                <div className="text-caos-mute text-xs">{m.dose_notes}</div>
              </TableCell>
              <TableCell className="font-mono text-lg tabular-nums">{m.time_hhmm}</TableCell>
              <TableCell>
                <div className="flex gap-1 flex-wrap">
                  {DAYS.map((d) => (
                    <span key={d} className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded ${(m.days || []).includes(d) ? "bg-caos-forest text-white" : "bg-caos-line text-caos-mute"}`}>{d[0]}</span>
                  ))}
                </div>
              </TableCell>
              <TableCell>{m.active ? <Badge className="bg-caos-moss text-white">ACTIVE</Badge> : <Badge variant="outline">paused</Badge>}</TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(m.reminder_id)} data-testid={`del-med-${m.reminder_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={6} className="text-center text-caos-mute py-6">No reminders yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </Card>
  );
}
