import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "../components/ui/table";
import { Radio, Trash2, Activity, CheckCircle2, XCircle, Loader2, Plus, Download } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

// Implements the [FW-006] "Listen and Learn" pairing flow from the blueprint.
// Admin clicks Add → modal opens → backend tells the kiosk SDR to listen →
// the next pendant press is captured → admin tags it → device is bound.

export default function RFPairingTab() {
  const [devices, setDevices] = useState([]);
  const [residents, setResidents] = useState([]);
  const [kiosks, setKiosks] = useState([]);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [testFor, setTestFor] = useState(null);

  const refresh = async () => {
    try {
      const [d, r, k, e] = await Promise.all([
        api.get("/rf/devices"),
        api.get("/residents"),
        api.get("/kiosks"),
        api.get("/rf/events?limit=20").catch(() => ({ data: [] })),
      ]);
      setDevices(d.data);
      setResidents(r.data);
      setKiosks(k.data);
      setEvents(e.data || []);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not load RF data");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); const t = setInterval(refresh, 6000); return () => clearInterval(t); }, []);

  const removeDevice = async (id) => {
    if (!window.confirm("Unpair this RF device? Future presses will no longer fire alerts.")) return;
    try {
      await api.delete(`/rf/devices/${id}`);
      toast.success("Unpaired");
      refresh();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to unpair");
    }
  };

  return (
    <div className="space-y-6" data-testid="rf-tab">
      <div className="flex items-end justify-between">
        <div>
          <h2 className="font-display text-3xl text-caos-forest">RF Pendants</h2>
          <p className="text-caos-mute text-sm mt-1">
            Sub-GHz buttons paired to residents. Vendor-agnostic — any 315/319/433/868/915 MHz pendant works.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link to="/admin/install" data-testid="rf-install-link">
            <Button variant="outline" className="rounded-full">
              <Download className="w-4 h-4 mr-2" /> Install bridge
            </Button>
          </Link>
          <Button
            onClick={() => setAddOpen(true)}
            data-testid="rf-add-pendant-btn"
            className="bg-caos-terracotta hover:bg-caos-terracotta-dark rounded-full"
          >
            <Plus className="w-4 h-4 mr-2" /> Add new pendant
          </Button>
        </div>
      </div>

      <Card className="p-0 overflow-hidden border-caos-line">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Label</TableHead>
              <TableHead>Resident</TableHead>
              <TableHead>Frequency</TableHead>
              <TableHead>Severity</TableHead>
              <TableHead>Last seen</TableHead>
              <TableHead>Presses</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading && (
              <TableRow><TableCell colSpan={7} className="text-center py-6 text-caos-mute">Loading…</TableCell></TableRow>
            )}
            {!loading && devices.length === 0 && (
              <TableRow><TableCell colSpan={7} className="text-center py-8 text-caos-mute italic">No paired pendants yet. Tap "Add new pendant" to begin.</TableCell></TableRow>
            )}
            {devices.map((d) => {
              const r = residents.find((x) => x.resident_id === d.resident_id);
              return (
                <TableRow key={d.rf_device_id} data-testid={`rf-device-row-${d.rf_device_id}`}>
                  <TableCell className="font-semibold">{d.label}</TableCell>
                  <TableCell>{r ? `${r.name} · Rm ${r.room}` : <span className="text-caos-mute italic">Unassigned</span>}</TableCell>
                  <TableCell className="font-mono text-xs">{(d.fingerprint?.frequency_hz / 1_000_000).toFixed(3)} MHz</TableCell>
                  <TableCell><SeverityBadge sev={d.severity} /></TableCell>
                  <TableCell className="text-xs text-caos-mute">{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : "—"}</TableCell>
                  <TableCell className="font-mono">{d.press_count || 0}</TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => setTestFor(d)}
                      data-testid={`rf-test-${d.rf_device_id}`}
                    >
                      <Activity className="w-3.5 h-3.5 mr-1" /> Test
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => removeDevice(d.rf_device_id)}
                      data-testid={`rf-delete-${d.rf_device_id}`}
                      className="text-caos-terracotta hover:text-white hover:bg-caos-terracotta border-caos-terracotta"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </Card>

      <Card className="p-5 border-caos-line">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-3">
          <Radio className="w-4 h-4 text-caos-forest" /> Recent RF events (live)
        </div>
        {events.length === 0 ? (
          <p className="text-caos-mute italic text-sm">Nothing on the air yet. Press a paired pendant — it'll appear here within 1 second.</p>
        ) : (
          <div className="space-y-1.5 max-h-80 overflow-y-auto">
            {events.map((e, i) => (
              <div
                key={`${e.received_at}-${i}`}
                data-testid={`rf-event-${i}`}
                className={`text-sm flex items-center gap-2 px-2 py-1.5 rounded ${e.matched_device_id ? "bg-caos-forest/5" : "bg-caos-amber/10"}`}
              >
                {e.matched_device_id ? <CheckCircle2 className="w-3.5 h-3.5 text-caos-forest" /> : <XCircle className="w-3.5 h-3.5 text-caos-amber" />}
                <span className="font-mono text-xs">{(e.fingerprint?.frequency_hz / 1_000_000).toFixed(3)} MHz</span>
                <span className="text-caos-mute text-xs">·</span>
                <span className="text-xs">{e.matched_device_id ? `matched (score ${e.match_score})` : "unmatched"}</span>
                <span className="text-caos-mute text-xs">·</span>
                <span className="text-xs text-caos-mute">{new Date(e.received_at).toLocaleTimeString()}</span>
                {e.alert_id && <Badge variant="outline" className="ml-auto text-[10px]">alert fired</Badge>}
              </div>
            ))}
          </div>
        )}
      </Card>

      <AddPendantDialog
        open={addOpen}
        onClose={() => { setAddOpen(false); refresh(); }}
        residents={residents}
        kiosks={kiosks}
      />
      <TestPendantDialog
        device={testFor}
        onClose={() => { setTestFor(null); refresh(); }}
      />
    </div>
  );
}

function SeverityBadge({ sev }) {
  const map = {
    emergency: "bg-caos-terracotta text-white",
    help:      "bg-caos-amber/30 text-caos-forest border border-caos-amber",
    assist:    "bg-caos-forest/15 text-caos-forest border border-caos-forest",
    comfort:   "bg-caos-mute/15 text-caos-ink",
  };
  return <Badge className={`uppercase text-[10px] tracking-widest ${map[sev] || ""}`}>{sev}</Badge>;
}

function AddPendantDialog({ open, onClose, residents, kiosks }) {
  const [step, setStep] = useState("idle");          // idle → listening → captured → saving
  const [capture, setCapture] = useState(null);
  const [kioskId, setKioskId] = useState("");
  const [label, setLabel] = useState("");
  const [residentId, setResidentId] = useState("");
  const [severity, setSeverity] = useState("help");

  useEffect(() => {
    if (!open) { setStep("idle"); setCapture(null); setLabel(""); setResidentId(""); setSeverity("help"); }
  }, [open]);

  useEffect(() => {
    if (step !== "listening" || !capture) return;
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/rf/listen/${capture.capture_id}`);
        setCapture(data);
        if (data.status === "captured") { setStep("captured"); clearInterval(t); }
        if (data.status === "timeout" || data.status === "cancelled") {
          toast.error("Didn't hear anything. Try again.");
          setStep("idle"); clearInterval(t);
        }
      } catch { /* keep polling */ }
    }, 800);
    return () => clearInterval(t);
  }, [step, capture]);

  const startListening = async () => {
    if (!kioskId) { toast.error("Pick a kiosk first."); return; }
    try {
      const { data } = await api.post("/rf/listen-start", { kiosk_id: kioskId, duration_seconds: 10 });
      setCapture(data);
      setStep("listening");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to start listen");
    }
  };

  const savePair = async () => {
    if (!label.trim()) { toast.error("Give the pendant a label."); return; }
    try {
      setStep("saving");
      await api.post("/rf/pair", {
        capture_id: capture.capture_id,
        label: label.trim(),
        resident_id: residentId || null,
        severity,
        match_threshold: 0.85,
      });
      toast.success(`Paired: ${label}`);
      onClose();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to pair");
      setStep("captured");
    }
  };

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent className="max-w-lg" data-testid="rf-add-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl text-caos-forest">Add a new pendant</DialogTitle>
        </DialogHeader>
        {step === "idle" && (
          <div className="space-y-4 py-2">
            <p className="text-caos-mute text-sm">Pick the kiosk that's nearest the pendant, then we'll listen for the button press.</p>
            <Select value={kioskId} onValueChange={setKioskId}>
              <SelectTrigger data-testid="rf-add-kiosk-select"><SelectValue placeholder="Choose a kiosk" /></SelectTrigger>
              <SelectContent>
                {kiosks.map((k) => <SelectItem key={k.kiosk_id} value={k.kiosk_id}>{k.name} · Rm {k.room}</SelectItem>)}
              </SelectContent>
            </Select>
            <DialogFooter>
              <Button onClick={startListening} data-testid="rf-add-listen-btn" className="bg-caos-forest rounded-full">
                <Radio className="w-4 h-4 mr-2" /> Start listening
              </Button>
            </DialogFooter>
          </div>
        )}
        {step === "listening" && (
          <div className="py-8 text-center space-y-3">
            <Loader2 className="w-10 h-10 animate-spin text-caos-forest mx-auto" />
            <p className="font-display text-2xl text-caos-forest">Press the pendant now</p>
            <p className="text-caos-mute text-sm">You have 10 seconds. We're listening on 315, 319, 433, 868, and 915 MHz.</p>
          </div>
        )}
        {step === "captured" && capture?.captured && (
          <div className="space-y-4 py-2" data-testid="rf-add-captured">
            <Card className="p-3 bg-caos-forest/5 border-caos-forest/30">
              <p className="text-xs uppercase tracking-widest text-caos-mute">Captured signal</p>
              <p className="font-mono text-lg text-caos-forest mt-1">{(capture.captured.frequency_hz / 1_000_000).toFixed(3)} MHz</p>
              <p className="font-mono text-xs text-caos-mute mt-1">Pattern: {capture.captured.bit_pattern_hex.slice(0, 64)}{capture.captured.bit_pattern_hex.length > 64 ? "…" : ""}</p>
              <p className="font-mono text-xs text-caos-mute">RSSI: {capture.captured.rssi ?? "—"} · {capture.captured.bit_length} bits · {capture.captured.modulation}</p>
            </Card>
            <Input
              placeholder="Label this pendant — e.g. Margaret's bedside"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              data-testid="rf-add-label-input"
            />
            <Select value={residentId || "_unassigned"} onValueChange={(v) => setResidentId(v === "_unassigned" ? "" : v)}>
              <SelectTrigger data-testid="rf-add-resident-select"><SelectValue placeholder="Bind to a resident (optional)" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="_unassigned">No resident — facility-wide</SelectItem>
                {residents.map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Rm {r.room}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={severity} onValueChange={setSeverity}>
              <SelectTrigger data-testid="rf-add-severity-select"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="help">help (default)</SelectItem>
                <SelectItem value="emergency">emergency</SelectItem>
                <SelectItem value="assist">assist</SelectItem>
                <SelectItem value="comfort">comfort</SelectItem>
              </SelectContent>
            </Select>
            <DialogFooter>
              <Button onClick={savePair} data-testid="rf-add-save-btn" className="bg-caos-forest rounded-full">
                Pair pendant
              </Button>
            </DialogFooter>
          </div>
        )}
        {step === "saving" && (
          <div className="py-10 text-center"><Loader2 className="w-8 h-8 animate-spin text-caos-forest mx-auto" /></div>
        )}
      </DialogContent>
    </Dialog>
  );
}

function TestPendantDialog({ device, onClose }) {
  const [capture, setCapture] = useState(null);
  const [step, setStep] = useState("idle");

  useEffect(() => {
    if (!device) { setCapture(null); setStep("idle"); return; }
    setStep("starting");
    (async () => {
      try {
        const { data } = await api.post(`/rf/test/${device.rf_device_id}`);
        setCapture(data);
        setStep("listening");
      } catch (err) {
        toast.error(err?.response?.data?.detail || "Could not start test");
        onClose();
      }
    })();
  }, [device]);                // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (step !== "listening" || !capture) return;
    const t = setInterval(async () => {
      try {
        const { data } = await api.get(`/rf/listen/${capture.capture_id}`);
        setCapture(data);
        if (data.status === "captured") { setStep("done"); clearInterval(t); }
        if (data.status === "timeout") { setStep("timeout"); clearInterval(t); }
      } catch { /* keep polling */ }
    }, 700);
    return () => clearInterval(t);
  }, [step, capture]);

  if (!device) return null;
  const score = step === "done" ? hamming(device.fingerprint.bit_pattern_hex, capture?.captured?.bit_pattern_hex) : null;
  const passed = score !== null && score >= (device.match_threshold || 0.85);

  return (
    <Dialog open={!!device} onOpenChange={(v) => { if (!v) onClose(); }}>
      <DialogContent data-testid="rf-test-dialog">
        <DialogHeader>
          <DialogTitle className="font-display text-2xl text-caos-forest">Test "{device.label}"</DialogTitle>
        </DialogHeader>
        {step === "starting" && <p className="text-caos-mute py-6 text-center">Opening capture window…</p>}
        {step === "listening" && (
          <div className="py-8 text-center space-y-3">
            <Loader2 className="w-10 h-10 animate-spin text-caos-forest mx-auto" />
            <p className="font-display text-2xl text-caos-forest">Press the pendant now</p>
            <p className="text-caos-mute text-sm">5-second window on {(device.fingerprint.frequency_hz / 1_000_000).toFixed(3)} MHz</p>
          </div>
        )}
        {step === "done" && (
          <div className="py-6 text-center space-y-3">
            {passed
              ? <CheckCircle2 className="w-14 h-14 text-caos-forest mx-auto" />
              : <XCircle className="w-14 h-14 text-caos-terracotta mx-auto" />}
            <p className="font-display text-2xl">
              {passed ? "Match — pendant works." : "No match — different signal heard."}
            </p>
            <p className="text-caos-mute text-sm font-mono">Similarity score: {(score * 100).toFixed(1)}%  ·  threshold: {(device.match_threshold * 100).toFixed(0)}%</p>
            <Button onClick={onClose} className="bg-caos-forest rounded-full mt-3">Close</Button>
          </div>
        )}
        {step === "timeout" && (
          <div className="py-6 text-center space-y-3">
            <XCircle className="w-12 h-12 text-caos-amber mx-auto" />
            <p className="font-display text-xl">Didn't hear anything.</p>
            <p className="text-caos-mute text-sm">Battery may be low, or the pendant is out of range.</p>
            <Button onClick={onClose} className="bg-caos-forest rounded-full mt-3">Close</Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

// Same Hamming similarity logic as the backend, for instant client-side feedback
function hamming(a, b) {
  if (!a || !b) return 0;
  const ba = hexToBytes(a), bb = hexToBytes(b);
  const n = Math.min(ba.length, bb.length);
  if (!n) return 0;
  let diff = 0;
  for (let i = 0; i < n; i++) {
    let x = ba[i] ^ bb[i];
    while (x) { diff += x & 1; x >>= 1; }
  }
  return 1 - diff / (n * 8);
}
function hexToBytes(hex) {
  const clean = (hex || "").replace(/\s+/g, "");
  const out = new Uint8Array(Math.floor(clean.length / 2));
  for (let i = 0; i < out.length; i++) out[i] = parseInt(clean.substr(i * 2, 2), 16) || 0;
  return out;
}
