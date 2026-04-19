import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card } from "../components/ui/card";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Trash2, Plus, LogOut, Activity } from "lucide-react";
import { toast } from "sonner";
import PendantsTab from "./PendantsTab";
import Roadmap from "./Roadmap";
import Insights from "./Insights";
import FamilyTab from "./FamilyTab";
import MovementDialog from "./MovementDialog";
import WearablesTab from "./WearablesTab";
import DeviceTokensTab from "./DeviceTokensTab";
import DevicesTab from "./DevicesTab";
import TasksTab from "./TasksTab";
import MedicationsTab from "./MedicationsTab";
import FloorPlanTab from "./FloorPlanTab";
import MemoryDialog from "./MemoryDialog";

export default function Admin() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  const [residents, setResidents] = useState([]);
  const [staff, setStaff] = useState([]);
  const [kiosks, setKiosks] = useState([]);
  const [zones, setZones] = useState([]);

  const fetchAll = async () => {
    try {
      const [r, s, k, z] = await Promise.all([
        api.get("/residents"),
        api.get("/staff"),
        api.get("/kiosks"),
        api.get("/zones"),
      ]);
      setResidents(r.data);
      setStaff(s.data);
      setKiosks(k.data);
      setZones(z.data);
    } catch (e) {
      if (e?.response?.status === 403) {
        toast.error("Admin access required");
        nav("/staff");
      }
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  return (
    <div className="min-h-screen bg-caos-bone">
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-7xl mx-auto flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6">
            <Link to="/" className="text-xl" data-testid="admin-home-link">
              <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
              <span className="font-display font-light text-caos-forest">Care</span>
            </Link>
            <span className="text-caos-mute text-sm">· Admin</span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/staff" data-testid="admin-staff-link">
              <Button variant="outline" className="border-2 h-10 rounded-full">
                <Activity className="w-4 h-4 mr-2" /> Dashboard
              </Button>
            </Link>
            <span className="text-sm text-caos-mute hidden md:block">{user?.name}</span>
            <Button
              variant="outline"
              onClick={async () => { await logout(); nav("/login"); }}
              className="border-2 h-10 rounded-full"
              data-testid="admin-logout-btn"
            >
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-6 py-8">
        <h1 className="font-display text-4xl font-light text-caos-forest mb-6">Community administration</h1>
        <Tabs defaultValue="residents">
          <TabsList className="flex-wrap h-auto">
            <TabsTrigger value="residents" data-testid="tab-residents">Residents ({residents.length})</TabsTrigger>
            <TabsTrigger value="pendants" data-testid="tab-pendants">Pendants</TabsTrigger>
            <TabsTrigger value="wearables" data-testid="tab-wearables">Wearables</TabsTrigger>
            <TabsTrigger value="devices" data-testid="tab-devices">Smart devices</TabsTrigger>
            <TabsTrigger value="tasks" data-testid="tab-tasks">Tasks</TabsTrigger>
            <TabsTrigger value="meds" data-testid="tab-meds">Meds</TabsTrigger>
            <TabsTrigger value="map" data-testid="tab-map">Map</TabsTrigger>
            <TabsTrigger value="staff" data-testid="tab-staff">Staff ({staff.length})</TabsTrigger>
            <TabsTrigger value="kiosks" data-testid="tab-kiosks">Kiosks ({kiosks.length})</TabsTrigger>
            <TabsTrigger value="zones" data-testid="tab-zones">Zones ({zones.length})</TabsTrigger>
            <TabsTrigger value="family" data-testid="tab-family">Family</TabsTrigger>
            <TabsTrigger value="tokens" data-testid="tab-tokens">Device tokens</TabsTrigger>
            <TabsTrigger value="insights" data-testid="tab-insights">Insights</TabsTrigger>
            <TabsTrigger value="roadmap" data-testid="tab-roadmap">Roadmap</TabsTrigger>
          </TabsList>

          <TabsContent value="residents" className="mt-6">
            <ResidentsTab residents={residents} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="pendants" className="mt-6">
            <PendantsTab residents={residents} />
          </TabsContent>
          <TabsContent value="wearables" className="mt-6">
            <WearablesTab residents={residents} />
          </TabsContent>
          <TabsContent value="devices" className="mt-6">
            <DevicesTab residents={residents} />
          </TabsContent>
          <TabsContent value="tasks" className="mt-6">
            <TasksTab residents={residents} staff={staff} />
          </TabsContent>
          <TabsContent value="meds" className="mt-6">
            <MedicationsTab residents={residents} />
          </TabsContent>
          <TabsContent value="map" className="mt-6">
            <FloorPlanTab />
          </TabsContent>
          <TabsContent value="staff" className="mt-6">
            <StaffTab staff={staff} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="kiosks" className="mt-6">
            <KiosksTab kiosks={kiosks} zones={zones} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="zones" className="mt-6">
            <ZonesTab zones={zones} onChange={fetchAll} />
          </TabsContent>
          <TabsContent value="family" className="mt-6">
            <FamilyTab residents={residents} />
          </TabsContent>
          <TabsContent value="tokens" className="mt-6">
            <DeviceTokensTab />
          </TabsContent>
          <TabsContent value="insights" className="mt-6">
            <Insights />
          </TabsContent>
          <TabsContent value="roadmap" className="mt-6">
            <Roadmap />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

/* -------------- Residents -------------- */
function ResidentsTab({ residents, onChange }) {
  const [open, setOpen] = useState(false);
  const emptyForm = { name: "", preferred_name: "", room: "", pendant_id: "", medical_notes: "", emergency_contact: "", preferences: "", memory: "", participation_level: "pendant_enhanced" };
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [movementFor, setMovementFor] = useState(null);
  const [memoryFor, setMemoryFor] = useState(null);

  const open_new = () => { setEditingId(null); setForm(emptyForm); setOpen(true); };
  const open_edit = (r) => {
    setEditingId(r.resident_id);
    setForm({
      name: r.name || "",
      preferred_name: r.preferred_name || "",
      room: r.room || "",
      pendant_id: r.pendant_id || "",
      medical_notes: r.medical_notes || "",
      emergency_contact: r.emergency_contact || "",
      preferences: r.preferences || "",
      memory: r.memory || "",
      participation_level: r.participation_level || "pendant_enhanced",
    });
    setOpen(true);
  };

  const save = async (e) => {
    e.preventDefault();
    try {
      if (editingId) {
        await api.put(`/residents/${editingId}`, form);
        toast.success("Updated");
      } else {
        await api.post("/residents", form);
        toast.success("Resident added");
      }
      setOpen(false);
      setForm(emptyForm);
      setEditingId(null);
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this resident?")) return;
    await api.delete(`/residents/${id}`);
    toast.success("Deleted");
    onChange();
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Residents</h2>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button onClick={open_new} className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-resident-btn">
              <Plus className="w-4 h-4 mr-2" /> Add resident
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
            <DialogHeader><DialogTitle className="font-display">{editingId ? "Edit resident" : "New resident"}</DialogTitle></DialogHeader>
            <form onSubmit={save} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Full name</Label><Input required data-testid="res-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
                <div><Label>Preferred name (used by AI)</Label><Input data-testid="res-preferred" value={form.preferred_name} onChange={(e) => setForm({ ...form, preferred_name: e.target.value })} placeholder="Maggie" /></div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Room</Label><Input required data-testid="res-room" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} /></div>
                <div><Label>Pendant ID</Label><Input required data-testid="res-pendant" value={form.pendant_id} onChange={(e) => setForm({ ...form, pendant_id: e.target.value })} /></div>
              </div>
              <div>
                <Label>Participation level</Label>
                <Select value={form.participation_level} onValueChange={(v) => setForm({ ...form, participation_level: v })}>
                  <SelectTrigger data-testid="res-participation"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="room_only">Room only</SelectItem>
                    <SelectItem value="pendant_enhanced">Pendant enhanced</SelectItem>
                    <SelectItem value="wearable_enhanced">Wearable enhanced</SelectItem>
                    <SelectItem value="family_connected">Family connected</SelectItem>
                    <SelectItem value="full">Full (all layers)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div><Label>Emergency contact</Label><Input data-testid="res-contact" value={form.emergency_contact} onChange={(e) => setForm({ ...form, emergency_contact: e.target.value })} /></div>
              <div><Label>Medical notes</Label><Textarea data-testid="res-notes" value={form.medical_notes} onChange={(e) => setForm({ ...form, medical_notes: e.target.value })} /></div>
              <div>
                <Label>Comfort topics they love <span className="text-caos-mute text-xs">(AI personalizes chat)</span></Label>
                <Textarea data-testid="res-preferences" value={form.preferences} onChange={(e) => setForm({ ...form, preferences: e.target.value })} placeholder="Piano hymns, her grandkids Liam & Aoife, rainy days…" />
              </div>
              <div>
                <Label>Things CAOS should remember <span className="text-caos-mute text-xs">(AI memory)</span></Label>
                <Textarea data-testid="res-memory" value={form.memory} onChange={(e) => setForm({ ...form, memory: e.target.value })} placeholder="Her late husband Frank passed in 2019. She was a schoolteacher in Boston." />
              </div>
              <DialogFooter><Button type="submit" data-testid="res-save" className="bg-caos-forest">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead><TableHead>Room</TableHead><TableHead>Pendant</TableHead><TableHead>Participation</TableHead><TableHead>AI personalization</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {residents.map((r) => (
            <TableRow key={r.resident_id} data-testid={`res-row-${r.resident_id}`}>
              <TableCell>
                <span className="font-medium">{r.name}</span>
                {r.preferred_name && <span className="text-caos-mute text-xs block">"{r.preferred_name}"</span>}
              </TableCell>
              <TableCell>{r.room}</TableCell>
              <TableCell className="font-mono text-xs">{r.pendant_id}</TableCell>
              <TableCell className="text-xs uppercase tracking-wider font-bold text-caos-forest">{r.participation_level?.replace("_", " ") || "—"}</TableCell>
              <TableCell className="text-caos-mute text-sm max-w-xs truncate" title={r.preferences}>
                {r.preferences ? `✓ ${r.preferences.slice(0, 60)}${r.preferences.length > 60 ? "…" : ""}` : <span className="text-caos-mute/50">—</span>}
              </TableCell>
              <TableCell>
                <div className="flex gap-1">
                  <Button variant="ghost" size="sm" onClick={() => setMemoryFor(r)} data-testid={`mem-res-${r.resident_id}`}>Memory</Button>
                  <Button variant="ghost" size="sm" onClick={() => setMovementFor(r)} data-testid={`move-res-${r.resident_id}`}>Movement</Button>
                  <Button variant="ghost" size="sm" onClick={() => open_edit(r)} data-testid={`edit-res-${r.resident_id}`}>Edit</Button>
                  <Button variant="ghost" size="sm" onClick={() => remove(r.resident_id)} data-testid={`del-res-${r.resident_id}`}>
                    <Trash2 className="w-4 h-4 text-caos-terracotta" />
                  </Button>
                </div>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <MovementDialog resident={movementFor} open={!!movementFor} onOpenChange={(o) => { if (!o) setMovementFor(null); }} />
      <MemoryDialog resident={memoryFor} open={!!memoryFor} onOpenChange={(o) => { if (!o) setMemoryFor(null); }} />
    </Card>
  );
}

/* -------------- Staff -------------- */
function StaffTab({ staff, onChange }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "staff" });

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/staff", form);
      toast.success("Staff added");
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "staff" });
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this staff member?")) return;
    try {
      await api.delete(`/staff/${id}`);
      toast.success("Deleted");
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Staff accounts</h2>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-staff-btn">
              <Plus className="w-4 h-4 mr-2" /> Add staff
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-display">New staff</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div><Label>Name</Label><Input required data-testid="staff-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div><Label>Email</Label><Input required type="email" data-testid="staff-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
              <div><Label>Password</Label><Input required type="password" minLength={6} data-testid="staff-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
              <div>
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="staff-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="staff">Staff</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="staff-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Table>
        <TableHeader>
          <TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead><TableHead>Provider</TableHead><TableHead></TableHead></TableRow>
        </TableHeader>
        <TableBody>
          {staff.map((s) => (
            <TableRow key={s.user_id} data-testid={`staff-row-${s.user_id}`}>
              <TableCell className="font-medium">{s.name}</TableCell>
              <TableCell>{s.email}</TableCell>
              <TableCell><span className="uppercase text-xs font-bold tracking-wider">{s.role}</span></TableCell>
              <TableCell className="text-caos-mute">{s.auth_provider}</TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(s.user_id)} data-testid={`del-staff-${s.user_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

/* -------------- Kiosks -------------- */
function KiosksTab({ kiosks, zones, onChange }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", room: "", zone: "", mac_address: "", is_central: false });

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/kiosks", form);
      toast.success("Kiosk added");
      setOpen(false);
      setForm({ name: "", room: "", zone: "", mac_address: "", is_central: false });
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this kiosk?")) return;
    await api.delete(`/kiosks/${id}`);
    toast.success("Deleted");
    onChange();
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Wall kiosks</h2>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-kiosk-btn">
              <Plus className="w-4 h-4 mr-2" /> Add kiosk
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-display">New kiosk</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div><Label>Display name</Label><Input required data-testid="kiosk-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Room</Label><Input required data-testid="kiosk-room" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} /></div>
                <div>
                  <Label>Zone</Label>
                  <Select value={form.zone} onValueChange={(v) => setForm({ ...form, zone: v })}>
                    <SelectTrigger data-testid="kiosk-zone"><SelectValue placeholder="Select zone" /></SelectTrigger>
                    <SelectContent>
                      {zones.map((z) => <SelectItem key={z.zone_id} value={z.name}>{z.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>MAC address (optional)</Label><Input data-testid="kiosk-mac" value={form.mac_address} onChange={(e) => setForm({ ...form, mac_address: e.target.value })} /></div>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="kiosk-central-toggle">
                <Checkbox checked={form.is_central} onCheckedChange={(v) => setForm({ ...form, is_central: !!v })} />
                <span className="text-sm font-semibold text-caos-forest">Central nurse station <span className="text-caos-mute font-normal">(listens for any facility emergency)</span></span>
              </label>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="kiosk-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Table>
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Room</TableHead><TableHead>Zone</TableHead><TableHead>MAC</TableHead><TableHead>Kiosk link</TableHead><TableHead></TableHead></TableRow></TableHeader>
        <TableBody>
          {kiosks.map((k) => (
            <TableRow key={k.kiosk_id} data-testid={`kiosk-row-${k.kiosk_id}`}>
              <TableCell className="font-medium">
                {k.name}
                {k.is_central && <Badge className="ml-2 bg-caos-terracotta text-white uppercase text-[10px] tracking-wider">Central</Badge>}
              </TableCell>
              <TableCell>{k.room}</TableCell>
              <TableCell>{k.zone}</TableCell>
              <TableCell className="font-mono text-xs">{k.mac_address || "—"}</TableCell>
              <TableCell>
                <Link to={`/kiosk/${k.kiosk_id}`} className="text-caos-forest underline text-sm" data-testid={`kiosk-open-${k.kiosk_id}`}>Open →</Link>
              </TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(k.kiosk_id)} data-testid={`del-kiosk-${k.kiosk_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

/* -------------- Zones -------------- */
function ZonesTab({ zones, onChange }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", floor: "", description: "", is_restricted: false });

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/zones", form);
      toast.success("Zone added");
      setOpen(false);
      setForm({ name: "", floor: "", description: "", is_restricted: false });
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this zone?")) return;
    await api.delete(`/zones/${id}`);
    toast.success("Deleted");
    onChange();
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Geo zones</h2>
          <p className="text-caos-mute text-sm mt-1">Mark a zone as <b>Restricted</b> to fire a wander/elopement alert if a resident enters it.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-zone-btn">
              <Plus className="w-4 h-4 mr-2" /> Add zone
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-display">New zone</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div><Label>Name</Label><Input required data-testid="zone-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div><Label>Floor</Label><Input data-testid="zone-floor" value={form.floor} onChange={(e) => setForm({ ...form, floor: e.target.value })} /></div>
              <div><Label>Description</Label><Textarea data-testid="zone-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="zone-restricted-toggle">
                <Checkbox checked={form.is_restricted} onCheckedChange={(v) => setForm({ ...form, is_restricted: !!v })} />
                <span className="text-sm font-semibold text-caos-forest">Restricted zone (fires wander alert on entry)</span>
              </label>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="zone-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Table>
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Floor</TableHead><TableHead>Description</TableHead><TableHead>Access</TableHead><TableHead></TableHead></TableRow></TableHeader>
        <TableBody>
          {zones.map((z) => (
            <TableRow key={z.zone_id} data-testid={`zone-row-${z.zone_id}`}>
              <TableCell className="font-medium">{z.name}</TableCell>
              <TableCell>{z.floor}</TableCell>
              <TableCell className="text-caos-mute text-sm">{z.description}</TableCell>
              <TableCell>
                {z.is_restricted
                  ? <Badge className="bg-caos-terracotta text-white uppercase tracking-wider text-xs font-bold">Restricted</Badge>
                  : <Badge variant="outline" className="uppercase tracking-wider text-xs">Open</Badge>}
              </TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(z.zone_id)} data-testid={`del-zone-${z.zone_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
