import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Check, Play } from "lucide-react";
import { api } from "../lib/api";
import { apiErrorText } from "../lib/apiError";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Textarea } from "./ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";
import RequestTimeline from "./RequestTimeline";
import TaskFacts from "./TaskFacts";
import { nextStepText } from "../lib/taskFacts";

const clock = (iso) => (iso ? new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }) : null);
const label = (s) => (s || "").replace(/_/g, " ");
const PRIO = { urgent: "text-[#B42318]", high: "text-[#C2410C]", normal: "text-caos-mute", low: "text-caos-mute" };

// Where the request stands, then what the worker may do next (the shared
// work-rule text, lib/taskFacts.js).
function nextStep(t) {
  const now = t.status === "in_progress" ? `In progress since ${clock(t.started_at) || "unknown"}`
    : t.acknowledged_at ? `Acknowledged ${clock(t.acknowledged_at)}` : "Waiting";
  return `${now} · next: ${nextStepText(t)}`;
}

// Opened on demand: why the request exists, its simulated clock (simulator
// tickets), the worker, notes and every receipt - GET /tasks/{id}/detail.
function MyTaskDetails({ t }) {
  const [detail, setDetail] = useState(null);
  const load = (e) => {
    if (!e.currentTarget.open) return;
    api.get(`/tasks/${t.task_id}/detail`).then(({ data }) => setDetail(data)).catch(() => setDetail({ failed: true }));
  };
  return (
    <details className="mt-1 text-sm" onToggle={load} data-testid={`my-task-details-${t.task_id}`}>
      <summary className="cursor-pointer text-xs font-semibold text-caos-mute">Details, notes and receipts</summary>
      <div className="mt-1 space-y-1">
        {t.description && t.description !== t.title && <div className="break-words">{t.description}</div>}
        <div><span className="text-caos-mute">Worker: </span>{t.assigned_name || "unassigned"}</div>
        <TaskFacts t={t} detail={detail} clock={clock} showNext={false} testid={`my-task-facts-${t.task_id}`} />
        {t.notes && <div className="break-words"><span className="text-caos-mute">Notes: </span>{t.notes}</div>}
        {!detail && <div className="text-caos-mute">Loading…</div>}
        {detail?.failed && <div className="text-caos-terracotta">Could not load the details.</div>}
        {detail?.task && <RequestTimeline task={detail.task} receipts={detail.receipts} />}
      </div>
    </details>
  );
}

// "My tasks today" for a signed-in worker: readable request, resident and
// room, priority, when it was asked (receipt time), status and next action.
export default function MyTasksCard() {
  const [tasks, setTasks] = useState([]);
  const [notesFor, setNotesFor] = useState(null);
  const [notes, setNotes] = useState("");

  const fetchMine = async () => {
    try {
      const { data } = await api.get("/tasks", { params: { mine_only: true } });
      setTasks(data);
    } catch { /* the list keeps its last value; actions report their own errors */ }
  };
  useEffect(() => {
    fetchMine();
    const t = setInterval(fetchMine, 10000);
    return () => clearInterval(t);
  }, []);

  const start = async (id) => {
    try { await api.post(`/tasks/${id}/start`); toast.success("Started"); fetchMine(); }
    catch (err) { toast.error(apiErrorText(err, "Start was refused")); fetchMine(); }
  };
  const complete = async () => {
    if (!notesFor || !notes.trim()) return;
    try {
      await api.post(`/tasks/${notesFor}/complete`, { notes: notes.trim() });
      toast.success("Completed");
      setNotesFor(null);
      setNotes("");
      fetchMine();
    } catch (err) { toast.error(apiErrorText(err, "Completion was refused")); }
  };

  const pending = tasks.filter((t) => t.status !== "completed" && t.status !== "skipped");
  const done = tasks.filter((t) => t.status === "completed" || t.status === "skipped");

  return (
    <Card className="border-caos-line bg-white p-5" data-testid="my-tasks-card">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="font-display text-xl font-medium text-caos-forest">My tasks today</h3>
        <span className="text-xs font-bold uppercase tracking-widest text-caos-mute">{pending.length} open · {done.length} done</span>
      </div>

      <div className="space-y-2" data-testid="my-tasks-list">
        {pending.map((t) => (
          <div key={t.task_id} data-testid={`my-task-${t.task_id}`}
               className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-caos-line p-3 hover:bg-caos-ambient/40">
            <div className="min-w-[14rem] flex-1">
              <div className="break-words font-semibold leading-snug text-caos-forest">{t.title}</div>
              {t.resident_words && <div className="mt-0.5 text-sm text-caos-ink">Resident said: “{t.resident_words}”</div>}
              <div className="mt-1 text-sm text-caos-mute">
                {[t.resident_name, t.room ? `Room ${t.room}` : null, label(t.category)].filter(Boolean).join(" · ")}
                {" · "}<span className={`font-semibold capitalize ${PRIO[t.priority] || PRIO.normal}`}>{t.priority}</span>
                {t.simulated ? " · SIM" : ""}
              </div>
              <div className="mt-0.5 text-xs text-caos-mute">
                Asked {clock(t.created_at)} (receipt time) · {nextStep(t)}
              </div>
              <MyTaskDetails t={t} />
            </div>
            <div className="flex shrink-0 gap-2">
              {t.status === "pending" && (
                <Button size="sm" onClick={() => start(t.task_id)} data-testid={`start-task-${t.task_id}`} className="bg-caos-forest hover:bg-caos-forest-hover">
                  <Play className="mr-1 h-4 w-4" /> Start
                </Button>
              )}
              {t.status === "in_progress" && (
                <Button size="sm" variant="outline" onClick={() => { setNotesFor(t.task_id); setNotes(""); }} data-testid={`complete-task-${t.task_id}`} className="border-2">
                  <Check className="mr-1 h-4 w-4" /> Complete
                </Button>
              )}
            </div>
          </div>
        ))}
        {pending.length === 0 && <div className="py-6 text-center italic text-caos-mute">All caught up.</div>}
      </div>

      {done.length > 0 && (
        <details className="mt-4">
          <summary className="cursor-pointer text-xs font-bold uppercase tracking-widest text-caos-mute">Completed ({done.length})</summary>
          <div className="mt-2 space-y-1 text-sm">
            {done.map((t) => (
              <div key={t.task_id} className="flex justify-between gap-3 text-caos-mute">
                <span>{t.title}{t.notes ? ` — ${t.notes}` : ""}</span>
                <span className="shrink-0">{t.duration_minutes != null ? `${t.duration_minutes}m` : ""}</span>
              </div>
            ))}
          </div>
        </details>
      )}

      <Dialog open={!!notesFor} onOpenChange={(o) => { if (!o) setNotesFor(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle className="font-display">Complete task</DialogTitle></DialogHeader>
          <label className="text-sm text-caos-ink" htmlFor="complete-notes-input">What was done? (required)</label>
          <Textarea id="complete-notes-input" placeholder="For example: helped Mrs. Lee to the bathroom, call light in reach."
                    value={notes} onChange={(e) => setNotes(e.target.value)} data-testid="complete-notes-input" rows={4} />
          <DialogFooter>
            <Button onClick={complete} disabled={!notes.trim()} className="bg-caos-forest" data-testid="complete-submit">Mark complete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
