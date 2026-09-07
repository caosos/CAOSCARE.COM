import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { LogOut, RefreshCw, Play, Check, Eye, Bus } from "lucide-react";
import { toast } from "sonner";
import { MyTasksCard } from "./TasksTab";

// One shared operational workspace, rendered per the signed-in staff
// member's Department (User.department -> Department.slug). It reuses the
// existing StaffTask / resident-request bus - GET /tasks is already
// department-scoped server-side for a `staff` role by their User.department
// (routes/tasks.py::list_tasks), so this is that same data, shaped for the
// people who own it. No new task/department model. Care/Nursing and
// unassigned staff are routed to /staff (the resident-assistance board)
// instead of here - see lib/roleHome.js.

const OPEN = ["pending", "in_progress"];
const STATUS_STYLE = {
  pending: "bg-caos-mute/10 text-caos-mute",
  in_progress: "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  completed: "bg-caos-moss/15 text-caos-forest border border-caos-moss",
  skipped: "bg-caos-line text-caos-mute line-through",
};

function ageLabel(iso) {
  if (!iso) return "—";
  const ms = Date.now() - new Date(iso).getTime();
  const h = Math.floor(ms / 3_600_000);
  if (h < 1) return `${Math.max(1, Math.floor(ms / 60_000))}m`;
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

function TransportSummary() {
  const [report, setReport] = useState(null);
  useEffect(() => {
    const today = new Date();
    const d = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
    api.get("/transportation/report", { params: { date: d } })
      .then(({ data }) => setReport(data))
      .catch(() => setReport(null));
  }, []);
  if (!report) return null;
  const s = report.summary;
  return (
    <Card className="border-caos-line p-5" data-testid="workspace-transport-summary">
      <div className="flex items-center gap-2 mb-3">
        <Bus className="w-4 h-4 text-caos-forest" />
        <h3 className="font-display text-lg font-medium text-caos-forest">Today's rides</h3>
      </div>
      <div className="grid grid-cols-3 gap-3 text-center">
        {[["Requests", s.total_requests_received], ["Booked", s.total_booked], ["Unresolved", s.total_unresolved]].map(([l, v]) => (
          <div key={l} className="rounded-xl border border-caos-line p-2">
            <div className="text-xl font-display text-caos-forest">{v}</div>
            <div className="text-[10px] uppercase tracking-wider text-caos-mute">{l}</div>
          </div>
        ))}
      </div>
      {report.current_state?.waiting_unbooked?.length > 0 && (
        <div className="mt-3 text-xs text-caos-mute">
          Waiting on a slot: {report.current_state.waiting_unbooked.map((r) => r.room || r.task_id).join(", ")}
        </div>
      )}
    </Card>
  );
}

export default function DepartmentWorkspace() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [departments, setDepartments] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);

  const dept = user?.department || null;
  const deptLabel = useMemo(() => {
    const d = departments.find((x) => x.slug === dept);
    return d ? d.label : dept;
  }, [departments, dept]);

  const fetchTasks = async () => {
    try {
      const params = dept ? { visibility_role: dept } : {};
      const { data } = await api.get("/tasks", { params });
      setTasks(data);
    } catch {
      toast.error("Could not load the queue");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    api.get("/departments").then(({ data }) => setDepartments(data)).catch(() => {});
  }, []);
  useEffect(() => {
    fetchTasks();
    const t = setInterval(fetchTasks, 15000);
    return () => clearInterval(t);
  }, [dept]); // eslint-disable-line react-hooks/exhaustive-deps

  const act = async (id, action) => {
    try {
      await api.post(`/tasks/${id}/${action}`);
      toast.success(action[0].toUpperCase() + action.slice(1) + (action === "acknowledge" ? "d" : action === "start" ? "ed" : "d"));
      fetchTasks();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const openItems = tasks.filter((t) => OPEN.includes(t.status))
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at)); // oldest first
  const doneItems = tasks.filter((t) => !OPEN.includes(t.status))
    .sort((a, b) => new Date(b.completed_at || b.created_at) - new Date(a.completed_at || a.created_at));

  return (
    <div className="min-h-screen bg-caos-bone">
      <header className="border-b border-caos-line bg-caos-bone sticky top-0 z-30">
        <div className="max-w-6xl mx-auto flex items-center justify-between px-6 py-4">
          <Link to="/" className="text-xl">
            <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
            <span className="font-display font-light text-caos-forest">Care</span>
          </Link>
          <div className="flex items-center gap-3">
            {["owner", "admin"].includes(user?.role) && (
              <Link to="/admin"><Button variant="outline" className="border-2 h-10 rounded-full">Admin</Button></Link>
            )}
            <span className="text-sm text-caos-mute hidden md:block">
              {user?.name}{deptLabel ? ` · ${deptLabel}` : ""}
            </span>
            <Button variant="outline" onClick={async () => { await logout(); nav("/login"); }} className="border-2 h-10 rounded-full" data-testid="workspace-logout-btn">
              <LogOut className="w-4 h-4 mr-2" /> Sign out
            </Button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6 flex-wrap gap-3">
          <h1 className="font-display text-4xl font-light text-caos-forest">
            {deptLabel ? `${deptLabel} workspace` : "Workspace"}
          </h1>
          <Button variant="ghost" onClick={fetchTasks} data-testid="workspace-refresh">
            <RefreshCw className="w-4 h-4 mr-2" /> Refresh
          </Button>
        </div>

        {!dept && (
          <Card className="border-caos-line p-8 text-center" data-testid="workspace-no-dept">
            <p className="font-display text-lg text-caos-forest">No department assigned yet.</p>
            <p className="text-caos-mute mt-1">
              Ask an administrator to set your department, or{" "}
              <Link to="/staff" className="underline">go to the resident-assistance board</Link>.
            </p>
          </Card>
        )}

        {dept && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <section className="lg:col-span-2">
              <div className="flex items-center justify-between mb-3">
                <h2 className="font-display text-2xl font-medium text-caos-forest">
                  Open queue <span className="text-caos-mute text-lg">({openItems.length})</span>
                </h2>
              </div>
              <div className="space-y-2" data-testid="workspace-open-list">
                {!loading && openItems.length === 0 && (
                  <Card className="p-8 text-center border-caos-line text-caos-mute italic">Nothing open right now.</Card>
                )}
                {openItems.map((t) => (
                  <Card key={t.task_id} className="p-4 border-caos-line" data-testid={`workspace-task-${t.task_id}`}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="font-semibold text-caos-forest">{t.title}</div>
                        <div className="text-xs text-caos-mute mt-0.5">
                          {t.category}
                          {(t.resident_name || t.room) && " · "}
                          {t.resident_name}{t.resident_name && t.room ? " · " : ""}{t.room ? `Room ${t.room}` : ""}
                          {" · open "}{ageLabel(t.created_at)}
                          {t.re_request_count > 0 && <span className="text-caos-terracotta"> · asked {t.re_request_count}x</span>}
                        </div>
                        {t.description && t.description !== t.title && (
                          <div className="text-sm text-caos-ink/80 mt-1">{t.description}</div>
                        )}
                        <div className="flex items-center gap-2 mt-2">
                          <Badge className={`uppercase tracking-wider text-[10px] font-bold ${STATUS_STYLE[t.status]}`}>{t.status.replace("_", " ")}</Badge>
                          {t.priority && t.priority !== "normal" && (
                            <Badge variant="outline" className="uppercase text-[10px]">{t.priority}</Badge>
                          )}
                          {t.assigned_name && <span className="text-[11px] text-caos-mute">→ {t.assigned_name}</span>}
                        </div>
                      </div>
                      <div className="flex flex-col gap-1.5 shrink-0">
                        {!t.acknowledged_at && (
                          <Button size="sm" variant="outline" className="border-2" onClick={() => act(t.task_id, "acknowledge")} data-testid={`ws-ack-${t.task_id}`}>
                            <Eye className="w-4 h-4 mr-1" /> Ack
                          </Button>
                        )}
                        {t.status === "pending" && (
                          <Button size="sm" className="bg-caos-forest hover:bg-caos-forest-hover" onClick={() => act(t.task_id, "start")} data-testid={`ws-start-${t.task_id}`}>
                            <Play className="w-4 h-4 mr-1" /> Start
                          </Button>
                        )}
                        <Button size="sm" variant="outline" className="border-2" onClick={() => act(t.task_id, "complete")} data-testid={`ws-done-${t.task_id}`}>
                          <Check className="w-4 h-4 mr-1" /> Done
                        </Button>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>

              {doneItems.length > 0 && (
                <details className="mt-5">
                  <summary className="text-xs font-bold uppercase tracking-widest text-caos-mute cursor-pointer">
                    Recently closed ({doneItems.length})
                  </summary>
                  <div className="mt-2 space-y-1 text-sm">
                    {doneItems.slice(0, 25).map((t) => (
                      <div key={t.task_id} className="flex justify-between text-caos-mute border-b border-caos-line py-1">
                        <span className={t.status === "skipped" ? "line-through" : ""}>{t.title}</span>
                        <span className="text-xs">{t.completed_by_name || ""} · {ageLabel(t.completed_at || t.created_at)} ago</span>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </section>

            <section className="space-y-6">
              {dept === "transportation" && <TransportSummary />}
              <MyTasksCard />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
