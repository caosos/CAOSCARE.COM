import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { CATEGORY_META, fmtSeconds } from "../lib/clinician";
import ClinicianRecentEvents from "../components/ClinicianRecentEvents";
import AlertDetailDialog from "./AlertDetailDialog";
import { Button } from "../components/ui/button";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import {
  Activity, AlertTriangle, Clock, Heart, Stethoscope, TrendingUp, TrendingDown, Minus, Loader2,
} from "lucide-react";

// Clinician Dashboard — visualizes /api/residents/{id}/stats so clinical
// admins (admin nurses) can see a resident's care pattern at a glance.
// Compares current 30-day window to the prior 30-day window so trends are
// visible without heavy charting deps.


export default function ClinicianTab({ residents = [] }) {
  const [residentId, setResidentId] = useState("");
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState(null);
  const [state, setState] = useState("idle");          // idle | loading | ok | error
  const [error, setError] = useState("");
  const [summary, setSummary] = useState("");
  const [summaryState, setSummaryState] = useState("loading");
  const [openAlert, setOpenAlert] = useState(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (residents.length && !residentId) setResidentId(residents[0].resident_id);
  }, [residents, residentId]);

  useEffect(() => {
    if (!residentId) return;
    let live = true;
    setState("loading");
    api.get(`/residents/${residentId}/stats?days=${days}`)
      .then(({ data }) => { if (live) { setStats(data); setState("ok"); } })
      .catch((err) => {
        if (!live) return;
        setStats(null); setState("error");
        setError(err?.response?.status === 403 ? "Resident care patterns are open to administrators and nursing staff." : "Could not load this resident's care pattern.");
      });
    setSummaryState("loading");
    api.get(`/residents/${residentId}/briefing`)
      .then(({ data }) => { if (live) { setSummary(data?.narrative || ""); setSummaryState("ok"); } })
      .catch(() => { if (live) setSummaryState("error"); });
    return () => { live = false; };
  }, [residentId, days, reload]);

  return (
    <div className="space-y-6" data-testid="clinician-tab">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h2 className="font-display text-3xl text-caos-forest">Resident care patterns</h2>
          <p className="text-caos-mute text-sm mt-1 max-w-2xl" data-testid="clinician-purpose">
            For administrators and nursing leads: pick a resident to see how often they called for help, how fast staff answered,
            and what the calls were about, compared with the period before. Open any event to see its timeline and close it out.
            This is not a medical record.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Select value={residentId} onValueChange={setResidentId}>
            <SelectTrigger className="w-[260px] max-w-full" data-testid="clinician-resident-picker"><SelectValue placeholder="Pick a resident" /></SelectTrigger>
            <SelectContent>
              {residents.map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Rm {r.room}</SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={String(days)} onValueChange={(v) => setDays(parseInt(v))}>
            <SelectTrigger className="w-[140px]" data-testid="clinician-days-picker"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="7">Last 7 days</SelectItem>
              <SelectItem value="14">Last 14 days</SelectItem>
              <SelectItem value="30">Last 30 days</SelectItem>
              <SelectItem value="90">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </header>

      {!residents.length && <Card className="p-8 text-center text-caos-mute">No residents yet. Add residents under Residents &amp; care → Residents.</Card>}
      {state === "loading" && <div className="py-12 text-center"><Loader2 className="w-8 h-8 animate-spin text-caos-forest mx-auto" /></div>}
      {state === "error" && (
        <Card className="p-6 text-sm border-caos-line" data-testid="clinician-error">
          {error} <Button size="sm" variant="outline" className="ml-2" onClick={() => setReload((n) => n + 1)}>Try again</Button>
        </Card>
      )}
      {state === "ok" && stats && (
        <>
          {stats.current_window.total_calls === 0 && (
            <Card className="p-4 text-sm text-caos-mute border-caos-line" data-testid="clinician-no-calls">No calls for help in the last {days} days.</Card>
          )}
          <KpiRow current={stats.current_window} previous={stats.previous_window} />
          <CategoryBreakdown current={stats.current_window} previous={stats.previous_window} />
          <ClinicianRecentEvents events={stats.recent_events} summary={summary} summaryState={summaryState} onOpen={setOpenAlert} />
        </>
      )}
      <AlertDetailDialog alertId={openAlert} open={!!openAlert} onOpenChange={(o) => { if (!o) setOpenAlert(null); }} onChanged={() => setReload((n) => n + 1)} />
    </div>
  );
}

