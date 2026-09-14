import React, { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";
import ConversationSessionDetail from "./ConversationSessionDetail";
import AlertDetailDialog from "./AlertDetailDialog";
import RequestDetailDialog from "./RequestDetailDialog";
import { deriveStatus, sourceLabel, STATUS_BADGE_CLASS, fmtDateTime } from "../lib/requestDisplay";

// Panels for the resident hub (ResidentRecordDialog). Each one is a
// resident-filtered read over an EXISTING collection/endpoint and, where an
// item has its own workflow, opens the SAME dialog the rest of Admin uses -
// AlertDetailDialog for assistance events (close-out lives there),
// RequestDetailDialog for requests. No new data model, no second workflow.

function ago(iso) {
  if (!iso) return "—";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

const OPEN_ALERT = ["active", "acknowledged"];

/* ---------------- Overview ---------------- */
export function OverviewPanel({ resident }) {
  const [brief, setBrief] = useState(null);
  const [stats, setStats] = useState(null);

  useEffect(() => {
    let live = true;
    api.get(`/residents/${resident.resident_id}/briefing`).then(({ data }) => live && setBrief(data)).catch(() => {});
    api.get(`/residents/${resident.resident_id}/stats`).then(({ data }) => live && setStats(data)).catch(() => {});
    return () => { live = false; };
  }, [resident.resident_id]);

  const cur = stats?.current_window;
  return (
    <div className="space-y-4" data-testid="hub-overview">
      <div className="rounded-xl border border-caos-line p-4 text-sm text-caos-ink/90">
        {brief ? brief.narrative : "Loading briefing…"}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
        <Stat n={brief?.active_alerts_24h ?? "—"} label="open alerts 24h" warn={(brief?.active_alerts_24h || 0) > 0} />
        <Stat n={cur ? cur.total_calls : "—"} label={`calls / ${stats?.window_days || 30}d`} />
        <Stat n={cur ? cur.falls_during_call : "—"} label="falls" warn={(cur?.falls_during_call || 0) > 0} />
        <Stat n={cur?.avg_response_s != null ? `${Math.round(cur.avg_response_s / 60)}m` : "—"} label="avg response" />
      </div>
      {brief?.pinned_memories?.length > 0 && (
        <div>
          <div className="text-xs font-bold uppercase tracking-widest text-caos-mute mb-1">Pinned for staff</div>
          <ul className="text-sm list-disc pl-5 space-y-0.5">
            {brief.pinned_memories.map((m, i) => <li key={i}>{m.text}</li>)}
          </ul>
        </div>
      )}
      <p className="text-xs text-caos-mute">
        Last seen {brief?.last_zone ? `in ${brief.last_zone}` : "—"} · full clinical patterns live in Residents &amp; care → Clinician.
      </p>
    </div>
  );
}

function Stat({ n, label, warn }) {
  return (
    <div className="rounded-lg border border-caos-line p-2">
      <div className={`text-xl font-display ${warn ? "text-caos-terracotta" : "text-caos-forest"}`}>{n}</div>
      <div className="text-[10px] uppercase tracking-wider text-caos-mute">{label}</div>
    </div>
  );
}

/* ---------------- Conversations ---------------- */
export function ConversationsPanel({ resident }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    setSelected(null);
    setLoading(true);
    api.get(`/residents/${resident.resident_id}/conversation-sessions`)
      .then(({ data }) => setSessions(data))
      .catch(() => toast.error("Could not load conversations"))
      .finally(() => setLoading(false));
  }, [resident.resident_id]);

  if (selected) {
    return <ConversationSessionDetail residentId={resident.resident_id} sessionId={selected} onBack={() => setSelected(null)} />;
  }
  return (
    <div className="space-y-2" data-testid="hub-conversations">
      {loading && <div className="text-caos-mute text-sm">Loading…</div>}
      {!loading && sessions.length === 0 && <div className="text-caos-mute text-sm">No conversations recorded yet — every Aria voice session in this resident's room will appear here.</div>}
      {sessions.map((s) => (
        <button
          key={s.session_id}
          onClick={() => setSelected(s.session_id)}
          data-testid={`conversation-session-${s.session_id}`}
          className="w-full text-left rounded-xl border border-caos-line p-3 hover:border-caos-forest transition-colors"
        >
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-caos-forest">{fmtDateTime(s.start_at)}</span>
            <div className="flex items-center gap-2">
              {s.is_test && <Badge variant="outline" className="text-[10px] uppercase">Test</Badge>}
              <span className="text-xs text-caos-mute">{s.turn_count} turns · {s.source || "unknown"}</span>
            </div>
          </div>
          <div className="text-sm text-caos-ink mt-1">{s.topic || "(no topic captured)"}</div>
          <div className="text-xs text-caos-mute mt-1">{s.room ? `Room ${s.room}` : "room unknown"}</div>
        </button>
      ))}
    </div>
  );
}

/* ---------------- Assistance events ---------------- */
export function AssistancePanel({ resident }) {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [detailId, setDetailId] = useState(null);

  const load = () => {
    setLoading(true);
    api.get("/alerts", { params: { limit: 500 } })
      .then(({ data }) => setAlerts(data))
      .catch(() => toast.error("Could not load assistance events"))
      .finally(() => setLoading(false));
  };
  useEffect(load, [resident.resident_id]); // eslint-disable-line react-hooks/exhaustive-deps

  const mine = useMemo(
    () => alerts
      .filter((a) => a.resident_id === resident.resident_id || (resident.room && a.room === resident.room))
      .sort((x, y) => new Date(y.created_at || 0) - new Date(x.created_at || 0)),
    [alerts, resident.resident_id, resident.room],
  );
  const open = mine.filter((a) => OPEN_ALERT.includes(a.status));

  return (
    <div className="space-y-2" data-testid="hub-assistance">
      <p className="text-xs text-caos-mute">
        Pendant / help-button / emergency events (not staff task requests). {open.length} open · {mine.length} total.
        Click one to see its timeline and close it out.
      </p>
      {loading && <div className="text-caos-mute text-sm">Loading…</div>}
      {!loading && mine.length === 0 && <div className="text-caos-mute text-sm">No assistance events for this resident.</div>}
      {mine.slice(0, 40).map((a) => (
        <button
          key={a.alert_id}
          onClick={() => setDetailId(a.alert_id)}
          data-testid={`hub-alert-${a.alert_id}`}
          className="w-full text-left rounded-xl border border-caos-line p-3 hover:border-caos-forest transition-colors"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="outline" className="uppercase text-[10px]">{a.severity}</Badge>
            <Badge variant="outline" className="uppercase text-[10px]">{a.status}</Badge>
            {a.press_count > 1 && <span className="text-xs text-caos-mute">{a.press_count} presses</span>}
            <span className="text-xs text-caos-mute">{ago(a.created_at)}</span>
          </div>
          <div className="text-sm text-caos-ink mt-1">
            via {String(a.triggered_by || "").replace("_", " ")}
            {a.outcome ? ` · outcome: ${a.outcome}` : ""}
          </div>
        </button>
      ))}
      <AlertDetailDialog alertId={detailId} open={!!detailId} onOpenChange={(o) => { if (!o) setDetailId(null); }} onChanged={load} />
    </div>
  );
}

/* ---------------- Requests ---------------- */
export function RequestsPanel({ resident }) {
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [taskId, setTaskId] = useState(null);

  const load = () => {
    setLoading(true);
    api.get("/tasks", { params: { resident_id: resident.resident_id } })
      .then(({ data }) => setTasks(data.filter((t) => t.source && t.source !== "staff")))
      .catch(() => toast.error("Could not load requests"))
      .finally(() => setLoading(false));
  };
  useEffect(load, [resident.resident_id]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="space-y-2" data-testid="hub-requests">
      <p className="text-xs text-caos-mute">
        Things this resident (or family / Front Desk) asked staff to do. {tasks.length} total.
      </p>
      {loading && <div className="text-caos-mute text-sm">Loading…</div>}
      {!loading && tasks.length === 0 && <div className="text-caos-mute text-sm">No requests on file for this resident.</div>}
      {tasks.map((t) => {
        const ds = deriveStatus(t);
        return (
          <button
            key={t.task_id}
            onClick={() => setTaskId(t.task_id)}
            data-testid={`hub-request-${t.task_id}`}
            className="w-full text-left rounded-xl border border-caos-line p-3 hover:border-caos-forest transition-colors"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm text-caos-ink truncate">{t.description || t.title}</span>
              <Badge className={STATUS_BADGE_CLASS[ds] || "bg-caos-mute/10 text-caos-mute"}>{ds}</Badge>
            </div>
            <div className="text-xs text-caos-mute mt-1">
              {t.category} · {sourceLabel(t.source)} · {fmtDateTime(t.created_at)}
            </div>
          </button>
        );
      })}
      <RequestDetailDialog taskId={taskId} open={!!taskId} onOpenChange={(o) => { if (!o) setTaskId(null); }} onChange={load} />
    </div>
  );
}

/* ---------------- Device / pendant ---------------- */
export function DevicePanel({ resident }) {
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.get("/rf/fleet/summary")
      .then(({ data }) => setDevices((data.devices || []).filter((d) => d.resident_id === resident.resident_id)))
      .catch(() => toast.error("Could not load device status"))
      .finally(() => setLoading(false));
  }, [resident.resident_id]);

  return (
    <div className="space-y-2" data-testid="hub-device">
      {loading && <div className="text-caos-mute text-sm">Loading…</div>}
      {!loading && devices.length === 0 && (
        <div className="text-caos-mute text-sm">No pendant / RF device paired to this resident. Pair one in Devices → Pendants.</div>
      )}
      {devices.map((d) => (
        <div key={d.rf_device_id} className="rounded-xl border border-caos-line p-3" data-testid={`hub-device-${d.rf_device_id}`}>
          <div className="flex items-center justify-between gap-2">
            <span className="font-semibold text-caos-forest">{d.label || "Pendant"}</span>
            <Badge
              className={`uppercase text-[10px] font-bold border ${
                d.status === "active" ? "border-caos-moss text-caos-forest bg-caos-moss/10"
                  : d.status === "low_battery" ? "border-caos-amber text-[#8B5A20] bg-caos-amber/10"
                  : "border-caos-terracotta text-caos-terracotta bg-caos-terracotta/10"
              }`}
            >
              {String(d.status).replace("_", " ")}
            </Badge>
          </div>
          <div className="text-xs text-caos-mute mt-1">
            last heard {ago(d.last_seen_at)} · {d.press_count || 0} presses total
          </div>
          {d.reason && <div className="text-xs text-caos-terracotta mt-1 font-medium">{d.reason}</div>}
          {!d.reason && <div className="text-xs text-caos-moss mt-1">Reporting normally.</div>}
        </div>
      ))}
    </div>
  );
}
