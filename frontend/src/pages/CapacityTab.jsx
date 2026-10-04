import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Input } from "../components/ui/input";
import { RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { LEVEL_LABEL, LEVEL_TONE, loadGroups, pct, projectionText, utilPct } from "../lib/capacity";

// Capacity and scalability (routes/capacity_monitor.py). Every number comes
// from the latest capacity sample; safe values come from the measured load
// test or are marked "configured". Simulator traffic is shown on its own.

function Stat({ label, value, sub }) {
  return (
    <div className="rounded-lg border border-caos-line p-3">
      <div className="text-xs text-caos-mute">{label}</div>
      <div className="text-xl font-semibold text-caos-ink">{value}</div>
      {sub && <div className="text-xs text-caos-mute mt-0.5">{sub}</div>}
    </div>
  );
}

function AlertRow({ a, onChanged }) {
  const [note, setNote] = useState("");
  const [action, setAction] = useState("");
  const call = async (path, body) => {
    try {
      await api.post(`/capacity/alerts/${a.alert_id}/${path}`, body);
      toast.success(path === "acknowledge" ? "Acknowledged" : "Resolved");
      onChanged();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Could not update the alert");
    }
  };
  return (
    <div className="rounded-lg border border-caos-line p-4 space-y-2" data-testid={`capacity-alert-${a.metric}`}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge className={LEVEL_TONE[a.level]}>{LEVEL_LABEL[a.level]}</Badge>
        <span className="font-medium">{a.component}</span>
        <span className="text-caos-mute text-sm">{a.metric}</span>
        {a.simulated && <Badge variant="outline">simulated traffic</Badge>}
        <span className="text-xs text-caos-mute ml-auto">{a.status} · opened {new Date(a.opened_at).toLocaleString()}</span>
      </div>
      <div className="text-sm">
        Measured {a.measured_value} {a.unit} against a tested safe value of {a.tested_safe_value} ({utilPct(a.utilization)}).
        Caused by: {a.traffic_class}.
      </div>
      {a.recommendation?.type && <div className="text-sm font-medium">Recommendation: {a.recommendation.text}</div>}
      {a.acknowledged_by && <div className="text-xs text-caos-mute">Acknowledged by {a.acknowledged_by}</div>}
      <div className="flex flex-wrap gap-2 items-center">
        {a.status === "open" && <Button size="sm" variant="outline" onClick={() => call("acknowledge", { note })}>Acknowledge</Button>}
        <Input className="h-8 max-w-xs" placeholder="Evidence (required to resolve)" value={note} onChange={(e) => setNote(e.target.value)} />
        <Input className="h-8 max-w-xs" placeholder="Action taken, if still high" value={action} onChange={(e) => setAction(e.target.value)} />
        <Button size="sm" onClick={() => call("resolve", { evidence: note, action_taken: action || null })}>Resolve</Button>
      </div>
    </div>
  );
}

export default function CapacityTab() {
  const [data, setData] = useState(null);
  const load = async () => {
    try {
      const { data: d } = await api.get("/capacity/status");
      setData(d);
    } catch {
      toast.error("Could not load capacity status");
    }
  };
  useEffect(() => {
    load();
    const t = setInterval(load, 15000);
    return () => clearInterval(t);
  }, []);

  if (!data) return <Card className="border-caos-line p-8 text-caos-mute">Loading capacity…</Card>;
  const s = data.latest;
  if (!s) return <Card className="border-caos-line p-8 text-caos-mute">No capacity samples yet - the monitor samples every {data.monitor.interval_s} s.</Card>;
  const v = s.voice || {}, adm = v.admission || {}, h = s.host || {}, hr = s.headroom || {};
  const loads = loadGroups(s);
  const metrics = Object.entries(hr.per_metric || {}).filter(([, m]) => m.utilization !== null)
    .sort((a, b) => b[1].utilization - a[1].utilization);

  return (
    <div className="space-y-6" data-testid="capacity-tab">
      <div className="flex items-center gap-3 flex-wrap">
        <h2 className="text-2xl font-display text-caos-ink">Capacity</h2>
        <Badge className={LEVEL_TONE[data.status]} data-testid="capacity-status">{LEVEL_LABEL[data.status]}</Badge>
        <span className="text-xs text-caos-mute">Sample {new Date(s.at).toLocaleTimeString()}</span>
        <Button size="sm" variant="outline" className="ml-auto" onClick={load}><RefreshCw className="w-4 h-4 mr-1" />Refresh</Button>
      </div>

      <Card className="border-caos-line p-5 space-y-3">
        <div className="font-medium">Headroom</div>
        <div className="text-sm">
          Current bottleneck: <b>{hr.bottleneck_component || "—"}</b> ({hr.bottleneck}) at {utilPct(hr.bottleneck_utilization)} of its safe value -
          remaining safe headroom {hr.headroom_pct ?? "—"}%.
        </div>
        <div className="text-sm">Projection: {projectionText(data.projection)}</div>
        <div className="text-sm">
          Emergency reserve: {hr.emergency_reserve?.reserved_staff_help_slots ?? 0} staff-help slots
          ({hr.emergency_reserve?.reserved_in_use ?? 0} in use); emergency words bypass slots entirely.
        </div>
      </Card>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Resident load" value={`${loads.resident}/min`} sub="voice, devices, help (real)" />
        <Stat label="Staff load" value={`${loads.staff}/min`} sub="dashboards and workflow" />
        <Stat label="Simulator load" value={`${loads.simulator}/min`} sub="never counted as real demand" />
        <Stat label="Background load" value={`${loads.background}/min`} sub="email, notifications, receipts" />
        <Stat label="Active voice sessions" value={v.active_sessions ?? 0} sub={`${s.voice_sessions?.new_per_min ?? 0} new/min`} />
        <Stat label="Voice queue" value={adm.queued ?? 0} sub={`oldest ${adm.oldest_queued_s ?? 0} s · ${adm.active ?? 0}/${(adm.slots || 0) * (adm.workers || 1)} slots`} />
        <Stat label="Voice first answer p95" value={v.latency_p95_s ? `${v.latency_p95_s} s` : "—"} sub={`p50 ${v.latency_p50_s ?? "—"} · p99 ${v.latency_p99_s ?? "—"}`} />
        <Stat label="Provider problems" value={`${(v.rate_limited || 0) + (v.llm_failures || 0) + (v.timeouts || 0)}`} sub={`429s ${v.rate_limited || 0} · failures ${v.llm_failures || 0} · timeouts ${v.timeouts || 0}`} />
        <Stat label="Host CPU" value={pct(h.cpu_pct)} sub={`load ${h.load_1 ?? "—"} · CAOSCare share ${pct(s.caoscare_cpu_share_pct)}`} />
        <Stat label="Memory" value={pct(h.memory?.used_pct)} sub={`${h.memory?.available_mb ?? "—"} MB free · swap out ${h.swap_out_per_s ?? 0}/s`} />
        <Stat label="Disk" value={pct(h.disk_used_pct)} sub={`${h.disk_free_gb ?? "—"} GB free · ${h.disk_latency_ms ?? "—"} ms/IO`} />
        <Stat label="Database" value={`${s.db?.ping_ms ?? "—"} ms`} sub={`${s.db?.connections_current ?? "—"} connections`} />
        <Stat label="Staff clients" value={s.staff?.active_clients ?? 0} sub={`${s.staff?.live_board_clients ?? 0} on live boards · ${s.staff?.reports ?? 0} reports`} />
        <Stat label="Devices" value={`${s.devices?.online ?? 0}/${s.devices?.configured ?? 0} online`} sub={`${s.devices?.events_per_min ?? 0} events/min · ${s.devices?.failed_commands ?? 0} failed`} />
        <Stat label="Receipt writes" value={s.receipts?.writes ?? 0} sub={`p95 ${s.receipts?.write_p95_ms ?? "—"} ms · ${s.receipts_orphan_recent_tasks ?? 0} recent tasks without receipt`} />
        <Stat label="Temperature" value={h.temperature_c ? `${Math.round(h.temperature_c)} °C` : "—"} />
      </div>

      <Card className="border-caos-line p-5">
        <div className="font-medium mb-3">Capacity alerts ({data.alerts.length})</div>
        <div className="space-y-3">
          {data.alerts.length === 0 && <div className="text-sm text-caos-mute">No open capacity alerts.</div>}
          {data.alerts.map((a) => <AlertRow key={a.alert_id} a={a} onChanged={load} />)}
        </div>
      </Card>

      <Card className="border-caos-line p-5">
        <div className="font-medium mb-3">Metrics against tested safe values</div>
        <table className="w-full text-sm">
          <thead><tr className="text-left text-caos-mute"><th>Metric</th><th>Component</th><th>Value</th><th>Safe</th><th>Use</th><th>Source</th></tr></thead>
          <tbody>
            {metrics.map(([k, m]) => (
              <tr key={k} className="border-t border-caos-line">
                <td className="py-1">{k}</td><td>{m.component}</td><td>{m.value} {m.unit}</td>
                <td>{m.safe}</td><td>{utilPct(m.utilization)}</td><td>{m.source}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
