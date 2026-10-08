import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Mail, Smartphone, Send, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";
import { deliveryStatus, routeLabel } from "../lib/notificationDelivery";
import EmailInboundPanel from "./EmailInboundPanel";

const STATUS_FILTERS = ["all", "logged", "simulated", "sent", "delivered", "failed", "bounced", "delayed"];

// Outbound provider status, a test send, and the delivery log for every
// notification CAOSCare attempted (department, family, test). Statuses come
// from lib/notificationDelivery so "recorded only" is never shown as sent.
export default function CommunicationsTab() {
  const [status, setStatus] = useState(null);
  const [notifs, setNotifs] = useState([]);
  const [filter, setFilter] = useState("all");
  const [testOpen, setTestOpen] = useState(false);
  const [test, setTest] = useState({ channel: "email", to: "", body: "CAOSCare test notification." });

  const load = async () => {
    try {
      const q = filter === "all" ? "" : `&status=${filter}`;
      const [s, n] = await Promise.all([api.get("/notifications/status"), api.get(`/notifications?limit=100${q}`)]);
      setStatus(s.data);
      setNotifs(n.data);
    } catch {
      toast.error("Could not load notifications");
    }
  };
  useEffect(() => { load(); }, [filter]); // eslint-disable-line react-hooks/exhaustive-deps

  const sendTest = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/notifications/test", test);
      toast.success(deliveryStatus(data.status).label);
      setTestOpen(false);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <div className="space-y-6" data-testid="communications-panel">
      <Card className="border-caos-line p-5">
        <div className="flex justify-between items-center flex-wrap gap-2 mb-3">
          <h3 className="font-display text-lg font-medium text-caos-forest">Providers</h3>
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
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="email">Email (Resend)</SelectItem>
                      <SelectItem value="sms">SMS (Twilio)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>To</Label>
                  <Input required value={test.to} onChange={(e) => setTest({ ...test, to: e.target.value })}
                    placeholder={test.channel === "sms" ? "+15551234567" : "you@example.com"} data-testid="test-to" />
                </div>
                <div>
                  <Label>Body</Label>
                  <Input required value={test.body} onChange={(e) => setTest({ ...test, body: e.target.value })} />
                </div>
                <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="test-send-btn">Send</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <ProviderBadge label="Resend email" ok={status?.resend_configured} detail={status?.resend_from} />
          <ProviderBadge label="Twilio SMS" ok={status?.twilio_configured} detail={status?.twilio_from} />
        </div>
        <p className="text-caos-mute text-sm mt-3">
          Without a configured provider, notifications are recorded here but not sent. "Accepted by provider"
          means the provider took the message; "Delivered" appears only when the provider reports delivery.
        </p>
      </Card>

      <Card className="border-caos-line p-5">
        <div className="flex justify-between items-center flex-wrap gap-2 mb-3">
          <h3 className="font-display text-lg font-medium text-caos-forest">Notification delivery</h3>
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-44"><SelectValue /></SelectTrigger>
            <SelectContent>
              {STATUS_FILTERS.map((f) => (
                <SelectItem key={f} value={f}>{f === "all" ? "All statuses" : deliveryStatus(f).label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-2" data-testid="notif-log">
          {notifs.map((n) => <NotificationRow key={n.notification_id} n={n} />)}
          {notifs.length === 0 && <p className="text-caos-mute text-sm">No notifications.</p>}
        </div>
      </Card>

      <EmailInboundPanel />
    </div>
  );
}

function NotificationRow({ n }) {
  const s = deliveryStatus(n.status);
  const route = routeLabel(n.route);
  const last = (n.delivery_events || []).slice(-1)[0];
  return (
    <div className="flex items-start gap-3 p-3 bg-caos-ambient/40 rounded-lg">
      {n.channel === "sms" ? <Smartphone className="w-4 h-4 text-caos-forest mt-0.5" /> : <Mail className="w-4 h-4 text-caos-forest mt-0.5" />}
      <div className="flex-1 min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-xs text-caos-mute">{n.to || "(no recipient)"}</span>
          <Badge variant="outline" className={`text-xs ${s.tone}`}>{s.label}</Badge>
          {n.department && <Badge variant="outline" className="text-xs">{n.department}</Badge>}
          {route && <span className="text-xs text-caos-mute">{route}</span>}
          <span className="text-xs text-caos-mute ml-auto">{n.created_at ? new Date(n.created_at).toLocaleString() : ""}</span>
        </div>
        {n.subject && <p className="text-sm font-medium mt-1">{n.subject}</p>}
        <p className="text-sm text-caos-ink mt-1 break-words">{n.body}</p>
        {last && <p className="text-xs text-caos-mute mt-1">Provider: {last.type}{last.detail ? ` - ${last.detail}` : ""}</p>}
        {n.status === "failed" && n.provider_response && <p className="text-xs text-caos-terracotta mt-1 italic break-words">{n.provider_response}</p>}
      </div>
    </div>
  );
}

function ProviderBadge({ label, ok, detail }) {
  return (
    <div className="flex items-start gap-3 p-3 bg-caos-ambient/40 rounded-lg">
      {ok ? <CheckCircle2 className="w-5 h-5 text-caos-moss mt-0.5" /> : <XCircle className="w-5 h-5 text-caos-mute mt-0.5" />}
      <div>
        <p className="font-semibold text-caos-forest">{label} - {ok ? "configured" : "not configured"}</p>
        {ok && detail && <p className="text-caos-mute text-xs mt-1">From {detail}</p>}
      </div>
    </div>
  );
}
