import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Switch } from "../components/ui/switch";
import { AlertTriangle, Save, Activity } from "lucide-react";
import { toast } from "sonner";

export default function EscalationTab() {
  const [rule, setRule] = useState(null);
  const [tickResult, setTickResult] = useState(null);

  useEffect(() => {
    api.get("/escalation/rule").then((r) => setRule(r.data));
  }, []);

  const save = async () => {
    try {
      await api.put("/escalation/rule", rule);
      toast.success("Saved");
    } catch (err) { toast.error(err?.response?.data?.detail || "Save failed"); }
  };

  const tick = async () => {
    try {
      const { data } = await api.post("/escalation/tick");
      setTickResult(data);
      toast.success(`Tick complete — ${data.escalated_to_2 + data.escalated_to_3} alerts moved`);
    } catch (err) { toast.error(err?.response?.data?.detail || "Tick failed"); }
  };

  if (!rule) return <p className="text-caos-mute italic">Loading…</p>;

  return (
    <div className="space-y-6" data-testid="escalation-tab">
      <div>
        <h2 className="font-display text-3xl text-caos-forest">Auto-escalation</h2>
        <p className="text-caos-mute text-sm mt-1 max-w-2xl">
          When an alert sits unacknowledged, escalate it. Level 2 pages a supervisor.
          Level 3 pages on-call medical. Times are seconds since alert creation.
        </p>
      </div>

      <Card className="p-5 border-caos-line">
        <div className="flex items-center justify-between mb-4">
          <span className="text-sm font-bold uppercase tracking-widest text-caos-mute">Enabled</span>
          <Switch checked={rule.enabled} onCheckedChange={(v) => setRule({ ...rule, enabled: v })} data-testid="esc-enabled" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Field label="Level 2 trigger (seconds)" value={rule.level_2_seconds} onChange={(v) => setRule({ ...rule, level_2_seconds: parseInt(v) || 90 })} testid="esc-l2-seconds" />
          <Field label="Level 3 trigger (seconds)" value={rule.level_3_seconds} onChange={(v) => setRule({ ...rule, level_3_seconds: parseInt(v) || 150 })} testid="esc-l3-seconds" />
          <Field label="Supervisor phone (Level 2 SMS)" value={rule.notify_supervisor_phone || ""} onChange={(v) => setRule({ ...rule, notify_supervisor_phone: v })} testid="esc-l2-phone" />
          <Field label="On-call phone (Level 3 SMS)" value={rule.notify_oncall_phone || ""} onChange={(v) => setRule({ ...rule, notify_oncall_phone: v })} testid="esc-l3-phone" />
        </div>
        <Card className="p-3 bg-caos-amber/10 border-caos-amber/40 mt-4">
          <p className="text-xs text-caos-forest">
            <AlertTriangle className="inline w-3.5 h-3.5 mr-1" />
            Twilio credentials must be set in backend <code>.env</code> for SMS to actually fire.
            Until then, escalations log to the server console without sending.
          </p>
        </Card>
        <div className="flex gap-2 mt-4">
          <Button onClick={save} className="bg-caos-forest rounded-full" data-testid="esc-save">
            <Save className="w-4 h-4 mr-2" /> Save rule
          </Button>
          <Button onClick={tick} variant="outline" className="rounded-full" data-testid="esc-tick">
            <Activity className="w-4 h-4 mr-2" /> Run tick now
          </Button>
        </div>
      </Card>

      {tickResult && (
        <Card className="p-4 border-caos-line">
          <p className="text-xs uppercase tracking-widest text-caos-mute mb-2">Last tick result</p>
          <pre className="text-xs font-mono text-caos-forest">{JSON.stringify(tickResult, null, 2)}</pre>
        </Card>
      )}
    </div>
  );
}

function Field({ label, value, onChange, testid }) {
  return (
    <div>
      <p className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-1">{label}</p>
      <Input value={value ?? ""} onChange={(e) => onChange(e.target.value)} data-testid={testid} />
    </div>
  );
}
