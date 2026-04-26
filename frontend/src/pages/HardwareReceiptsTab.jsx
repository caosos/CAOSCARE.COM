import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import {
  Cpu, CheckCircle2, XCircle, AlertTriangle, Plus, Loader2, Award, Trash2, RefreshCw,
} from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "../lib/auth";

// Implements [INF-004] Hardware Receipts tab — admin manages every device,
// runs probes, sees pass/fail receipts, assigns deployment roles (gated).

const CLASS_LABEL = {
  kiosk_tablet: "Kiosk Tablet",
  caos_hub: "CAOS Hub",
  speaker_node: "Speaker Node",
  linux_bridge: "Linux Bridge",
  wearable_gateway: "Wearable Gateway",
  wall_terminal: "Wall Terminal",
};

const CAPABILITY_LABEL = {
  far_field_mic: "Far-field mic",
  speaker_quality: "Speaker quality",
  wifi_ac: "Wi-Fi AC+",
  persistent_power: "AC power",
  haptic_feedback: "Haptic",
  usb_host: "USB host",
  bluetooth_le: "Bluetooth LE",
  mesh_radio_subghz: "Sub-GHz radio",
  camera: "Camera",
  battery_min_hours: "Battery (≥4h)",
  touchscreen: "Touchscreen",
  display_resolution_min: "Display ≥720p",
};

