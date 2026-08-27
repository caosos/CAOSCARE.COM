import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Trash2, Plus, Lightbulb, Fan, Thermometer, Tv, Volume2, Power, Zap } from "lucide-react";
import { toast } from "sonner";

const KIND_ICON = {
  light: Lightbulb, fan: Fan, heater: Thermometer, ac: Thermometer, thermostat: Thermometer,
  tv: Tv, speaker: Volume2, blinds: Power, outlet: Power,
  humidifier: Thermometer, bed: Power, door_lock: Power, generic: Power,
};

const ALL_CAPS = ["power", "brightness", "temperature", "fan_speed", "volume", "channel", "input", "color", "position"];
// "mock" first and separated visually below via the badge - no bridge/hardware
// exists for it, so it's the only protocol that actually works end-to-end
// today. The rest are real transports, wired for the bridge-tablet queue
// path but pending physical hardware (see docs/reports for current status).
const PROTOCOLS = ["mock", "home_assistant", "bluetooth", "wifi", "rf_433", "rf_915", "ir", "zigbee", "matter"];
const KINDS = ["light", "fan", "heater", "ac", "thermostat", "tv", "speaker", "blinds", "outlet", "humidifier", "bed", "door_lock", "generic"];

export default function DevicesTab({ residents }) {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const emptyForm = { label: "", kind: "light", protocol: "bluetooth", room: "", resident_id: "", endpoint: "", capabilities: ["power"], vendor: "", model: "", notes: "" };
  const [form, setForm] = useState(emptyForm);
  const [testOpen, setTestOpen] = useState(null); // device object or null

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/devices");
      setItems(data);
    } catch { toast.error("Could not load devices"); }
  };
  useEffect(() => { fetchAll(); }, []);

  const save = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form };
      if (!payload.resident_id) delete payload.resident_id;
      await api.post("/devices", payload);
      toast.success("Device added");
      setOpen(false);
      setForm(emptyForm);
      fetchAll();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove this device?")) return;
    await api.delete(`/devices/${id}`);
    toast.success("Removed");
    fetchAll();
  };

  const toggleCap = (c) => {
    setForm({ ...form, capabilities: form.capabilities.includes(c) ? form.capabilities.filter((x) => x !== c) : [...form.capabilities, c] });
  };

  const sendCommand = async (dev, action, value) => {
    try {
      await api.post(`/devices/${dev.device_id}/command`, { action, value });
      toast.success(`${action}=${value} queued`);
      fetchAll();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  return (
    <Card className="border-caos-line p-6" data-testid="devices-panel">
      <div className="flex justify-between items-start mb-4 flex-wrap gap-3">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Smart-room devices</h2>
          <p className="text-caos-mute text-sm mt-1 max-w-2xl">
            Lights, fans, heaters, TVs, locks — anything the resident's tablet can reach over BLE / WiFi / RF / IR / Zigbee / Matter.
            Commands queue to the room's bridge tablet, which executes them locally.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-device-btn">
              <Plus className="w-4 h-4 mr-2" /> Add device
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="font-display">New smart-room device</DialogTitle></DialogHeader>
            <form onSubmit={save} className="space-y-3">
              <div><Label>Label</Label><Input required data-testid="dev-label" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} placeholder="Bedside lamp" /></div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Kind</Label>
                  <Select value={form.kind} onValueChange={(v) => setForm({ ...form, kind: v })}>
                    <SelectTrigger data-testid="dev-kind"><SelectValue /></SelectTrigger>
                    <SelectContent>{KINDS.map((k) => <SelectItem key={k} value={k}>{k}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Protocol</Label>
                  <Select value={form.protocol} onValueChange={(v) => setForm({ ...form, protocol: v })}>
                    <SelectTrigger data-testid="dev-protocol"><SelectValue /></SelectTrigger>
                    <SelectContent>{PROTOCOLS.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Room</Label><Input data-testid="dev-room" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} placeholder="101" /></div>
                <div>
                  <Label>Resident</Label>
                  <Select value={form.resident_id || "__none__"} onValueChange={(v) => setForm({ ...form, resident_id: v === "__none__" ? "" : v })}>
                    <SelectTrigger data-testid="dev-resident"><SelectValue placeholder="Optional" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">— Unassigned —</SelectItem>
                      {(residents || []).map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>Endpoint</Label><Input data-testid="dev-endpoint" value={form.endpoint} onChange={(e) => setForm({ ...form, endpoint: e.target.value })} placeholder="MAC / IP / RF code / zigbee id" /></div>
              <div>
                <Label>Capabilities</Label>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  {ALL_CAPS.map((c) => (
                    <label key={c} className="flex items-center gap-2 cursor-pointer text-sm" data-testid={`cap-${c}`}>
                      <Checkbox checked={form.capabilities.includes(c)} onCheckedChange={() => toggleCap(c)} />
                      {c}
                    </label>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Vendor</Label><Input value={form.vendor} onChange={(e) => setForm({ ...form, vendor: e.target.value })} /></div>
                <div><Label>Model</Label><Input value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} /></div>
              </div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="dev-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Device</TableHead><TableHead>Room</TableHead><TableHead>Protocol</TableHead><TableHead>Capabilities</TableHead><TableHead>State</TableHead><TableHead>Actions</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((d) => {
            const Icon = KIND_ICON[d.kind] || Power;
            return (
              <TableRow key={d.device_id} data-testid={`dev-row-${d.device_id}`}>
                <TableCell><span className="inline-flex items-center gap-2 font-medium"><Icon className="w-4 h-4 text-caos-forest" /> {d.label}</span></TableCell>
                <TableCell>{d.room || "—"}</TableCell>
                <TableCell>
                  <Badge variant="outline" className={`text-xs ${d.protocol === "mock" ? "border-caos-amber text-caos-amber" : "border-caos-forest text-caos-forest"}`}>
                    {d.protocol === "mock" ? "MOCK — no hardware" : d.protocol}
                  </Badge>
                </TableCell>
                <TableCell><div className="flex flex-wrap gap-1">{(d.capabilities || []).map((c) => <Badge key={c} variant="outline" className="text-xs">{c}</Badge>)}</div></TableCell>
                <TableCell className="font-mono text-xs">{Object.entries(d.state || {}).map(([k, v]) => `${k}=${v}`).join(" · ") || "—"}</TableCell>
                <TableCell>
                  <div className="flex gap-1 flex-wrap">
                    {d.capabilities?.includes("power") && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => sendCommand(d, "power", "on")} data-testid={`on-${d.device_id}`}>On</Button>
                        <Button size="sm" variant="outline" onClick={() => sendCommand(d, "power", "off")} data-testid={`off-${d.device_id}`}>Off</Button>
                      </>
                    )}
                    {d.capabilities?.includes("brightness") && (
                      <Button size="sm" variant="outline" onClick={() => sendCommand(d, "brightness", 50)}>50%</Button>
                    )}
                    {d.capabilities?.includes("temperature") && (
                      <>
                        <Button size="sm" variant="outline" onClick={() => sendCommand(d, "temperature", 20)}>20°</Button>
                        <Button size="sm" variant="outline" onClick={() => sendCommand(d, "temperature", 24)}>24°</Button>
                      </>
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Button variant="ghost" size="sm" onClick={() => remove(d.device_id)} data-testid={`del-dev-${d.device_id}`}>
                    <Trash2 className="w-4 h-4 text-caos-terracotta" />
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={7} className="text-center text-caos-mute py-6">No smart devices yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <div className="mt-6 bg-caos-ambient rounded-xl p-4 text-sm text-caos-ink/80">
        <p className="font-semibold text-caos-forest mb-1">How the tablet executes commands</p>
        <p>
          Commands queue at <code className="text-xs bg-white px-1 rounded">GET /api/devices/queue/{`{room}`}</code>.
          The room's bridge tablet polls this endpoint, executes locally (BLE GATT / WiFi HTTP / RF transmit via the same RFM69 board / IR blaster / Zigbee dongle), then POSTs
          <code className="text-xs bg-white px-1 rounded ml-1">/api/devices/queue/{`{command_id}`}/ack</code> with status = executed or failed.
        </p>
      </div>
    </Card>
  );
}
