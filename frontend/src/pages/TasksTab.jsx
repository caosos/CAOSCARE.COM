import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../components/ui/tabs";
import { Plus, Trash2, Play, Check, Repeat } from "lucide-react";
import { toast } from "sonner";
import { CATEGORIES, SHIFTS } from "../lib/taskConstants";
import TaskTemplatesBoard from "./TaskTemplatesBoard";

// Facility-local (browser wall-clock) YYYY-MM-DD - matches how a real
// front-desk laptop physically in the building experiences "today,"
// consistent with the same local-date convention used elsewhere in Admin
// rather than a UTC-derived date that can read as tomorrow/yesterday near
// midnight. tasks.py's day= filter already exists (list_tasks) - this is
// the "smallest existing-pattern equivalent" wiring, no new backend filter.
function localTodayISO() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

const STATUS_STYLES = {
  pending: "bg-caos-mute/10 text-caos-mute",
  in_progress: "bg-caos-amber/15 text-[#8B5A20] border border-caos-amber",
  completed: "bg-caos-moss/15 text-caos-forest border border-caos-moss",
  skipped: "bg-caos-line text-caos-mute line-through",
};

function fmtTime(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch { return iso; }
}

export default function TasksTab({ residents, staff }) {
  const [tab, setTab] = useState("today");
  const [tasks, setTasks] = useState([]);
  const [templates, setTemplates] = useState([]);
  // Default true: the tab is literally labeled "Today" - it must actually
  // mean that. "Show all" stays one click away rather than removing older/
  // undated tasks from view entirely (audit §6#4/§8: the day= filter
  // already existed and was simply never passed).
  const [todayOnly, setTodayOnly] = useState(true);

  const fetchAll = async () => {
    try {
      const [t, tpl] = await Promise.all([
        api.get("/tasks", { params: todayOnly ? { day: localTodayISO() } : {} }),
        api.get("/tasks/templates/all"),
      ]);
      setTasks(t.data);
      setTemplates(tpl.data);
    } catch {
      toast.error("Could not load tasks");
    }
  };
  useEffect(() => { fetchAll(); }, [todayOnly]); // eslint-disable-line react-hooks/exhaustive-deps

  const spawnToday = async () => {
    try {
      const { data } = await api.post("/tasks/spawn-today");
      toast.success(`Spawned ${data.created} task${data.created === 1 ? "" : "s"} for today`);
      fetchAll();
    } catch { toast.error("Could not spawn today's tasks"); }
  };

  return (
    <Card className="border-caos-line p-6" data-testid="tasks-tab-root">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Staff tasks</h2>
          <p className="text-caos-mute text-sm mt-1">
            Daily workflow. Templates spawn real tasks each morning. Staff tap Start → Complete. Every move is logged.
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            onClick={() => setTodayOnly((v) => !v)}
            variant="outline"
            className="border-2 rounded-full"
            data-testid="tasks-today-toggle"
          >
            {todayOnly ? "Show all" : "Today only"}
          </Button>
          <Button onClick={spawnToday} variant="outline" className="border-2 rounded-full" data-testid="tasks-spawn-today-btn">
            <Repeat className="w-4 h-4 mr-2" /> Spawn today's tasks
          </Button>
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="today" data-testid="tasks-subtab-today">
            {todayOnly ? "Today" : "All"} ({tasks.length})
          </TabsTrigger>
          <TabsTrigger value="templates" data-testid="tasks-subtab-templates">Templates ({templates.length})</TabsTrigger>
        </TabsList>

        <TabsContent value="today" className="mt-4">
          <TasksBoard tasks={tasks} residents={residents} staff={staff} onChange={fetchAll} todayOnly={todayOnly} />
        </TabsContent>
        <TabsContent value="templates" className="mt-4">
          <TaskTemplatesBoard templates={templates} residents={residents} onChange={fetchAll} />
        </TabsContent>
      </Tabs>
    </Card>
  );
}

