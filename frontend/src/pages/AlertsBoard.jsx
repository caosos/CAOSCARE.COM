import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { RefreshCw, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import AlertDetailDialog from "./AlertDetailDialog";
import { filterAlerts, staleSummary, isLikelyStale, alertTone, STALE_HOURS } from "../lib/alertsView";

const TONE = {
  critical: { border: "#B6463A", bg: "#FDECE9", text: "#98392F" },
  warn: { border: "#D28D38", bg: "#FDF3E3", text: "#8B5A20" },
  info: { border: "#4A7C59", bg: "#EAF3EC", text: "#2F5940" },
  muted: { border: "#A8A29E", bg: "#F3F1EE", text: "#7A6B56" },
};
const STATUSES = ["all", "active", "acknowledged", "resolved"];
const SEVERITIES = ["all", "emergency", "assist", "comfort"];

function ago(iso) {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

// One place to see alerts / resident-assistance events with real filters and
// an honest stale-data distinction. Reuses GET /alerts + AlertDetailDialog -
// the Level-1 event semantics are unchanged, this is read + navigate only.
export default function AlertsBoard() {
  const [sp, setSp] = useSearchParams();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailId, setDetailId] = useState(null);
  const [hideStale, setHideStale] = useState(false);

  const status = sp.get("status") || "all";
  const severity = sp.get("severity") || "all";
  const setParam = (k, v) => setSp((p) => { const n = new URLSearchParams(p); v && v !== "all" ? n.set(k, v) : n.delete(k); return n; }, { replace: true });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/alerts", { params: { limit: 500 } });
      setAlerts(data);
    } catch { toast.error("Could not load alerts"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []);

  const summary = useMemo(() => staleSummary(alerts), [alerts]);
  const rows = useMemo(() => filterAlerts(alerts, { status, severity, hideStale }), [alerts, status, severity, hideStale]);

  return (
    <div className="space-y-4" data-testid="alerts-board">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display text-2xl font-medium text-caos-forest">Alerts &amp; assistance events</h2>
          <p className="text-caos-mute text-sm mt-1">{rows.length} shown · {summary.open_total} open ({summary.live} live, {summary.likely_stale} likely stale)</p>
        </div>
        <Button variant="ghost" onClick={load} data-testid="alerts-refresh"><RefreshCw className="w-4 h-4 mr-2" /> Refresh</Button>
      </div>

      <div className="flex flex-wrap gap-2 items-center">
        <Select value={status} onValueChange={(v) => setParam("status", v)}>
          <SelectTrigger className="w-40" data-testid="alerts-filter-status"><SelectValue /></SelectTrigger>
          <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s === "all" ? "Any status" : s}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={severity} onValueChange={(v) => setParam("severity", v)}>
          <SelectTrigger className="w-40" data-testid="alerts-filter-severity"><SelectValue /></SelectTrigger>
          <SelectContent>{SEVERITIES.map((s) => <SelectItem key={s} value={s}>{s === "all" ? "Any severity" : s}</SelectItem>)}</SelectContent>
        </Select>
        <label className="flex items-center gap-2 text-sm text-caos-mute cursor-pointer">
          <input type="checkbox" checked={hideStale} onChange={(e) => setHideStale(e.target.checked)} data-testid="alerts-hide-stale" />
          Hide likely-stale (open &gt;{STALE_HOURS}h)
        </label>
      </div>

      {summary.likely_stale > 0 && !hideStale && (
        <div className="flex items-start gap-2 text-xs text-caos-mute bg-[#F3F1EE] rounded-lg p-3" data-testid="alerts-stale-banner">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {summary.likely_stale} open event{summary.likely_stale === 1 ? "" : "s"} older than {STALE_HOURS}h — likely stale RF/pendant test activations from earlier sessions, not a live queue. Not deleted; lifecycle cleanup is a separate task.
        </div>
      )}

      <div className="space-y-2" data-testid="alerts-list">
        {!loading && rows.length === 0 && (
          <Card className="p-8 text-center border-caos-line text-caos-mute italic" data-testid="alerts-empty">No alerts match these filters.</Card>
        )}
        {rows.map((a) => {
          const c = TONE[alertTone(a)];
          const stale = isLikelyStale(a);
          return (
            <Card key={a.alert_id} data-testid={`alert-row-${a.alert_id}`}
              className="p-4 border-2 cursor-pointer hover:shadow-sm transition-shadow"
              style={{ borderLeftColor: c.border, borderLeftWidth: 6 }}
              onClick={() => setDetailId(a.alert_id)}>
              <div className="flex items-center gap-2 flex-wrap">
                <Badge style={{ background: c.bg, color: c.text, border: `1px solid ${c.border}` }} className="uppercase text-[10px] font-bold">{a.severity}</Badge>
                <Badge variant="outline" className="uppercase text-[10px]">{a.status}</Badge>
                {a.escalation_level > 0 && <Badge className="bg-caos-amber text-white text-[10px]">Esc Lv{a.escalation_level}</Badge>}
                {a.aria_state && a.aria_state !== "dormant" && <Badge variant="outline" className="text-[10px] uppercase">Aria {String(a.aria_state).replace("_", " ")}</Badge>}
                {stale && <Badge className="bg-caos-mute/20 text-caos-mute text-[10px] uppercase">likely stale</Badge>}
                <span className="text-xs text-caos-mute">{ago(a.created_at)} ago</span>
              </div>
              <div className="font-semibold text-caos-forest mt-1">{a.resident_name || "Unknown resident"}</div>
              <div className="text-xs text-caos-mute">
                {[a.room ? `Room ${a.room}` : null, a.zone, `via ${String(a.triggered_by || "").replace("_", " ")}`,
                  a.acknowledged_by ? `ack by ${a.acknowledged_by}` : (a.status === "active" ? "unacknowledged" : null),
                  a.press_count > 1 ? `${a.press_count} presses` : null].filter(Boolean).join(" · ")}
              </div>
            </Card>
          );
        })}
      </div>

      <AlertDetailDialog alertId={detailId} open={!!detailId} onOpenChange={(o) => { if (!o) setDetailId(null); }} onChanged={load} />
    </div>
  );
}