export default function HardwareReceiptsTab() {
  const { user } = useAuth();
  const [devices, setDevices] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [roles, setRoles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [probeFor, setProbeFor] = useState(null);
  const [assignFor, setAssignFor] = useState(null);

  const refresh = async () => {
    try {
      const [d, p, r] = await Promise.all([
        api.get("/hardware/devices"),
        api.get("/hardware/profiles"),
        api.get("/hardware/roles"),
      ]);
      setDevices(d.data); setProfiles(p.data); setRoles(r.data);
    } catch (err) { toast.error(err?.response?.data?.detail || "Load failed"); }
    finally { setLoading(false); }
  };
  useEffect(() => { refresh(); }, []);

  const removeDevice = async (id) => {
    if (!window.confirm("Remove this device permanently?")) return;
    await api.delete(`/hardware/devices/${id}`).catch((e) => toast.error(e?.response?.data?.detail || "Delete failed"));
    refresh();
  };

  return (
    <div className="space-y-6" data-testid="hardware-tab">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h2 className="font-display text-3xl text-caos-forest">Hardware Receipts</h2>
          <p className="text-caos-mute text-sm mt-1 max-w-2xl">
            Capability-probe doctrine — every device must produce a passing receipt before a role
            can be assigned. No marketplace claim counts. Only a probe counts.
          </p>
        </div>
        <Button onClick={() => setAddOpen(true)} data-testid="hw-add-device-btn" className="bg-caos-terracotta hover:bg-caos-terracotta-dark rounded-full">
          <Plus className="w-4 h-4 mr-2" /> Register device
        </Button>
      </header>

      <Card className="p-0 overflow-hidden border-caos-line">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Device</TableHead>
              <TableHead>Class</TableHead>
              <TableHead>Receipt</TableHead>
              <TableHead>Role</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && <TableRow><TableCell colSpan={5} className="py-6 text-center text-caos-mute">Loading…</TableCell></TableRow>}
            {!loading && devices.length === 0 && (
              <TableRow><TableCell colSpan={5} className="py-8 text-center text-caos-mute italic">
                No hardware registered. Tap "Register device" to start.
              </TableCell></TableRow>
            )}
            {devices.map((d) => (
              <TableRow key={d.hw_id} data-testid={`hw-row-${d.hw_id}`}>
                <TableCell>
                  <p className="font-semibold">{d.model_name || d.serial || d.hw_id}</p>
                  <p className="text-[10px] text-caos-mute font-mono">{d.hw_id}{d.serial ? ` · ${d.serial}` : ""}</p>
                </TableCell>
                <TableCell><Badge variant="outline">{CLASS_LABEL[d.device_class] || d.device_class}</Badge></TableCell>
                <TableCell><ReceiptStatus status={d.last_receipt_status} /></TableCell>
                <TableCell>
                  {d.deployment_role ? (
                    <span className="text-sm font-semibold text-caos-forest">{d.deployment_role}{d.deployment_room ? ` · ${d.deployment_room}` : ""}</span>
                  ) : (
                    <span className="text-caos-mute italic text-sm">Unassigned</span>
                  )}
                </TableCell>
                <TableCell className="text-right space-x-1">
                  <Button size="sm" variant="outline" onClick={() => setProbeFor(d)} data-testid={`hw-probe-${d.hw_id}`}>
                    <RefreshCw className="w-3.5 h-3.5 mr-1" /> Probe
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => setAssignFor(d)} data-testid={`hw-assign-${d.hw_id}`}>
                    <Award className="w-3.5 h-3.5 mr-1" /> Role
                  </Button>
                  {user?.role === "owner" && (
                    <Button size="sm" variant="outline" onClick={() => removeDevice(d.hw_id)} data-testid={`hw-delete-${d.hw_id}`}
                      className="text-caos-terracotta hover:text-white hover:bg-caos-terracotta border-caos-terracotta">
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Card>

      <RegisterDialog open={addOpen} onClose={() => { setAddOpen(false); refresh(); }} />
      <ProbeDialog
        device={probeFor}
        profiles={profiles}
        onClose={() => { setProbeFor(null); refresh(); }}
      />
      <AssignRoleDialog
        device={assignFor}
        roles={roles}
        onClose={() => { setAssignFor(null); refresh(); }}
      />
    </div>
  );
}

function ReceiptStatus({ status }) {
  const map = {
    pass:    { icon: <CheckCircle2 className="w-3.5 h-3.5" />, label: "PASS",     color: "bg-caos-forest/15 text-caos-forest border-caos-forest" },
    fail:    { icon: <XCircle className="w-3.5 h-3.5" />,      label: "FAIL",     color: "bg-caos-terracotta/15 text-caos-terracotta border-caos-terracotta" },
    expired: { icon: <AlertTriangle className="w-3.5 h-3.5" />,label: "EXPIRED",  color: "bg-caos-amber/15 text-caos-forest border-caos-amber" },
    none:    { icon: null,                                     label: "NEVER PROBED", color: "bg-caos-mute/15 text-caos-ink border-caos-mute/40" },
  };
  const m = map[status] || map.none;
  return <Badge variant="outline" className={`uppercase tracking-widest text-[10px] inline-flex items-center gap-1 ${m.color}`}>{m.icon}{m.label}</Badge>;
}

function RegisterDialog({ open, onClose }) {
  const [deviceClass, setDeviceClass] = useState("kiosk_tablet");
  const [modelName, setModelName] = useState("");
  const [serial, setSerial] = useState("");
  const [room, setRoom] = useState("");
  const submit = async () => {
    try {
      await api.post("/hardware/devices", {
        device_class: deviceClass,
        model_name: modelName.trim() || null,
        serial: serial.trim() || null,
        deployment_room: room.trim() || null,
      });
      toast.success("Device registered");
      onClose();
    } catch (err) { toast.error(err?.response?.data?.detail || "Register failed"); }
  };
  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent data-testid="hw-add-dialog">
        <DialogHeader><DialogTitle className="font-display text-2xl text-caos-forest">Register a device</DialogTitle></DialogHeader>
        <div className="space-y-3 py-2">
          <div>
            <p className="text-xs uppercase tracking-widest text-caos-mute mb-1">Device class</p>
            <Select value={deviceClass} onValueChange={setDeviceClass}>
              <SelectTrigger data-testid="hw-add-class"><SelectValue /></SelectTrigger>
              <SelectContent>
                {Object.entries(CLASS_LABEL).map(([k, v]) => <SelectItem key={k} value={k}>{v}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <Input placeholder="Model name (optional, e.g. Lenovo Tab M10)" value={modelName} onChange={(e) => setModelName(e.target.value)} data-testid="hw-add-model" />
          <Input placeholder="Serial / asset tag (optional)" value={serial} onChange={(e) => setSerial(e.target.value)} data-testid="hw-add-serial" />
          <Input placeholder="Intended room (optional)" value={room} onChange={(e) => setRoom(e.target.value)} data-testid="hw-add-room" />
        </div>
        <DialogFooter>
          <Button onClick={submit} className="bg-caos-forest rounded-full" data-testid="hw-add-submit">Register</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ProbeDialog({ device, profiles, onClose }) {
  const profile = device ? profiles.find((p) => p.device_class === device.device_class) : null;
  const allCaps = profile ? [...profile.required.map((c) => ({ key: c, required: true })), ...profile.optional.map((c) => ({ key: c, required: false }))] : [];
  const [results, setResults] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!device) { setResults({}); return; }
    const init = {};
    for (const c of allCaps) init[c.key] = "not_tested";
    setResults(init);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device]);

  const submit = async () => {
    setBusy(true);
    try {
      const probes = Object.entries(results).map(([capability, result]) => ({ capability, result }));
      const { data } = await api.post("/hardware/probe", { hw_id: device.hw_id, probes });
      toast.success(data.overall === "pass" ? "Receipt issued: PASS ✓" : "Receipt issued: FAIL — see details");
      onClose();
    } catch (err) { toast.error(err?.response?.data?.detail || "Probe failed"); }
    finally { setBusy(false); }
  };

  if (!device) return null;
  return (
    <Dialog open={!!device} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent data-testid="hw-probe-dialog" className="max-w-lg">
        <DialogHeader><DialogTitle className="font-display text-2xl text-caos-forest">Compatibility Probe — {device.model_name || device.hw_id}</DialogTitle></DialogHeader>
        <p className="text-caos-mute text-sm">
          Mark each capability as <b>pass</b> or <b>fail</b> based on what you can actually verify on the device.
          In production this is run by the Companion APK automatically.
        </p>
        <div className="space-y-1.5 py-2 max-h-80 overflow-y-auto">
          {allCaps.map(({ key, required }) => (
            <div key={key} className="flex items-center justify-between gap-3 px-2 py-1.5 rounded bg-caos-ambient/40">
              <div className="flex-1">
                <p className="text-sm font-semibold text-caos-forest">{CAPABILITY_LABEL[key] || key}</p>
                <p className="text-[10px] uppercase tracking-widest text-caos-mute">{required ? "Required" : "Optional"}</p>
              </div>
              <Select value={results[key] || "not_tested"} onValueChange={(v) => setResults((r) => ({ ...r, [key]: v }))}>
                <SelectTrigger className="w-[130px]" data-testid={`probe-${key}`}><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="pass">Pass ✓</SelectItem>
                  <SelectItem value="fail">Fail ✗</SelectItem>
                  <SelectItem value="not_tested">Not tested</SelectItem>
                </SelectContent>
              </Select>
            </div>
          ))}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={busy} className="bg-caos-forest rounded-full" data-testid="hw-probe-submit">
            {busy ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Cpu className="w-4 h-4 mr-2" />}
            Issue receipt
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function AssignRoleDialog({ device, roles, onClose }) {
  const [role, setRole] = useState("");
  const [room, setRoom] = useState("");
  useEffect(() => {
    if (!device) return;
    setRole(device.deployment_role || "");
    setRoom(device.deployment_room || "");
  }, [device]);
  const submit = async () => {
    try {
      const { data } = await api.post("/hardware/assign-role", {
        hw_id: device.hw_id, deployment_role: role, deployment_room: room.trim() || null,
      });
      toast.success(`Role assigned: ${role} (stack: ${data.blueprint_stack.length} services)`);
      onClose();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Assign failed");
    }
  };
  if (!device) return null;
  return (
    <Dialog open={!!device} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent data-testid="hw-assign-dialog">
        <DialogHeader><DialogTitle className="font-display text-2xl text-caos-forest">Assign deployment role</DialogTitle></DialogHeader>
        <p className="text-caos-mute text-sm">
          Roles are gated. If the device's receipt doesn't satisfy the role's required capabilities,
          assignment will be refused — that's the point.
        </p>
        <div className="space-y-3 py-2">
          <Select value={role} onValueChange={setRole}>
            <SelectTrigger data-testid="hw-assign-role"><SelectValue placeholder="Pick a role" /></SelectTrigger>
            <SelectContent>
              {roles.map((r) => (
                <SelectItem key={r.role} value={r.role}>
                  {r.role} <span className="text-caos-mute"> · {r.required_capabilities.length} required caps</span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input placeholder="Room (optional)" value={room} onChange={(e) => setRoom(e.target.value)} data-testid="hw-assign-room" />
          {role && (
            <Card className="p-3 bg-caos-forest/5 border-caos-forest/20">
              <p className="text-xs uppercase tracking-widest text-caos-mute mb-1">If assigned, this device runs:</p>
              <div className="flex flex-wrap gap-1">
                {(roles.find((r) => r.role === role)?.blueprint_stack || []).map((s) => (
                  <Badge key={s} variant="outline" className="text-[10px]">{s}</Badge>
                ))}
              </div>
            </Card>
          )}
        </div>
        <DialogFooter>
          <Button onClick={submit} disabled={!role} className="bg-caos-forest rounded-full" data-testid="hw-assign-submit">Assign</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
