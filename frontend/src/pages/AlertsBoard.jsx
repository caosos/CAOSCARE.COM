import React, { useEffect, useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { RefreshCw, AlertCircle, Radio } from "lucide-react";
import { toast } from "sonner";
import AlertDetailDialog from "./AlertDetailDialog";
import { filterAlerts, staleSummary, isLikelyStale, alertTone } from "../lib/alertsView";
import { useAuth } from "../lib/auth";
import { ReviewBanner, LegacyCloseDialog } from "./LegacyReviewControls";

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
  // Default: current work only. Older open items (operations_currency "review") are one click away, never deleted.
  const [showOlder, setShowOlder] = useState(false);
  const [currency, setCurrency] = useState(null);
  const [closeOne, setCloseOne] = useState(null);
  const { user } = useAuth();
  const isAdmin = ["owner", "admin"].includes(user?.role);

  const status = sp.get("status") || "all";
  const severity = sp.get("severity") || "all";
  const setParam = (k, v) => setSp((p) => { const n = new URLSearchParams(p); v && v !== "all" ? n.set(k, v) : n.delete(k); return n; }, { replace: true });

  const load = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/alerts", { params: { limit: 500 } });
      setAlerts(data);
      if (isAdmin) api.get("/ops/currency").then(({ data: c }) => setCurrency(c)).catch(() => setCurrency(null));
    } catch { toast.error("Could not load alerts"); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); const t = setInterval(load, 15000); return () => clearInterval(t); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const summary = useMemo(() => staleSummary(alerts), [alerts]);
  const all = useMemo(() => filterAlerts(alerts, { status, severity, hideStale: false }), [alerts, status, severity]);
  const rows = useMemo(() => all.filter((a) => (showOlder ? isLikelyStale(a) : !isLikelyStale(a))), [all, showOlder]);

  return (
    <div className="space-y-4" data-testid="alerts-board">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display text-2xl font-medium text-caos-forest">Alerts &amp; assistance events</h2>
          <p className="text-caos-mute text-sm mt-1" data-testid="alerts-counts">{rows.length} shown · {summary.live} current open · {summary.likely_stale} older needing review</p>
          <p className="text-caos-mute text-xs mt-1">
            Pendant / help-button / emergency <strong>assistance events</strong> — not staff task requests
            (those are under <Link to="/admin?tab=requests" className="underline">Communication &amp; requests</Link>).
          </p>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto max-w-full">
          <Link to="/staff" data-testid="alerts-open-live-board" className="shrink-0">
            <Button variant="outline" className="border-2 whitespace-nowrap"><Radio className="w-4 h-4 mr-2" /> Live Staff Dashboard</Button>
          </Link>
          <Button variant="ghost" onClick={load} data-testid="alerts-refresh"><RefreshCw className="w-4 h-4 mr-2" /> Refresh</Button>
        </div>
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
        <div className="flex rounded-full border-2 border-caos-line overflow-hidden text-sm" data-testid="alerts-view-toggle">
          <button className={`px-3 py-1 ${!showOlder ? "bg-caos-forest text-white" : ""}`} onClick={() => setShowOlder(false)} data-testid="alerts-view-current">Current ({summary.live})</button>
          <button className={`px-3 py-1 ${showOlder ? "bg-caos-forest text-white" : ""}`} onClick={() => setShowOlder(true)} data-testid="alerts-view-older">Older, needs review ({summary.likely_stale})</button>
        </div>
      </div>

      {!showOlder && summary.likely_stale > 0 && (
        <div className="flex items-start gap-2 text-xs text-caos-mute bg-[#F3F1EE] rounded-lg p-3" data-testid="alerts-stale-banner">
          <AlertCircle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
          {summary.likely_stale} older open event{summary.likely_stale === 1 ? " is" : "s are"} not shown here (open longer than 72 h, mostly RF/pendant test activity). Use "Older, needs review" to check and close them; nothing is closed automatically.
        </div>
      )}
      {showOlder && <ReviewBanner currency={currency} reviewRows={rows.filter((a) => ["active", "acknowledged"].includes(a.status))} isAdmin={isAdmin} onClosed={load} />}

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
                {stale && <Badge className="bg-caos-mute/20 text-caos-mute text-[10px] uppercase" title={a.currency?.reason || ""}>needs review</Badge>}
                {a.simulated && <Badge variant="outline" className="text-[10px] uppercase">SIM {a.simulation_run_id || ""}</Badge>}
                <span className="text-xs text-caos-mute">{ago(a.created_at)} ago</span>
              </div>
              <div className="font-semibold text-caos-forest mt-1">{a.resident_name || "Unknown resident"}</div>
              <div className="text-xs text-caos-mute">
                {[a.room ? `Room ${a.room}` : null, a.zone, `via ${String(a.triggered_by || "").replace("_", " ")}`,
                  a.acknowledged_by ? `ack by ${a.acknowledged_by}` : (a.status === "active" ? "unacknowledged" : null),
                  a.press_count > 1 ? `${a.press_count} presses` : null].filter(Boolean).join(" · ")}
              </div>
              {stale && a.currency?.reason && <div className="text-xs text-caos-mute mt-0.5">Review: {a.currency.reason}</div>}
              {stale && isAdmin && ["active", "acknowledged"].includes(a.status) && (
                <Button size="sm" variant="outline" className="border-2 h-7 text-xs mt-2" onClick={(e) => { e.stopPropagation(); setCloseOne(a); }} data-testid={`alert-close-legacy-${a.alert_id}`}>Close as reviewed…</Button>
              )}
            </Card>
          );
        })}
      </div>

      <LegacyCloseDialog open={!!closeOne} onOpenChange={(o) => { if (!o) setCloseOne(null); }} kind="alert" ids={closeOne ? [closeOne.alert_id] : []}
        emergency={closeOne?.severity === "emergency"} onDone={load} />
      <AlertDetailDialog alertId={detailId} open={!!detailId} onOpenChange={(o) => { if (!o) setDetailId(null); }} onChanged={load} />
    </div>
  );
}
