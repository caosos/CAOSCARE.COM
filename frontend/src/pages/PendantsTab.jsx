import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Trash2, Plus, Radio, Battery, BatteryLow, Zap } from "lucide-react";
import { toast } from "sonner";

export default function PendantsTab({ residents }) {
  const [pendants, setPendants] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ pendant_id: "", frequency_mhz: "", resident_id: "", battery_percent: 100, status: "active", notes: "" });
  const [testOpen, setTestOpen] = useState(false);
  const [testForm, setTestForm] = useState({ frequency_mhz: "", event_type: "press", zone: "Hallway A", signal_strength: 82 });

  const fetchPendants = async () => {
    try {
      const { data } = await api.get("/pendants");
      setPendants(data);
    } catch { toast.error("Failed to load pendants"); }
  };
  useEffect(() => { fetchPendants(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form, frequency_mhz: parseFloat(form.frequency_mhz), battery_percent: parseInt(form.battery_percent) };
      if (!payload.resident_id) delete payload.resident_id;
      await api.post("/pendants", payload);
      toast.success("Pendant registered");
      setOpen(false);
      setForm({ pendant_id: "", frequency_mhz: "", resident_id: "", battery_percent: 100, status: "active", notes: "" });
      fetchPendants();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove this pendant registration?")) return;
    await api.delete(`/pendants/${id}`);
    toast.success("Removed");
    fetchPendants();
  };

  const simulateEvent = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        frequency_mhz: parseFloat(testForm.frequency_mhz),
        event_type: testForm.event_type,
        zone: testForm.zone,
        signal_strength: parseInt(testForm.signal_strength),
      };
      const { data } = await api.post("/pendants/event", payload);
      toast.success(data.alert ? "Alert created via pendant" : "Pendant ping recorded");
      setTestOpen(false);
      fetchPendants();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Card className="border-caos-line p-6" data-testid="pendants-panel">
      <div className="flex justify-between items-start mb-4 flex-wrap gap-3">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Pendant registry</h2>
          <p className="text-caos-mute text-sm mt-1 max-w-2xl">
            Each pendant transmits on its own frequency. The Android tablet's USB RF receiver
            hears the press and POSTs <code className="text-xs bg-caos-ambient px-1.5 py-0.5 rounded">/api/pendants/event</code>
            to identify the resident and page staff.
          </p>
        </div>
        <div className="flex gap-2">
          <Dialog open={testOpen} onOpenChange={setTestOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="border-2 rounded-full" data-testid="test-pendant-btn">
                <Zap className="w-4 h-4 mr-2" /> Simulate press
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle className="font-display">Simulate pendant event</DialogTitle></DialogHeader>
              <form onSubmit={simulateEvent} className="space-y-4">
                <div>
                  <Label>Frequency (MHz)</Label>
                  <Select value={testForm.frequency_mhz} onValueChange={(v) => setTestForm({ ...testForm, frequency_mhz: v })}>
                    <SelectTrigger data-testid="test-freq-select"><SelectValue placeholder="Pick a pendant" /></SelectTrigger>
                    <SelectContent>
                      {pendants.map((p) => (
                        <SelectItem key={p.pendant_device_id} value={String(p.frequency_mhz)}>
                          {p.frequency_mhz} MHz — {p.resident_name || "(unassigned)"} · {p.pendant_id}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Event type</Label>
                  <Select value={testForm.event_type} onValueChange={(v) => setTestForm({ ...testForm, event_type: v })}>
                    <SelectTrigger data-testid="test-event-select"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="press">Button press</SelectItem>
                      <SelectItem value="fall">Fall detected</SelectItem>
                      <SelectItem value="periodic_ping">Periodic ping (no alert)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div><Label>Zone reported by receiver tablet</Label>
                  <Input value={testForm.zone} onChange={(e) => setTestForm({ ...testForm, zone: e.target.value })} data-testid="test-zone" />
                </div>
                <DialogFooter>
                  <Button type="submit" className="bg-caos-forest" data-testid="test-fire">Fire event</Button>
                </DialogFooter>
              </form>
            </DialogContent>
          </Dialog>

          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-pendant-btn">
                <Plus className="w-4 h-4 mr-2" /> Register pendant
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle className="font-display">New pendant</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Pendant serial / label</Label><Input required data-testid="pendant-id" value={form.pendant_id} onChange={(e) => setForm({ ...form, pendant_id: e.target.value })} placeholder="PEN-0119" /></div>
                  <div><Label>Frequency (MHz)</Label><Input required type="number" step="0.0001" data-testid="pendant-freq" value={form.frequency_mhz} onChange={(e) => setForm({ ...form, frequency_mhz: e.target.value })} placeholder="916.1250" /></div>
                </div>
                <div>
                  <Label>Assign to resident (optional)</Label>
                  <Select value={form.resident_id || "__none__"} onValueChange={(v) => setForm({ ...form, resident_id: v === "__none__" ? "" : v })}>
                    <SelectTrigger data-testid="pendant-resident"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— Unassigned —</SelectItem>
                      {(residents || []).map((r) => (
                        <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Room {r.room}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div><Label>Battery %</Label><Input type="number" min="0" max="100" value={form.battery_percent} onChange={(e) => setForm({ ...form, battery_percent: e.target.value })} /></div>
                  <div>
                    <Label>Status</Label>
                    <Select value={form.status} onValueChange={(v) => setForm({ ...form, status: v })}>
                      <SelectTrigger><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="inactive">Inactive</SelectItem>
                        <SelectItem value="lost">Lost</SelectItem>
                        <SelectItem value="low_battery">Low battery</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
                <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="pendant-save">Save</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Pendant</TableHead>
            <TableHead>Frequency</TableHead>
            <TableHead>Resident</TableHead>
            <TableHead>Battery</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Last seen</TableHead>
            <TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {pendants.map((p) => (
            <TableRow key={p.pendant_device_id} data-testid={`pendant-row-${p.pendant_device_id}`}>
              <TableCell className="font-mono text-xs">{p.pendant_id}</TableCell>
              <TableCell className="font-mono">
                <span className="inline-flex items-center gap-1"><Radio className="w-3.5 h-3.5 text-caos-forest" /> {p.frequency_mhz}</span>
              </TableCell>
              <TableCell>{p.resident_name ? `${p.resident_name} · ${p.room}` : <span className="text-caos-mute">Unassigned</span>}</TableCell>
              <TableCell>
                <span className="inline-flex items-center gap-1">
                  {(p.battery_percent ?? 0) < 25
                    ? <BatteryLow className="w-4 h-4 text-caos-terracotta" />
                    : <Battery className="w-4 h-4 text-caos-moss" />}
                  {p.battery_percent ?? "—"}%
                </span>
              </TableCell>
              <TableCell>
                <Badge variant="outline" className="uppercase text-xs tracking-wider">
                  {p.status}
                </Badge>
              </TableCell>
              <TableCell className="text-caos-mute text-xs">
                {p.last_seen_at ? new Date(p.last_seen_at).toLocaleString() : "Never"}
              </TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(p.pendant_device_id)} data-testid={`del-pendant-${p.pendant_device_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {pendants.length === 0 && (
            <TableRow><TableCell colSpan={7} className="text-center text-caos-mute py-8">No pendants registered yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <div className="mt-6 bg-caos-ambient rounded-xl p-4 text-sm text-caos-ink/80">
        <p className="font-semibold text-caos-forest mb-1">Android bridge payload</p>
        <p className="text-caos-mute mb-2">The tablet-side bridge app POSTs to <code>/api/pendants/event</code> with:</p>
        <pre className="bg-white border border-caos-line rounded p-3 text-xs overflow-x-auto"><code>{`{
  "frequency_mhz": 916.1250,
  "signal_strength": 82,
  "battery_percent": 87,
  "event_type": "press",      // or "fall" or "periodic_ping"
  "zone": "Hallway A",         // the receiver tablet's known zone
  "device_token": "…"          // reserved for signed device auth (P1)
}`}</code></pre>
      </div>
    </Card>
  );
}
