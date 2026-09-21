import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Loader2, Mail, Clock, Hand, Play, Check } from "lucide-react";
import { toast } from "sonner";

// Blueprint section 5: "Each department must be clickable and open a real
// department workspace." First pass, reusing the existing staff_tasks/
// resident-request-bus data via GET /tasks?visibility_role=<slug> - the
// same field routes.py's _notify_department() already treats as "who a
// department's work belongs to" (routes/departments.py, routes/tasks.py).
// No parallel data model - deliberately.
//
// 2026-09-21 (Track 1 Lane 3, audit §8/§11.4): this dialog was read-only
// despite POST /tasks/{id}/{acknowledge,start,complete,assign} already
// existing and already used by MaintenanceWorkspace.jsx - the exact
// pattern mirrored below (same endpoints, same GET /staff/assignable
// roster call, generalized to this department's own slug instead of a
// hardcoded "maintenance"). No new backend lifecycle, no new task states.
const STATUS_STYLES = {
  pending: "bg-caos-mute/10 text-caos-mute",
  in_progress: "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  completed: "bg-caos-moss/15 text-caos-forest border border-caos-moss",
  skipped: "bg-caos-line text-caos-mute line-through",
};
const OPEN_STATUSES = ["pending", "in_progress"];

function ageLabel(iso) {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const hrs = Math.floor(ms / 3_600_000);
  if (hrs < 1) return "just now";
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function DepartmentWorkspaceDialog({ department, onClose }) {
  const { user } = useAuth();
  const [tasks, setTasks] = useState([]);
  const [roster, setRoster] = useState([]);
  const [loading, setLoading] = useState(false);
  const [completeFor, setCompleteFor] = useState(null);
  const [notes, setNotes] = useState("");

  const load = useCallback(() => {
    if (!department) return;
    setLoading(true);
    api.get("/tasks", { params: { visibility_role: department.slug } })
      .then(({ data }) => setTasks(data))
      .catch(() => toast.error("Could not load this department's requests"))
      .finally(() => setLoading(false));
  }, [department]);

  useEffect(() => {
    load();
    if (!department) { setRoster([]); return; }
    api.get("/staff/assignable", { params: { department: department.slug } })
      .then(({ data }) => setRoster(data)).catch(() => setRoster([]));
  }, [department, load]);

  if (!department) return null;

  const act = async (id, path, body) => {
    try {
      await api.post(`/tasks/${id}/${path}`, body);
      toast.success("Done");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Action failed");
    }
  };
  const acknowledge = (id) => act(id, "acknowledge");
  const claim = (id) => act(id, "assign", { assigned_to: user?.user_id });
  const assignTo = (id, uid) => act(id, "assign", { assigned_to: uid || null });
  const start = (id) => act(id, "start");
  const doComplete = async () => {
    if (!completeFor) return;
    await act(completeFor, "complete", { notes });
    setCompleteFor(null);
    setNotes("");
  };

  const open = tasks.filter((t) => OPEN_STATUSES.includes(t.status));
  const counts = tasks.reduce((acc, t) => { acc[t.status] = (acc[t.status] || 0) + 1; return acc; }, {});

  return (
    <>
    <Dialog open={!!department} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" data-testid="dept-workspace-dialog">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            {department.label}
            <Badge variant="outline" className={department.active ? "" : "text-caos-mute"}>
              {department.active ? "Active" : "Inactive"}
            </Badge>
          </DialogTitle>
        </DialogHeader>

        {department.description && <p className="text-caos-mute text-sm">{department.description}</p>}
        {department.contact_email && (
          <p className="text-sm flex items-center gap-2 text-caos-ink/80">
            <Mail className="w-3.5 h-3.5 text-caos-mute" /> {department.contact_email}
          </p>
        )}

        <div className="flex gap-2 flex-wrap mt-2" data-testid="dept-workspace-counts">
          <Badge variant="outline">{open.length} open</Badge>
          <Badge variant="outline" className="text-caos-mute">{counts.completed || 0} completed</Badge>
          <Badge variant="outline" className="text-caos-mute">{counts.skipped || 0} skipped</Badge>
        </div>

        <div className="mt-4">
          <h3 className="text-sm font-semibold text-caos-forest uppercase tracking-wide mb-2">Open requests</h3>
          {loading && <div className="py-8 text-center"><Loader2 className="w-6 h-6 animate-spin text-caos-forest mx-auto" /></div>}
          {!loading && open.length === 0 && (
            <p className="text-caos-mute text-sm italic py-4">Nothing open routed to this department right now.</p>
          )}
          <div className="space-y-2">
            {open.map((t) => (
              <div key={t.task_id} className="border border-caos-line rounded-lg p-3" data-testid={`dept-workspace-task-${t.task_id}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium text-sm">{t.title}</div>
                    {(t.resident_name || t.room) && (
                      <div className="text-xs text-caos-mute mt-0.5">
                        {t.resident_name}{t.resident_name && t.room ? " · " : ""}{t.room ? `Room ${t.room}` : ""}
                      </div>
                    )}
                    <div className="text-xs text-caos-mute mt-0.5">
                      {t.assigned_name ? `→ ${t.assigned_name}` : "unassigned"}
                      {t.acknowledged_by_name ? ` · acknowledged by ${t.acknowledged_by_name}` : ""}
                    </div>
                  </div>
                  <Badge className={STATUS_STYLES[t.status] || ""} variant="outline">{t.status.replace("_", " ")}</Badge>
                </div>
                <div className="flex items-center gap-3 mt-2 text-xs text-caos-mute">
                  <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {ageLabel(t.created_at)}</span>
                  {t.priority && t.priority !== "normal" && (
                    <span className={t.priority === "urgent" ? "text-caos-terracotta font-semibold" : ""}>
                      {t.priority}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {!t.acknowledged_by && (
                    <Button size="sm" variant="outline" className="border-2 h-7 text-xs" onClick={() => acknowledge(t.task_id)} data-testid={`dept-ack-${t.task_id}`}>
                      Acknowledge
                    </Button>
                  )}
                  {!t.assigned_to && (
                    <Button size="sm" variant="outline" className="border-2 h-7 text-xs" onClick={() => claim(t.task_id)} data-testid={`dept-claim-${t.task_id}`}>
                      <Hand className="w-3.5 h-3.5 mr-1" /> Claim
                    </Button>
                  )}
                  {t.status === "pending" && (
                    <Button size="sm" className="bg-caos-forest hover:bg-caos-forest-hover h-7 text-xs" onClick={() => start(t.task_id)} data-testid={`dept-start-${t.task_id}`}>
                      <Play className="w-3.5 h-3.5 mr-1" /> Start
                    </Button>
                  )}
                  <Button size="sm" variant="outline" className="border-2 h-7 text-xs" onClick={() => { setCompleteFor(t.task_id); setNotes(""); }} data-testid={`dept-complete-${t.task_id}`}>
                    <Check className="w-3.5 h-3.5 mr-1" /> Complete
                  </Button>
                </div>
                <div className="mt-2">
                  <Select value={t.assigned_to || "__none"} onValueChange={(v) => assignTo(t.task_id, v === "__none" ? "" : v)}>
                    <SelectTrigger className="h-7 w-48 text-xs" data-testid={`dept-assign-${t.task_id}`}><SelectValue placeholder="Assign to…" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none">Unassigned</SelectItem>
                      {roster.map((u) => <SelectItem key={u.user_id} value={u.user_id}>{u.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>

    <Dialog open={!!completeFor} onOpenChange={(o) => { if (!o) setCompleteFor(null); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">Complete request</DialogTitle></DialogHeader>
        <Textarea placeholder="What was done / outcome (optional)…" value={notes}
          onChange={(e) => setNotes(e.target.value)} rows={4} data-testid="dept-complete-notes" />
        <DialogFooter>
          <Button onClick={doComplete} className="bg-caos-forest" data-testid="dept-complete-submit">Mark complete</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
    </>
  );
}
