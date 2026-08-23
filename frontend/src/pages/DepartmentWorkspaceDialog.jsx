import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import { Loader2, Mail, Clock } from "lucide-react";
import { toast } from "sonner";

// Blueprint section 5: "Each department must be clickable and open a real
// department workspace." First pass, reusing the existing staff_tasks/
// resident-request-bus data via GET /tasks?visibility_role=<slug> - the
// same field routes.py's _notify_department() already treats as "who a
// department's work belongs to" (routes/departments.py, routes/tasks.py).
// No parallel data model - deliberately.
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
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!department) return;
    setLoading(true);
    api.get("/tasks", { params: { visibility_role: department.slug } })
      .then(({ data }) => setTasks(data))
      .catch(() => toast.error("Could not load this department's requests"))
      .finally(() => setLoading(false));
  }, [department]);

  if (!department) return null;

  const open = tasks.filter((t) => OPEN_STATUSES.includes(t.status));
  const counts = tasks.reduce((acc, t) => { acc[t.status] = (acc[t.status] || 0) + 1; return acc; }, {});

  return (
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
                  <div>
                    <div className="font-medium text-sm">{t.title}</div>
                    {(t.resident_name || t.room) && (
                      <div className="text-xs text-caos-mute mt-0.5">
                        {t.resident_name}{t.resident_name && t.room ? " · " : ""}{t.room ? `Room ${t.room}` : ""}
                      </div>
                    )}
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
              </div>
            ))}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
