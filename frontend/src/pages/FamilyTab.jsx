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
import { Trash2, Plus, Mail, Smartphone, Send, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";

const NOTIFY_OPTIONS = [
  { key: "emergency", label: "Emergency" },
  { key: "assist", label: "Assist calls" },
  { key: "wander", label: "Wander / geofence" },
  { key: "daily_summary", label: "Daily summary" },
];

export default function FamilyTab({ residents }) {
  const [contacts, setContacts] = useState([]);
  const [status, setStatus] = useState(null);
  const [notifs, setNotifs] = useState([]);
  const [open, setOpen] = useState(false);
  const [testOpen, setTestOpen] = useState(false);
  const [form, setForm] = useState({ resident_id: "", name: "", relationship: "", email: "", phone: "", notify_on: ["emergency", "wander"] });
  const [test, setTest] = useState({ channel: "sms", to: "", body: "CAOS Care test notification." });

  const fetchAll = async () => {
    try {
      const [cRes, sRes, nRes] = await Promise.all([
        api.get("/family-contacts"),
        api.get("/notifications/status"),
        api.get("/notifications?limit=20"),
      ]);
      setContacts(cRes.data);
      setStatus(sRes.data);
      setNotifs(nRes.data);
    } catch {}
  };
  useEffect(() => { fetchAll(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!form.resident_id) { toast.error("Select a resident"); return; }
    try {
      await api.post("/family-contacts", form);
      toast.success("Family contact added");
      setOpen(false);
      setForm({ resident_id: "", name: "", relationship: "", email: "", phone: "", notify_on: ["emergency", "wander"] });
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Remove this contact?")) return;
    await api.delete(`/family-contacts/${id}`);
    toast.success("Removed");
    fetchAll();
  };

  const sendTest = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/notifications/test", test);
      toast.success(data.status === "sent" ? "Sent via provider" : "Logged (provider not configured)");
      setTestOpen(false);
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const toggleNotifyOn = (key) => {
    const has = form.notify_on.includes(key);
    setForm({ ...form, notify_on: has ? form.notify_on.filter((k) => k !== key) : [...form.notify_on, key] });
  };

  return (
    <div className="space-y-6" data-testid="family-panel">
      {/* Provider status */}
      <Card className="border-caos-line p-5">
        <h3 className="font-display text-lg font-medium text-caos-forest mb-3">Provider status</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <ProviderBadge label="Twilio SMS" ok={status?.twilio_configured} hint="Set TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_FROM_NUMBER in backend/.env" />
          <ProviderBadge label="Resend email" ok={status?.resend_configured} hint="Set RESEND_API_KEY (and optionally RESEND_FROM_EMAIL) in backend/.env" />
        </div>
        <p className="text-caos-mute text-sm mt-3">
          Both channels are wired. Until the keys are configured, outbound messages are recorded to the
          notifications log but not sent. Drop the keys in and they activate automatically — no code changes.
        </p>
      </Card>

      {/* Family contacts */}
      <Card className="border-caos-line p-5">
        <div className="flex justify-between items-center mb-4 flex-wrap gap-2">
          <h3 className="font-display text-lg font-medium text-caos-forest">Family contacts</h3>
          <div className="flex gap-2">
            <Dialog open={testOpen} onOpenChange={setTestOpen}>
              <DialogTrigger asChild>
                <Button variant="outline" className="border-2 rounded-full" data-testid="send-test-btn">
                  <Send className="w-4 h-4 mr-2" /> Send test
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle className="font-display">Send test notification</DialogTitle></DialogHeader>
                <form onSubmit={sendTest} className="space-y-3">
                  <div>
                    <Label>Channel</Label>
                    <Select value={test.channel} onValueChange={(v) => setTest({ ...test, channel: v })}>
                      <SelectTrigger data-testid="test-channel"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="sms">SMS (Twilio)</SelectItem>
                        <SelectItem value="email">Email (Resend)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <Label>To</Label>
                    <Input required value={test.to} onChange={(e) => setTest({ ...test, to: e.target.value })} placeholder={test.channel === "sms" ? "+15551234567" : "you@example.com"} data-testid="test-to" />
                  </div>
                  <div>
                    <Label>Body</Label>
                    <Input required value={test.body} onChange={(e) => setTest({ ...test, body: e.target.value })} data-testid="test-body" />
                  </div>
                  <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="test-send-btn">Send</Button></DialogFooter>
                </form>
              </DialogContent>
            </Dialog>

            <Dialog open={open} onOpenChange={setOpen}>
              <DialogTrigger asChild>
                <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-family-btn">
                  <Plus className="w-4 h-4 mr-2" /> Add family contact
                </Button>
              </DialogTrigger>
              <DialogContent>
                <DialogHeader><DialogTitle className="font-display">New family contact</DialogTitle></DialogHeader>
                <form onSubmit={create} className="space-y-3">
                  <div>
                    <Label>Resident</Label>
                    <Select value={form.resident_id} onValueChange={(v) => setForm({ ...form, resident_id: v })}>
                      <SelectTrigger data-testid="fam-resident"><SelectValue placeholder="Pick a resident" /></SelectTrigger>
                      <SelectContent>
                        {(residents || []).map((r) => (
                          <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Room {r.room}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div><Label>Name</Label><Input required data-testid="fam-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Liam O'Brien" /></div>
                    <div><Label>Relationship</Label><Input data-testid="fam-rel" value={form.relationship} onChange={(e) => setForm({ ...form, relationship: e.target.value })} placeholder="son" /></div>
                  </div>
                  <div><Label>Phone (SMS)</Label><Input data-testid="fam-phone" value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} placeholder="+15551234567" /></div>
                  <div><Label>Email</Label><Input type="email" data-testid="fam-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="family@example.com" /></div>
                  <div>
                    <Label>Notify on</Label>
                    <div className="grid grid-cols-2 gap-2 mt-2">
                      {NOTIFY_OPTIONS.map((opt) => (
                        <label key={opt.key} className="flex items-center gap-2 cursor-pointer" data-testid={`fam-notify-${opt.key}`}>
                          <Checkbox checked={form.notify_on.includes(opt.key)} onCheckedChange={() => toggleNotifyOn(opt.key)} />
                          <span className="text-sm">{opt.label}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="fam-save">Save</Button></DialogFooter>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Contact</TableHead><TableHead>Resident</TableHead><TableHead>Phone</TableHead><TableHead>Email</TableHead><TableHead>Notify on</TableHead><TableHead></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {contacts.map((c) => {
              const resident = (residents || []).find((r) => r.resident_id === c.resident_id);
              return (
                <TableRow key={c.contact_id} data-testid={`fam-row-${c.contact_id}`}>
                  <TableCell>
                    <span className="font-medium">{c.name}</span>
                    {c.relationship && <span className="text-caos-mute text-xs block">{c.relationship}</span>}
                  </TableCell>
                  <TableCell>{resident ? `${resident.name} · ${resident.room}` : c.resident_id}</TableCell>
                  <TableCell className="font-mono text-xs">{c.phone || "—"}</TableCell>
                  <TableCell className="font-mono text-xs">{c.email || "—"}</TableCell>
                  <TableCell>
                    <div className="flex flex-wrap gap-1">
                      {c.notify_on.map((k) => <Badge key={k} variant="outline" className="text-xs">{k}</Badge>)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="sm" onClick={() => remove(c.contact_id)} data-testid={`del-fam-${c.contact_id}`}>
                      <Trash2 className="w-4 h-4 text-caos-terracotta" />
                    </Button>
                  </TableCell>
                </TableRow>
              );
            })}
            {contacts.length === 0 && (
              <TableRow><TableCell colSpan={6} className="text-center text-caos-mute py-6">No family contacts yet.</TableCell></TableRow>
            )}
          </TableBody>
        </Table>
      </Card>

      {/* Notification log */}
      <Card className="border-caos-line p-5">
        <h3 className="font-display text-lg font-medium text-caos-forest mb-3">Recent notifications</h3>
        <div className="space-y-2" data-testid="notif-log">
          {notifs.map((n) => (
            <div key={n.notification_id || `${n.created_at}-${n.to}`} className="flex items-start gap-3 p-3 bg-caos-ambient/40 rounded-lg">
              {n.channel === "sms" ? <Smartphone className="w-4 h-4 text-caos-forest mt-0.5" /> : <Mail className="w-4 h-4 text-caos-forest mt-0.5" />}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-caos-mute">{n.to}</span>
                  <Badge
                    variant="outline"
                    className={`text-xs ${n.status === "sent" ? "text-caos-moss" : n.status === "failed" ? "text-caos-terracotta" : "text-caos-mute"}`}
                  >
                    {n.status}
                  </Badge>
                  <span className="text-xs text-caos-mute ml-auto">{n.created_at ? new Date(n.created_at).toLocaleString() : ""}</span>
                </div>
                <p className="text-sm text-caos-ink mt-1">{n.body}</p>
                {n.provider_response && <p className="text-xs text-caos-mute mt-1 italic">{n.provider_response}</p>}
              </div>
            </div>
          ))}
          {notifs.length === 0 && <p className="text-caos-mute text-sm">No notifications yet.</p>}
        </div>
      </Card>
    </div>
  );
}

function ProviderBadge({ label, ok, hint }) {
  return (
    <div className="flex items-start gap-3 p-3 bg-caos-ambient/40 rounded-lg">
      {ok ? <CheckCircle2 className="w-5 h-5 text-caos-moss mt-0.5" /> : <XCircle className="w-5 h-5 text-caos-mute mt-0.5" />}
      <div>
        <p className="font-semibold text-caos-forest">{label} — {ok ? "connected" : "not configured"}</p>
        <p className="text-caos-mute text-xs mt-1">{hint}</p>
      </div>
    </div>
  );
}