function KpiRow({ current, previous }) {
  const cards = [
    { icon: Activity, label: "Total calls", curr: current.total_calls, prev: previous.total_calls, fmt: (v) => v },
    { icon: AlertTriangle, label: "Falls", curr: current.falls_during_call, prev: previous.falls_during_call, fmt: (v) => v, danger: true },
    { icon: Clock, label: "Avg response", curr: current.avg_response_s, prev: previous.avg_response_s, fmt: fmtSeconds, lowerBetter: true },
    { icon: Stethoscope, label: "Avg duration", curr: current.avg_duration_s, prev: previous.avg_duration_s, fmt: fmtSeconds },
    { icon: Heart, label: "Unresolved", curr: current.unresolved, prev: previous.unresolved, fmt: (v) => v, danger: true, lowerBetter: true,
      note: current.unresolved_older ? `${current.unresolved_older} older than 3 days, need review` : null },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="clinician-kpis">
      {cards.map((c, i) => <KpiCard key={i} {...c} />)}
    </div>
  );
}

function KpiCard({ icon: Icon, label, curr, prev, fmt, danger = false, lowerBetter = false, note = null }) {
  const d = trend(curr, prev, lowerBetter);
  const accent = danger && (curr || 0) > 0 ? "text-caos-terracotta" : "text-caos-forest";
  return (
    <Card className="p-4 border-caos-line" data-testid={`kpi-${label.toLowerCase().replace(/\s+/g, "-")}`}>
      <div className="flex items-center gap-2 text-xs uppercase tracking-widest text-caos-mute">
        <Icon className="w-3.5 h-3.5" /> {label}
      </div>
      <div className={`mt-2 font-display text-3xl font-light ${accent}`}>
        {curr === null || curr === undefined ? "—" : fmt(curr)}
      </div>
      {note && <div className="mt-1 text-[11px] text-caos-mute" data-testid="kpi-unresolved-older">{note}</div>}
      {d && (
        <div className={`mt-1 text-xs flex items-center gap-1 ${d.color}`}>
          {d.icon}
          <span className="font-mono">{d.label}</span>
          <span className="text-caos-mute">vs prior</span>
        </div>
      )}
    </Card>
  );
}

function trend(curr, prev, lowerBetter = false) {
  if (curr === null || curr === undefined || prev === null || prev === undefined) return null;
  if (curr === 0 && prev === 0) return null;
  if (curr === prev) return { icon: <Minus className="w-3 h-3" />, label: "no change", color: "text-caos-mute" };
  const up = curr > prev;
  const good = lowerBetter ? !up : up;
  const color = good ? "text-caos-forest" : "text-caos-terracotta";
  const Icon = up ? TrendingUp : TrendingDown;
  const delta = prev === 0 ? "" : `${up ? "+" : ""}${Math.round(((curr - prev) / Math.max(prev, 1)) * 100)}%`;
  return { icon: <Icon className="w-3 h-3" />, label: delta || (up ? "up" : "down"), color };
}

function CategoryBreakdown({ current, previous }) {
  const cats = useMemo(() => {
    const all = new Set([...Object.keys(current.by_category), ...Object.keys(previous.by_category)]);
    return Array.from(all)
      .map((k) => ({ key: k, curr: current.by_category[k] || 0, prev: previous.by_category[k] || 0 }))
      .sort((a, b) => b.curr - a.curr);
  }, [current, previous]);
  const max = Math.max(1, ...cats.map((c) => Math.max(c.curr, c.prev)));

  return (
    <Card className="p-5 border-caos-line" data-testid="clinician-categories">
      <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-4">
        <Stethoscope className="w-4 h-4 text-caos-forest" /> Calls by category
      </div>
      {cats.length === 0 ? (
        <p className="text-caos-mute italic text-sm">No calls in this window.</p>
      ) : (
        <div className="space-y-3">
          {cats.map((c) => {
            const meta = CATEGORY_META[c.key] || { label: c.key, color: "#7A6B56" };
            return (
              <div key={c.key} data-testid={`cat-row-${c.key}`}>
                <div className="flex items-center justify-between text-sm">
                  <span className="font-semibold text-caos-forest">{meta.label}</span>
                  <span className="font-mono text-caos-ink/80">
                    <span className="text-caos-forest">{c.curr}</span>
                    <span className="text-caos-mute"> · prior {c.prev}</span>
                  </span>
                </div>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <div className="flex-1 h-2 rounded-full bg-caos-ambient overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{ width: `${(c.curr / max) * 100}%`, backgroundColor: meta.color }}
                    />
                  </div>
                  <div className="flex-1 h-2 rounded-full bg-caos-ambient overflow-hidden opacity-50">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${(c.prev / max) * 100}%`, backgroundColor: meta.color }}
                    />
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
      <p className="text-[10px] text-caos-mute mt-4 italic">Solid bar = current window · faded bar = prior window</p>
    </Card>
  );
}

