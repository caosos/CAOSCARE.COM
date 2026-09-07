import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Plus, RefreshCw, Play, Check, Hand, History } from "lucide-react";
import { toast } from "sonner";
import { workOrderBuckets, isOverdue, canClaim, canAssign, ageLabel } from "../lib/maintenance";
import MaintenanceWorkOrderForm from "./MaintenanceWorkOrderForm";

const PRIO_STYLE = {
  urgent: "bg-caos-terracotta text-white",
  high: "bg-caos-amber text-white",
  normal: "border border-caos-line text-caos-mute",
  low: "border border-caos-line text-caos-mute",
};

// Maintenance department workspace. Every "work order" is a StaffTask with
// visibility_role === "maintenance"; this view just buckets and acts on
// that existing data (GET /tasks, POST /tasks/{id}/{assign,start,complete}).
export default function MaintenanceWorkspace({ adminMode = false }) {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [roster, setRoster] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [completeFor, setCompleteFor] = useState(null);
  const [notes, setNotes] = useState("");
  const [historyFor, setHistoryFor] = useState(null);

  const load = useCallback(async () => {
    try {
      const params = adminMode ? { visibility_role: "maintenance" } : {};
      const { data } = await api.get("/tasks", { params });
      setTasks(data);
    } catch {
      toast.error("Could not load work orders");
    } finally {
      setLoading(false);
    }
  }, [adminMode]);

  useEffect(() => {
    load();
    api.get("/staff/assignable", { params: { department: "maintenance" } })
      .then(({ data }) => setRoster(data)).catch(() => setRoster([]));
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load]);

  const b = useMemo(() => workOrderBuckets(tasks, { meId: user?.user_id }), [tasks, user]);

  const act = async (id, path, body) => {
    try {
      await api.post(`/tasks/${id}/${path}`, body);
      toast.success("Done");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Action failed");
    }
  };
  const claim = (id) => act(id, "assign", { assigned_to: user?.user_id });
  const assignTo = (id, uid) => act(id, "assign", { assigned_to: uid || null });
  const start = (id) => act(id, "start");
  const doComplete = async () => {
    if (!completeFor) return;
    await act(completeFor, "complete", { notes });
    setCompleteFor(null);
    setNotes("");
  };

  const showAssign = canAssign(user);

  const Row = ({ t }) => {
    const overdue = isOverdue(t);
    return (
      <Card className="p-3 border-caos-line" data-testid={`wo-${t.task_id}`}>
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={`uppercase text-[10px] font-bold ${PRIO_STYLE[t.priority] || PRIO_STYLE.normal}`}>{t.priority}</Badge>
              <Badge variant="outline" className="uppercase text-[10px]">{t.status.replace("_", " ")}</Badge>
              <span className="text-xs text-caos-mute">opened {ageLabel(t.created_at)} ago</span>
              {t.due_at && (
                <span className={`text-xs ${overdue ? "text-caos-terracotta font-semibold" : "text-caos-mute"}`}>
                  due {new Date(t.due_at).toLocaleDateString()}{overdue ? " · OVERDUE" : ""}
                </span>
              )}
            </div>
            <div className="font-semibold text-caos-forest mt-1 truncate">{t.title}</div>
            {t.description && t.description !== t.title && (
              <div className="text-sm text-caos-ink/80 truncate">{t.description}</div>
            )}
            <div className="text-xs text-caos-mute mt-0.5">
              {[t.room ? `Room ${t.room}` : null, t.resident_name,
                t.assigned_name ? `→ ${t.assigned_name}` : "unassigned"].filter(Boolean).join(" · ")}
            </div>
          </div>
          <div className="flex flex-col gap-1.5 shrink-0">
            {canClaim(t, user) && (
              <Button size="sm" variant="outline" className="border-2" onClick={() => claim(t.task_id)} data-testid={`wo-claim-${t.task_id}`}>
                <Hand className="w-4 h-4 mr-1" /> Claim
              </Button>
            )}
            {t.status === "pending" && (
              <Button size="sm" className="bg-caos-forest hover:bg-caos-forest-hover" onClick={() => start(t.task_id)} data-testid={`wo-start-${t.task_id}`}>
                <Play className="w-4 h-4 mr-1" /> Start
              </Button>
            )}
            {t.status !== "completed" && t.status !== "skipped" && (
              <Button size="sm" variant="outline" className="border-2" onClick={() => { setCompleteFor(t.task_id); setNotes(""); }} data-testid={`wo-complete-${t.task_id}`}>
                <Check className="w-4 h-4 mr-1" /> Complete
              </Button>
            )}
            <Button size="sm" variant="ghost" onClick={() => setHistoryFor(t.task_id)} data-testid={`wo-history-${t.task_id}`}>
              <History className="w-4 h-4 mr-1" /> History
            </Button>
          </div>
        </div>
        {showAssign && t.status !== "completed" && t.status !== "skipped" && (
          <div className="mt-2">
            <Select value={t.assigned_to || "__none"} onValueChange={(v) => assignTo(t.task_id, v === "__none" ? "" : v)}>
              <SelectTrigger className="h-8 w-56 text-xs" data-testid={`wo-assign-${t.task_id}`}><SelectValue placeholder="Assign to…" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="__none">Unassigned</SelectItem>
                {roster.map((u) => <SelectItem key={u.user_id} value={u.user_id}>{u.name}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
        )}
      </Card>
    );
  };

  const Section = ({ title, rows, tone }) => rows.length === 0 ? null : (
    <section data-testid={`wo-section-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <h3 className={`font-display text-lg font-medium mb-2 ${tone === "warn" ? "text-caos-terracotta" : "text-caos-forest"}`}>
        {title} <span className="text-caos-mute text-sm">({rows.length})</span>
      </h3>
      <div className="space-y-2 mb-6">{rows.map((t) => <Row key={t.task_id} t={t} />)}</div>
    </section>
  );

  return (
    <div className="space-y-4" data-testid="maintenance-workspace">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="font-display text-2xl font-medium text-caos-forest">Maintenance work orders</h2>
          {["open", "unassigned", "in_progress", "overdue"].map((k) => (
            <Badge key={k} variant="outline" className="uppercase text-[10px]" data-testid={`wo-count-${k}`}>
              {b.counts[k]} {k.replace("_", " ")}
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={load} data-testid="wo-refresh"><RefreshCw className="w-4 h-4 mr-2" /> Refresh</Button>
          <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" onClick={() => setShowForm(true)} data-testid="wo-new-btn">
            <Plus className="w-4 h-4 mr-2" /> New work order
          </Button>
        </div>
      </div>

      {!loading && b.all.length === 0 && (
        <Card className="p-10 text-center border-caos-line text-caos-mute" data-testid="wo-empty">
          No maintenance work orders yet.
        </Card>
      )}

      <Section title="Overdue" rows={b.overdue} tone="warn" />
      <Section title="Unassigned" rows={b.unassigned} />
      {!adminMode && <Section title="Assigned to me" rows={b.mine} />}
      <Section title="In progress" rows={b.inProgress} />
      {adminMode && <Section title="Assigned, not started" rows={b.assigned} />}

      {b.completed.length > 0 && (
        <details data-testid="wo-completed">
          <summary className="text-xs font-bold uppercase tracking-widest text-caos-mute cursor-pointer">
            Recently completed ({b.completed.length})
          </summary>
          <div className="mt-2 space-y-1 text-sm">
            {b.completed.map((t) => (
              <div key={t.task_id} className="flex justify-between border-b border-caos-line py-1 text-caos-mute">
                <span>{t.title}{t.room ? ` · Rm ${t.room}` : ""}</span>
                <span className="text-xs">{t.completed_by_name || ""} · {ageLabel(t.completed_at)} ago</span>
              </div>
            ))}
          </div>
        </details>
      )}

      <MaintenanceWorkOrderForm open={showForm} onOpenChange={setShowForm} roster={roster} onCreated={load} />

      <Dialog open={!!completeFor} onOpenChange={(o) => { if (!o) setCompleteFor(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle className="font-display">Complete work order</DialogTitle></DialogHeader>
          <Textarea placeholder="What was done / outcome (optional)…" value={notes}
            onChange={(e) => setNotes(e.target.value)} rows={4} data-testid="wo-complete-notes" />
          <DialogFooter>
            <Button onClick={doComplete} className="bg-caos-forest" data-testid="wo-complete-submit">Mark complete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <HistoryDialog taskId={historyFor} onClose={() => setHistoryFor(null)} />
    </div>
  );
}

function HistoryDialog({ taskId, onClose }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!taskId) { setData(null); return; }
    api.get(`/tasks/${taskId}/detail`).then(({ data: d }) => setData(d)).catch(() => setData(null));
  }, [taskId]);
  if (!taskId) return null;
  const events = [];
  if (data?.task) {
    events.push({ at: data.task.created_at, label: "Created" });
    (data.receipts || []).forEach((r) => events.push({ at: r.created_at, label: r.action_type.replace(/_/g, " ") }));
    if (data.task.started_at) events.push({ at: data.task.started_at, label: `Started${data.task.assigned_name ? ` — ${data.task.assigned_name}` : ""}` });
    if (data.task.completed_at) events.push({ at: data.task.completed_at, label: `Completed${data.task.completed_by_name ? ` by ${data.task.completed_by_name}` : ""}` });
  }
  events.sort((a, b) => new Date(a.at || 0) - new Date(b.at || 0));
  return (
    <Dialog open={!!taskId} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-lg" data-testid="wo-history-dialog">
        <DialogHeader><DialogTitle className="font-display">Work order history</DialogTitle></DialogHeader>
        {!data ? <div className="text-caos-mute text-sm">Loading…</div> : (
          <>
            <div className="text-sm font-medium text-caos-forest">{data.task.title}</div>
            {data.task.notes && <div className="text-sm text-caos-ink/80 mt-1">Notes: {data.task.notes}</div>}
            <div className="mt-3 space-y-1 text-sm">
              {events.map((e, i) => (
                <div key={i} className="flex gap-3">
                  <span className="text-xs text-caos-mute w-40 shrink-0">{e.at ? new Date(e.at).toLocaleString() : "—"}</span>
                  <span className="capitalize">{e.label}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
