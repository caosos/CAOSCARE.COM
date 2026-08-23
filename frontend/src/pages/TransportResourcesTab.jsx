import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Checkbox } from "../components/ui/checkbox";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

// Transportation resource config (drivers, vehicles, scheduling buffer) -
// admin-only facility configuration. Deliberately does NOT invent vehicle
// capacity - it's left blank until an admin sets it, and the booking
// engine treats an unset capacity as "no room to share" rather than
// guessing.

function DriverSection({ drivers, onChange }) {
  const [form, setForm] = useState({ name: "", is_flex: false });
  const add = async () => {
    if (!form.name.trim()) return;
    try {
      await api.post("/transportation/drivers", form);
      setForm({ name: "", is_flex: false });
      onChange();
    } catch { toast.error("Could not add driver"); }
  };
  const toggle = async (d, field) => {
    try { await api.patch(`/transportation/drivers/${d.driver_id}`, { [field]: !d[field] }); onChange(); }
    catch { toast.error("Could not update driver"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Remove this driver?")) return;
    try { await api.delete(`/transportation/drivers/${id}`); onChange(); }
    catch { toast.error("Could not remove driver"); }
  };
  return (
    <Card className="border-caos-line p-6">
      <h2 className="font-display text-xl font-medium text-caos-forest mb-4">Drivers</h2>
      <div className="flex gap-2 mb-4">
        <Input placeholder="Driver name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="driver-name-input" />
        <label className="flex items-center gap-2 text-sm whitespace-nowrap">
          <Checkbox checked={form.is_flex} onCheckedChange={(v) => setForm({ ...form, is_flex: !!v })} /> Flex (not always available)
        </label>
        <Button onClick={add} className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-driver-btn"><Plus className="w-4 h-4" /></Button>
      </div>
      <Table>
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Flex</TableHead><TableHead>Enabled</TableHead><TableHead></TableHead></TableRow></TableHeader>
        <TableBody>
          {drivers.map((d) => (
            <TableRow key={d.driver_id} data-testid={`driver-row-${d.driver_id}`}>
              <TableCell>{d.name}</TableCell>
              <TableCell><Checkbox checked={d.is_flex} onCheckedChange={() => toggle(d, "is_flex")} /></TableCell>
              <TableCell><Checkbox checked={d.enabled} onCheckedChange={() => toggle(d, "enabled")} /></TableCell>
              <TableCell><Button variant="ghost" size="sm" onClick={() => remove(d.driver_id)}><Trash2 className="w-4 h-4 text-caos-terracotta" /></Button></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function VehicleSection({ vehicles, onChange }) {
  const [form, setForm] = useState({ name: "", capacity: "" });
  const add = async () => {
    if (!form.name.trim()) return;
    try {
      await api.post("/transportation/vehicles", { name: form.name, capacity: form.capacity === "" ? null : Number(form.capacity) });
      setForm({ name: "", capacity: "" });
      onChange();
    } catch { toast.error("Could not add vehicle"); }
  };
  const setCapacity = async (v, capacity) => {
    try { await api.patch(`/transportation/vehicles/${v.vehicle_id}`, { capacity: capacity === "" ? null : Number(capacity) }); onChange(); }
    catch { toast.error("Could not update vehicle"); }
  };
  const remove = async (id) => {
    if (!window.confirm("Remove this vehicle?")) return;
    try { await api.delete(`/transportation/vehicles/${id}`); onChange(); }
    catch { toast.error("Could not remove vehicle"); }
  };
  return (
    <Card className="border-caos-line p-6">
      <h2 className="font-display text-xl font-medium text-caos-forest mb-4">Vehicles</h2>
      <p className="text-caos-mute text-sm mb-3">Capacity left blank means "not configured yet" - the booking engine will not share a ride on that vehicle until you set a real number.</p>
      <div className="flex gap-2 mb-4">
        <Input placeholder="Vehicle name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} data-testid="vehicle-name-input" />
        <Input type="number" min="1" placeholder="Capacity (optional)" className="w-40" value={form.capacity} onChange={(e) => setForm({ ...form, capacity: e.target.value })} data-testid="vehicle-capacity-input" />
        <Button onClick={add} className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-vehicle-btn"><Plus className="w-4 h-4" /></Button>
      </div>
      <Table>
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Capacity</TableHead><TableHead></TableHead></TableRow></TableHeader>
        <TableBody>
          {vehicles.map((v) => (
            <TableRow key={v.vehicle_id} data-testid={`vehicle-row-${v.vehicle_id}`}>
              <TableCell>{v.name}</TableCell>
              <TableCell>
                <Input type="number" min="1" className="w-24" defaultValue={v.capacity ?? ""} placeholder="not set"
                  onBlur={(e) => setCapacity(v, e.target.value)} data-testid={`vehicle-capacity-${v.vehicle_id}`} />
              </TableCell>
              <TableCell><Button variant="ghost" size="sm" onClick={() => remove(v.vehicle_id)}><Trash2 className="w-4 h-4 text-caos-terracotta" /></Button></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function BufferSection({ config, onChange }) {
  const [minutes, setMinutes] = useState(config.buffer_minutes);
  const save = async () => {
    try { await api.put("/transportation/scheduling-config", { buffer_minutes: Number(minutes) }); toast.success("Saved"); onChange(); }
    catch { toast.error("Could not save"); }
  };
  return (
    <Card className="border-caos-line p-6">
      <h2 className="font-display text-xl font-medium text-caos-forest mb-2">Scheduling buffer</h2>
      <p className="text-caos-mute text-sm mb-3">Minimum gap CAOSCARE assumes between two runs on the same driver/vehicle - a scheduling policy, not a claim about how long any specific trip takes.</p>
      <div className="flex items-center gap-2">
        <Input type="number" min="0" className="w-32" value={minutes} onChange={(e) => setMinutes(e.target.value)} data-testid="buffer-minutes-input" />
        <span className="text-sm text-caos-mute">minutes</span>
        <Button onClick={save} variant="outline" className="border-2 rounded-full" data-testid="save-buffer-btn">Save</Button>
      </div>
    </Card>
  );
}

export default function TransportResourcesTab() {
  const [drivers, setDrivers] = useState([]);
  const [vehicles, setVehicles] = useState([]);
  const [config, setConfig] = useState({ buffer_minutes: 30 });

  const fetchAll = async () => {
    try {
      const [d, v, c] = await Promise.all([
        api.get("/transportation/drivers"),
        api.get("/transportation/vehicles"),
        api.get("/transportation/scheduling-config"),
      ]);
      setDrivers(d.data); setVehicles(v.data); setConfig(c.data);
    } catch { toast.error("Could not load transportation resources"); }
  };
  useEffect(() => { fetchAll(); }, []);

  return (
    <div className="space-y-6" data-testid="transport-resources-root">
      <DriverSection drivers={drivers} onChange={fetchAll} />
      <VehicleSection vehicles={vehicles} onChange={fetchAll} />
      <BufferSection config={config} onChange={fetchAll} />
    </div>
  );
}
