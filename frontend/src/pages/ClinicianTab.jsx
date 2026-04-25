import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
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

const CATEGORY_META = {
  bathroom:    { label: "Bathroom",    color: "#4A7C59" },
  fall:        { label: "Fall",        color: "#B6463A" },
  pain:        { label: "Pain",        color: "#D4954A" },
  medication:  { label: "Medication",  color: "#7A6B56" },
  lonely:      { label: "Loneliness",  color: "#8E7AB5" },
  confusion:   { label: "Confusion",   color: "#5C7B8A" },
  meal:        { label: "Meal",        color: "#9B8550" },
  other:       { label: "Other",       color: "#7A6B56" },
  unclassified:{ label: "Unclassified",color: "#A8A29E" },
};

export default function ClinicianTab({ residents = [] }) {
  const [residentId, setResidentId] = useState("");
  const [days, setDays] = useState(30);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (residents.length && !residentId) setResidentId(residents[0].resident_id);
  }, [residents, residentId]);

  useEffect(() => {
    if (!residentId) return;
    setLoading(true);
    api.get(`/residents/${residentId}/stats?days=${days}`)
      .then(({ data }) => setStats(data))
      .catch(() => setStats(null))
      .finally(() => setLoading(false));
  }, [residentId, days]);

  return (
    <div className="space-y-6" data-testid="clinician-tab">
      <header className="flex items-end justify-between flex-wrap gap-4">
        <div>
          <h2 className="font-display text-3xl text-caos-forest">Clinician Dashboard</h2>
          <p className="text-caos-mute text-sm mt-1">
            Per-resident care pattern. Trends, response times, and recent events.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={residentId} onValueChange={setResidentId}>
            <SelectTrigger className="w-[260px]" data-testid="clinician-resident-picker"><SelectValue placeholder="Pick a resident" /></SelectTrigger>
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

      {loading && <div className="py-12 text-center"><Loader2 className="w-8 h-8 animate-spin text-caos-forest mx-auto" /></div>}

      {!loading && stats && (
        <>
          <KpiRow current={stats.current_window} previous={stats.previous_window} />
          <CategoryBreakdown current={stats.current_window} previous={stats.previous_window} />
          <RecentEvents events={stats.recent_events} narrative={stats.narrative} />
        </>
      )}

      {!loading && !stats && residentId && (
        <Card className="p-8 text-center text-caos-mute italic">No data for this resident yet.</Card>
      )}
    </div>
  );
}

function KpiRow({ current, previous }) {
  const cards = [
    { icon: Activity, label: "Total calls", curr: current.total_calls, prev: previous.total_calls, fmt: (v) => v },
    { icon: AlertTriangle, label: "Falls", curr: current.falls_during_call, prev: previous.falls_during_call, fmt: (v) => v, danger: true },
    { icon: Clock, label: "Avg response", curr: current.avg_response_s, prev: previous.avg_response_s, fmt: fmtSeconds, lowerBetter: true },
    { icon: Stethoscope, label: "Avg duration", curr: current.avg_duration_s, prev: previous.avg_duration_s, fmt: fmtSeconds },
    { icon: Heart, label: "Unresolved", curr: current.unresolved, prev: previous.unresolved, fmt: (v) => v, danger: true, lowerBetter: true },
  ];
  return (
    <div className="grid grid-cols-2 md:grid-cols-5 gap-3" data-testid="clinician-kpis">
      {cards.map((c, i) => <KpiCard key={i} {...c} />)}
    </div>
  );
}

function KpiCard({ icon: Icon, label, curr, prev, fmt, danger = false, lowerBetter = false }) {
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

function RecentEvents({ events = [], narrative }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card className="p-5 border-caos-line md:col-span-2" data-testid="clinician-recent">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-3">
          <Activity className="w-4 h-4 text-caos-forest" /> Recent events
        </div>
        {events.length === 0 ? (
          <p className="text-caos-mute italic text-sm">No events yet.</p>
        ) : (
          <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
            {events.map((e) => {
              const meta = CATEGORY_META[e.category] || { label: e.category, color: "#7A6B56" };
              return (
                <div key={e.alert_id} data-testid={`event-${e.alert_id}`} className="flex items-start gap-3 p-3 bg-caos-ambient/40 rounded-lg">
                  <div className="w-1.5 self-stretch rounded-full" style={{ backgroundColor: meta.color }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className="uppercase text-[10px] tracking-wider">{meta.label}</Badge>
                      <span className="text-xs text-caos-mute">{new Date(e.created_at).toLocaleString()}</span>
                      <SeverityBadge sev={e.severity} />
                      {e.status !== "resolved" && <Badge className="bg-caos-amber/30 text-caos-forest text-[10px] uppercase tracking-wider">{e.status}</Badge>}
                    </div>
                    {e.ai_summary && <p className="text-sm text-caos-forest mt-1 leading-snug">{e.ai_summary}</p>}
                    {e.resident_stated_reason && (
                      <p className="text-xs text-caos-mute mt-0.5 italic">"{e.resident_stated_reason}"</p>
                    )}
                    {e.outcome && <p className="text-xs text-caos-ink/80 mt-1">→ {e.outcome}</p>}
                    <div className="text-[10px] text-caos-mute mt-1 font-mono">
                      response {fmtSeconds(e.response_seconds)} · duration {fmtSeconds(e.duration_seconds)}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      <Card className="p-5 border-caos-line" data-testid="clinician-narrative">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-3">
          <Heart className="w-4 h-4 text-caos-forest" /> AI summary
        </div>
        {narrative ? (
          <p className="text-sm text-caos-forest leading-relaxed">{narrative}</p>
        ) : (
          <p className="text-caos-mute italic text-sm">
            A short paragraph summary of this resident's care pattern lives here when the
            backend has populated it. Tap "Brief" on the resident card to generate a fresh narrative.
          </p>
        )}
      </Card>
    </div>
  );
}

function SeverityBadge({ sev }) {
  const map = {
    emergency: "bg-caos-terracotta text-white",
    assist:    "bg-caos-forest/15 text-caos-forest border border-caos-forest",
    comfort:   "bg-caos-mute/15 text-caos-ink",
  };
  return <Badge className={`uppercase text-[10px] tracking-widest ${map[sev] || ""}`}>{sev}</Badge>;
}

function fmtSeconds(s) {
  if (s === null || s === undefined) return "—";
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const r = s % 60;
  return r ? `${m}m ${r}s` : `${m}m`;
}
