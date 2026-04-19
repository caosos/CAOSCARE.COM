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
import { Trash2, Plus, Watch, Heart, Battery, BatteryLow, Zap } from "lucide-react";
import { toast } from "sonner";

export default function WearablesTab({ residents }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ device_label: "", device_type: "smartwatch", mac_address: "", resident_id: "", status: "active", notes: "" });
  const [testOpen, setTestOpen] = useState(false);
  const [test, setTest] = useState({ wearable_id: "", event_type: "press", zone: "Hallway A", heart_rate: 78 });

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/wearables");
      setItems(data);
    } catch { toast.error("Failed to load wearables"); }
  };
  useEffect(() => { fetchAll(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form };
      if (!payload.resident_id) delete payload.resident_id;
      await api.post("/wearables", payload);
      toast.success("Wearable paired");
      setOpen(false);
      setForm({ device_label: "", device_type: "smartwatch", mac_address: "", resident_id: "", status: "active", notes: "" });
      fetchAll();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove this wearable?")) return;
    await api.delete(`/wearables/${id}`);
    toast.success("Removed");
    fetchAll();
  };

  const simulate = async (e) => {
    e.preventDefault();
    try {
      const payload = {
        wearable_id: test.wearable_id,
        event_type: test.event_type,
        zone: test.zone,
      };
      if (["heart_rate_high", "heart_rate_low"].includes(test.event_type)) {
        payload.heart_rate = parseInt(test.heart_rate);
      }
      const { data } = await api.post("/wearables/event", payload);
      toast.success(data.alert ? "Alert created via wearable" : "Ping recorded");
      setTestOpen(false);
      fetchAll();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  return (
    <Card className="border-caos-line p-6" data-testid="wearables-panel">
      <div className="flex justify-between items-start mb-4 flex-wrap gap-3">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Wearables</h2>
          <p className="text-caos-mute text-sm mt-1 max-w-2xl">
            Pair any device (smartwatch, earbuds, BLE beacon, glasses) that can reach the network.
            Companion apps POST <code className="text-xs bg-caos-ambient px-1.5 py-0.5 rounded">/api/wearables/event</code> with
            <code className="text-xs bg-caos-ambient px-1.5 py-0.5 rounded">{`{wearable_id, event_type, heart_rate?, zone?}`}</code>.
          </p>
        </div>
        <div className="flex gap-2">
          <Dialog open={testOpen} onOpenChange={setTestOpen}>
            <DialogTrigger asChild>
              <Button variant="outline" className="border-2 rounded-full" data-testid="test-wearable-btn">
                <Zap className="w-4 h-4 mr-2" /> Simulate event
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle className="font-display">Simulate wearable event</DialogTitle></DialogHeader>
              <form onSubmit={simulate} className="space-y-4">
                <div>
                  <Label>Wearable</Label>
                  <Select value={test.wearable_id} onValueChange={(v) => setTest({ ...test, wearable_id: v })}>
                    <SelectTrigger data-testid="test-wearable-select"><SelectValue placeholder="Pick a wearable" /></SelectTrigger>
                    <SelectContent>
                      {items.map((w) => (
                        <SelectItem key={w.wearable_id} value={w.wearable_id}>
                          {w.device_label} — {w.resident_name || "(unassigned)"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Event type</Label>
                  <Select value={test.event_type} onValueChange={(v) => setTest({ ...test, event_type: v })}>
                    <SelectTrigger data-testid="test-wearable-event"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="press">Button press</SelectItem>
                      <SelectItem value="fall">Fall detected</SelectItem>
                      <SelectItem value="heart_rate_high">High heart rate</SelectItem>
                      <SelectItem value="heart_rate_low">Low heart rate</SelectItem>
                      <SelectItem value="inactivity">Inactivity</SelectItem>
                      <SelectItem value="periodic_ping">Periodic ping (no alert)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                {["heart_rate_high", "heart_rate_low"].includes(test.event_type) && (
                  <div><Label>Heart rate (BPM)</Label><Input type="number" value={test.heart_rate} onChange={(e) => setTest({ ...test, heart_rate: e.target.value })} /></div>
                )}
                <div><Label>Zone</Label><Input value={test.zone} onChange={(e) => setTest({ ...test, zone: e.target.value })} /></div>
                <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="test-wearable-fire">Fire event</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-wearable-btn">
                <Plus className="w-4 h-4 mr-2" /> Pair wearable
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader><DialogTitle className="font-display">Pair new wearable</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-4">
                <div><Label>Label</Label><Input required data-testid="wear-label" value={form.device_label} onChange={(e) => setForm({ ...form, device_label: e.target.value })} placeholder="Margaret's blue smartwatch" /></div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <Label>Type</Label>
                    <Select value={form.device_type} onValueChange={(v) => setForm({ ...form, device_type: v })}>
                      <SelectTrigger data-testid="wear-type"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="smartwatch">Smartwatch</SelectItem>
                        <SelectItem value="earbuds">Earbuds</SelectItem>
                        <SelectItem value="glasses">Glasses</SelectItem>
                        <SelectItem value="ble_beacon">BLE beacon</SelectItem>
                        <SelectItem value="generic">Generic</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div><Label>MAC address</Label><Input data-testid="wear-mac" value={form.mac_address} onChange={(e) => setForm({ ...form, mac_address: e.target.value })} placeholder="AA:BB:CC:DD:EE:FF" /></div>
                </div>
                <div>
                  <Label>Resident</Label>
                  <Select value={form.resident_id || "__none__"} onValueChange={(v) => setForm({ ...form, resident_id: v === "__none__" ? "" : v })}>
                    <SelectTrigger data-testid="wear-resident"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— Unassigned —</SelectItem>
                      {(residents || []).map((r) => (
                        <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Room {r.room}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div><Label>Notes</Label><Textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
                <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="wear-save">Save</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Device</TableHead><TableHead>Type</TableHead><TableHead>Resident</TableHead><TableHead>HR</TableHead><TableHead>Battery</TableHead><TableHead>Status</TableHead><TableHead>Last seen</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((w) => (
            <TableRow key={w.wearable_id} data-testid={`wear-row-${w.wearable_id}`}>
              <TableCell>
                <span className="inline-flex items-center gap-2 font-medium"><Watch className="w-4 h-4 text-caos-forest" /> {w.device_label}</span>
                {w.mac_address && <span className="text-caos-mute text-xs block font-mono">{w.mac_address}</span>}
              </TableCell>
              <TableCell className="uppercase text-xs tracking-wider font-bold text-caos-forest">{w.device_type.replace("_", " ")}</TableCell>
              <TableCell>{w.resident_name ? `${w.resident_name} · ${w.room}` : <span className="text-caos-mute">Unassigned</span>}</TableCell>
              <TableCell>
                {w.last_heart_rate ? <span className="inline-flex items-center gap-1"><Heart className="w-3.5 h-3.5 text-caos-terracotta" />{w.last_heart_rate}</span> : <span className="text-caos-mute">—</span>}
              </TableCell>
              <TableCell>
                <span className="inline-flex items-center gap-1">
                  {(w.battery_percent ?? 0) < 25 ? <BatteryLow className="w-4 h-4 text-caos-terracotta" /> : <Battery className="w-4 h-4 text-caos-moss" />}
                  {w.battery_percent ?? "—"}%
                </span>
              </TableCell>
              <TableCell><Badge variant="outline" className="uppercase text-xs tracking-wider">{w.status}</Badge></TableCell>
              <TableCell className="text-caos-mute text-xs">{w.last_seen_at ? new Date(w.last_seen_at).toLocaleString() : "Never"}</TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(w.wearable_id)} data-testid={`del-wear-${w.wearable_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={8} className="text-center text-caos-mute py-6">No wearables paired yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <div className="mt-6 bg-caos-ambient rounded-xl p-4 text-sm text-caos-ink/80">
        <p className="font-semibold text-caos-forest mb-1">Companion app payload</p>
        <pre className="bg-white border border-caos-line rounded p-3 text-xs overflow-x-auto"><code>{`POST /api/wearables/event
{
  "wearable_id": "wear_...",   // or match by "mac_address"
  "event_type": "press",        // press | fall | heart_rate_high | heart_rate_low | inactivity | periodic_ping
  "heart_rate": 78,             // optional
  "battery_percent": 92,        // optional
  "zone": "Dining Room",        // optional
  "device_token": "..."         // optional HMAC (see Admin → Device Tokens)
}`}</code></pre>
      </div>
    </Card>
  );
}