function TasksBoard({ tasks, residents, staff, onChange, todayOnly }) {
  const [open, setOpen] = useState(false);
  const empty = { title: "", description: "", category: "other", shift: "any", assigned_to: "", resident_id: "", notes: "" };
  const [form, setForm] = useState(empty);

  const create = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form };
      if (!payload.assigned_to) delete payload.assigned_to;
      if (!payload.resident_id) delete payload.resident_id;
      await api.post("/tasks", payload);
      toast.success("Task created");
      setOpen(false);
      setForm(empty);
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this task?")) return;
    await api.delete(`/tasks/${id}`);
    toast.success("Deleted");
    onChange();
  };

  return (
    <div>
      <div className="flex justify-end mb-3">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-task-btn">
              <Plus className="w-4 h-4 mr-2" /> New task
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-display">New one-off task</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-3">
              <div><Label>Title</Label><Input required data-testid="task-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
              <div><Label>Description</Label><Textarea data-testid="task-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Category</Label>
                  <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                    <SelectTrigger data-testid="task-cat"><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Shift</Label>
                  <Select value={form.shift} onValueChange={(v) => setForm({ ...form, shift: v })}>
                    <SelectTrigger data-testid="task-shift"><SelectValue /></SelectTrigger>
                    <SelectContent>{SHIFTS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Assign to</Label>
                  <Select value={form.assigned_to || "__none"} onValueChange={(v) => setForm({ ...form, assigned_to: v === "__none" ? "" : v })}>
                    <SelectTrigger data-testid="task-assignee"><SelectValue placeholder="Unassigned" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none">Unassigned</SelectItem>
                      {(staff || []).map((s) => <SelectItem key={s.user_id} value={s.user_id}>{s.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Resident (optional)</Label>
                  <Select value={form.resident_id || "__none"} onValueChange={(v) => setForm({ ...form, resident_id: v === "__none" ? "" : v })}>
                    <SelectTrigger data-testid="task-resident"><SelectValue placeholder="None" /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none">None</SelectItem>
                      {(residents || []).map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Rm {r.room}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="task-save">Create</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Status</TableHead><TableHead>Task</TableHead><TableHead>Shift</TableHead>
            <TableHead>Assigned</TableHead><TableHead>Started</TableHead><TableHead>Completed</TableHead>
            <TableHead>Dur.</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {tasks.map((t) => (
            <TableRow key={t.task_id} data-testid={`task-row-${t.task_id}`}>
              <TableCell>
                <Badge className={`uppercase tracking-wider text-[10px] font-bold ${STATUS_STYLES[t.status]}`}>{t.status.replace("_", " ")}</Badge>
              </TableCell>
              <TableCell>
                <div className="font-medium">{t.title}</div>
                <div className="text-caos-mute text-xs">{t.category} {t.resident_name && `· ${t.resident_name}`}</div>
              </TableCell>
              <TableCell className="text-xs uppercase tracking-wider">{t.shift}</TableCell>
              <TableCell className="text-sm">{t.assigned_name || <span className="text-caos-mute italic">unassigned</span>}</TableCell>
              <TableCell className="text-xs text-caos-mute">{fmtTime(t.started_at)}</TableCell>
              <TableCell className="text-xs text-caos-mute">
                {fmtTime(t.completed_at)}
                {t.completed_by_name && <div className="text-[11px]">by {t.completed_by_name}</div>}
              </TableCell>
              <TableCell className="text-sm tabular-nums">{t.duration_minutes != null ? `${t.duration_minutes}m` : "—"}</TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(t.task_id)} data-testid={`del-task-${t.task_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {tasks.length === 0 && (
            <TableRow><TableCell colSpan={8} className="text-center text-caos-mute py-6">
              {todayOnly ? 'No tasks today. Click "Spawn today\'s tasks", or "Show all" to see older/undated tasks.' : "No tasks."}
            </TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}

// Exported for StaffDashboard
export function MyTasksCard() {
  const [tasks, setTasks] = useState([]);
  const [notesFor, setNotesFor] = useState(null);
  const [notes, setNotes] = useState("");

  const fetchMine = async () => {
    try {
      const { data } = await api.get("/tasks", { params: { mine_only: true } });
      setTasks(data);
    } catch { /* silent */ }
  };
  useEffect(() => {
    fetchMine();
    const t = setInterval(fetchMine, 10000);
    return () => clearInterval(t);
  }, []);

  const start = async (id) => {
    try { await api.post(`/tasks/${id}/start`); toast.success("Started"); fetchMine(); }
    catch { toast.error("Could not start"); }
  };
  const complete = async () => {
    if (!notesFor) return;
    try {
      await api.post(`/tasks/${notesFor}/complete`, { notes });
      toast.success("Completed");
      setNotesFor(null);
      setNotes("");
      fetchMine();
    } catch { toast.error("Could not complete"); }
  };

  const pending = tasks.filter((t) => t.status !== "completed" && t.status !== "skipped");
  const done = tasks.filter((t) => t.status === "completed" || t.status === "skipped");

  return (
    <Card className="border-caos-line bg-white p-5" data-testid="my-tasks-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-display text-xl font-medium text-caos-forest">My tasks today</h3>
        <span className="text-xs font-bold uppercase tracking-widest text-caos-mute">{pending.length} open · {done.length} done</span>
      </div>

      <div className="space-y-2" data-testid="my-tasks-list">
        {pending.map((t) => (
          <div key={t.task_id} data-testid={`my-task-${t.task_id}`} className="flex items-center justify-between p-3 rounded-xl border border-caos-line hover:bg-caos-ambient/40">
            <div className="min-w-0">
              <div className="font-semibold text-caos-forest truncate">{t.title}</div>
              <div className="text-xs text-caos-mute uppercase tracking-wider">
                {t.category} · {t.shift} {t.resident_name && `· ${t.resident_name}`}
                {t.status === "in_progress" && <span className="ml-2 text-caos-amber">● in progress</span>}
              </div>
            </div>
            <div className="flex gap-2 shrink-0">
              {t.status === "pending" && (
                <Button size="sm" onClick={() => start(t.task_id)} data-testid={`start-task-${t.task_id}`} className="bg-caos-forest hover:bg-caos-forest-hover">
                  <Play className="w-4 h-4 mr-1" /> Start
                </Button>
              )}
              <Button size="sm" variant="outline" onClick={() => { setNotesFor(t.task_id); setNotes(""); }} data-testid={`complete-task-${t.task_id}`} className="border-2">
                <Check className="w-4 h-4 mr-1" /> Complete
              </Button>
            </div>
          </div>
        ))}
        {pending.length === 0 && (
          <div className="text-center text-caos-mute py-6 italic">All caught up.</div>
        )}
      </div>

      {done.length > 0 && (
        <details className="mt-4">
          <summary className="text-xs font-bold uppercase tracking-widest text-caos-mute cursor-pointer">Completed ({done.length})</summary>
          <div className="mt-2 space-y-1 text-sm">
            {done.map((t) => (
              <div key={t.task_id} className="flex justify-between text-caos-mute">
                <span className="line-through">{t.title}</span>
                <span>{t.duration_minutes != null ? `${t.duration_minutes}m` : ""}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      <Dialog open={!!notesFor} onOpenChange={(o) => { if (!o) setNotesFor(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle className="font-display">Complete task</DialogTitle></DialogHeader>
          <Textarea
            placeholder="Notes (optional)…"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            data-testid="complete-notes-input"
            rows={4}
          />
          <DialogFooter>
            <Button onClick={complete} className="bg-caos-forest" data-testid="complete-submit">Mark complete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
