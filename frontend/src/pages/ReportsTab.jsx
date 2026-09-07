import React, { useEffect, useMemo, useState } from "react";
import { api, API } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Download, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { exceptionKindLabel, exceptionTone, fmtHours, defaultWeekStart, buildQuery } from "../lib/reports";

const TONE = {
  critical: "bg-caos-terracotta/15 text-caos-terracotta border border-caos-terracotta",
  warn: "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  info: "bg-caos-moss/15 text-caos-forest border border-caos-moss",
  stale: "bg-caos-mute/10 text-caos-mute",
};

function today() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

async function downloadCsv(path, params, filename) {
  try {
    const token = localStorage.getItem("caos_token");
    const qs = buildQuery({ ...params, format: "csv" });
    const res = await fetch(`${API}${path}?${qs}`, { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const url = URL.createObjectURL(await res.blob());
    const a = document.createElement("a");
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
    toast.success(`${filename} downloaded`);
  } catch (e) {
    toast.error(e?.message || "Download failed");
  }
}

export default function ReportsTab() {
  const [mode, setMode] = useState("daily");
  const [departments, setDepartments] = useState([]);
  const [dept, setDept] = useState("all");
  const [date, setDate] = useState(today());
  const [weekStart, setWeekStart] = useState(defaultWeekStart());
  const [days, setDays] = useState("7");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/departments").then(({ data }) => setDepartments(data)).catch(() => {});
  }, []);

  const params = useMemo(() => (
    mode === "daily"
      ? { date, department: dept }
      : { week_start: weekStart, days, department: dept }
  ), [mode, date, weekStart, days, dept]);

  useEffect(() => {
    setLoading(true);
    const path = mode === "daily" ? "/reports/daily-exceptions" : "/reports/weekly-workload";
    api.get(path, { params: buildQueryObj(params) })
      .then(({ data }) => setData(data))
      .catch(() => toast.error("Could not load the report"))
      .finally(() => setLoading(false));
  }, [mode, params]); // eslint-disable-line react-hooks/exhaustive-deps

  const csv = () => {
    if (mode === "daily") downloadCsv("/reports/daily-exceptions", params, `daily-exceptions-${date}.csv`);
    else downloadCsv("/reports/weekly-workload", params, `weekly-workload-${weekStart}.csv`);
  };

  return (
    <div className="space-y-4" data-testid="reports-tab">
      <div>
        <h2 className="font-display text-2xl font-medium text-caos-forest">Operations reports</h2>
        <p className="text-caos-mute text-sm mt-1">Built from the same StaffTask / receipt / alert records as the Overview and Activity log. Export is the exact filtered rows.</p>
      </div>

      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex gap-2">
          <Button variant={mode === "daily" ? "default" : "outline"} className={`rounded-full border-2 ${mode === "daily" ? "bg-caos-forest" : ""}`} onClick={() => setMode("daily")} data-testid="reports-mode-daily">Daily exceptions</Button>
          <Button variant={mode === "weekly" ? "default" : "outline"} className={`rounded-full border-2 ${mode === "weekly" ? "bg-caos-forest" : ""}`} onClick={() => setMode("weekly")} data-testid="reports-mode-weekly">Weekly workload</Button>
        </div>
        {mode === "daily" ? (
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="reports-date" />
        ) : (
          <>
            <Input type="date" value={weekStart} onChange={(e) => setWeekStart(e.target.value)} data-testid="reports-week-start" />
            <Select value={days} onValueChange={setDays}>
              <SelectTrigger className="w-28" data-testid="reports-days"><SelectValue /></SelectTrigger>
              <SelectContent>{["7", "14", "30"].map((d) => <SelectItem key={d} value={d}>{d} days</SelectItem>)}</SelectContent>
            </Select>
          </>
        )}
        <Select value={dept} onValueChange={setDept}>
          <SelectTrigger className="w-44" data-testid="reports-dept"><SelectValue /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All departments</SelectItem>
            {departments.map((d) => <SelectItem key={d.slug} value={d.slug}>{d.label}</SelectItem>)}
          </SelectContent>
        </Select>
        <Button variant="outline" className="border-2 rounded-full" onClick={csv} data-testid="reports-csv"><Download className="w-4 h-4 mr-2" /> CSV</Button>
      </div>

      {loading && <Card className="p-8 text-caos-mute border-caos-line">Loading…</Card>}
      {!loading && data && mode === "daily" && <DailyTable data={data} />}
      {!loading && data && mode === "weekly" && <WeeklyTable data={data} />}

      {data?.caveats?.length > 0 && (
        <div className="text-xs text-caos-mute space-y-1">
          {data.caveats.map((c, i) => (
            <p key={i} className="flex items-start gap-2"><AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" /> {c}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function buildQueryObj(params) {
  const out = {};
  Object.entries(params).forEach(([k, v]) => { if (v && v !== "all") out[k] = v; });
  return out;
}

function DailyTable({ data }) {
  return (
    <Card className="border-caos-line overflow-hidden" data-testid="reports-daily">
      <div className="p-3 flex flex-wrap gap-2 text-xs border-b border-caos-line">
        <span className="text-caos-mute">{data.total} exception{data.total === 1 ? "" : "s"} · {data.date}</span>
        {Object.entries(data.counts || {}).map(([k, n]) => (
          <Badge key={k} variant="outline" className="text-[10px]">{exceptionKindLabel(k)}: {n}</Badge>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-caos-ambient/50 text-caos-mute text-xs uppercase tracking-wider">
            <tr><th className="text-left p-2">Kind</th><th className="text-left p-2">What</th><th className="text-left p-2">Dept</th><th className="text-left p-2">Where</th><th className="text-left p-2">Owner</th><th className="text-left p-2">Age</th><th className="text-left p-2">Reason</th></tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={`${r.ref_type}-${r.ref_id}`} data-testid={`exc-${r.ref_id}`} className="border-t border-caos-line">
                <td className="p-2"><Badge className={`text-[10px] uppercase ${TONE[exceptionTone(r)]}`}>{exceptionKindLabel(r.kind)}</Badge></td>
                <td className="p-2">{r.title}<div className="text-[10px] font-mono text-caos-mute truncate max-w-[140px]">{r.ref_type}:{r.ref_id}</div></td>
                <td className="p-2 text-caos-mute">{r.department_label}</td>
                <td className="p-2 text-caos-mute">{[r.room ? `Rm ${r.room}` : null, r.resident_name].filter(Boolean).join(" · ") || "—"}</td>
                <td className="p-2 text-caos-mute">{r.owner || <span className="italic">unowned</span>}</td>
                <td className="p-2 text-caos-mute whitespace-nowrap">{fmtHours(r.age_hours)}{r.overdue && <span className="text-caos-terracotta font-semibold"> · overdue</span>}</td>
                <td className="p-2 text-caos-mute truncate max-w-[260px]">{r.reason}{r.result ? ` — ${r.result}` : ""}</td>
              </tr>
            ))}
            {data.rows.length === 0 && <tr><td colSpan={7} className="p-8 text-center text-caos-mute italic" data-testid="reports-daily-empty">No exceptions for this date / filter.</td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function WeeklyTable({ data }) {
  return (
    <Card className="border-caos-line overflow-hidden" data-testid="reports-weekly">
      <div className="p-3 text-xs text-caos-mute border-b border-caos-line">{data.week_start} → {data.window_end} ({data.days} days)</div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-caos-ambient/50 text-caos-mute text-xs uppercase tracking-wider">
            <tr><th className="text-left p-2">Department</th><th className="text-left p-2">Created</th><th className="text-left p-2">Completed</th><th className="text-left p-2">Still open</th><th className="text-left p-2">Assigned</th><th className="text-left p-2">Unassigned</th><th className="text-left p-2">Oldest open</th><th className="text-left p-2">By staff</th></tr>
          </thead>
          <tbody>
            {data.rows.map((r) => (
              <tr key={r.department_slug} data-testid={`wk-${r.department_slug}`} className="border-t border-caos-line align-top">
                <td className="p-2 font-medium text-caos-forest">{r.department_label}</td>
                <td className="p-2">{r.created}</td>
                <td className="p-2">{r.completed}</td>
                <td className="p-2">{r.still_open}</td>
                <td className="p-2">{r.assigned_open}</td>
                <td className="p-2">{r.unassigned_open}</td>
                <td className="p-2 text-caos-mute">{r.oldest_open_age_hours != null ? fmtHours(r.oldest_open_age_hours) : "—"}</td>
                <td className="p-2 text-caos-mute text-xs">
                  {r.by_staff?.length ? r.by_staff.map((s) => <div key={s.user_id}>{s.name}: {s.open} open · {s.completed_this_week} done</div>) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
