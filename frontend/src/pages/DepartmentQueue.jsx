import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Plus, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { workOrderBuckets, canAssign, ageLabel, closedLabel } from "../lib/maintenance";
import MaintenanceWorkOrderForm from "./MaintenanceWorkOrderForm";
import RequestHistoryDialog from "./RequestHistoryDialog";
import { PlanWindowDialog, ReasonDialog, ConflictDialog } from "./QueueDialogs";
import { conflictDetail, conflictSummary, overridePayload } from "../lib/scheduleConflict";
import DepartmentDispatchNote from "../components/DepartmentDispatchNote";
import DepartmentRoster from "../components/DepartmentRoster";
import QueueTaskRow from "../components/QueueTaskRow";
import { useWorkContext } from "../lib/workContext";
import { useExceptionReview } from "../components/ExceptionReview";
import { inspectionText, useInspection } from "../components/InspectionControls";

// A department's request queue (Maintenance work orders, Nursing requests,
// ...). Every item is a StaffTask with visibility_role === department; this
// view buckets and acts on that existing data: GET /tasks,
// POST /tasks/{id}/{acknowledge,assign,start,complete}, PATCH notes.
export default function DepartmentQueue({ department, title, itemName = "request", allowCreate = false, adminMode = false, onLoaded }) {
  const { user: principal } = useAuth();
  const workContext = useWorkContext();
  const user = useMemo(
    () => workContext ? { ...principal, role: workContext.acting_role, department: workContext.acting_department } : principal,
    [principal, workContext]
  );
  const [tasks, setTasks] = useState([]);
  const [roster, setRoster] = useState([]);
  const [rosterState, setRosterState] = useState("loading");
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [completing, setCompleting] = useState(false);
  const completingRef = useRef(false);   // synchronous guard: two clicks in the same tick must send one completion
  const [completeFor, setCompleteFor] = useState(null);
  const [notes, setNotes] = useState("");
  const [historyFor, setHistoryFor] = useState(null);
  const [noteFor, setNoteFor] = useState(null);
  const [noteText, setNoteText] = useState("");
  const [reopenFor, setReopenFor] = useState(null);
  const [reopenReason, setReopenReason] = useState("");
  const [planFor, setPlanFor] = useState(null);
  const [conflict, setConflict] = useState(null);   // {fields, summary} awaiting "save anyway"
  const [cancelFor, setCancelFor] = useState(null);
  const [rides, setRides] = useState({});   // task_id -> GET /tasks/{id}/ride view, for requests with a linked ride

  const onLoadedRef = useRef(onLoaded);   // lets a neighbour (Upcoming) refresh when the queue reloads
  onLoadedRef.current = onLoaded;
  const load = useCallback(async () => {
    try {
      const params = adminMode ? { visibility_role: department } : {};
      const { data } = await api.get("/tasks", { params });
      setTasks(data);
      onLoadedRef.current?.();
      const linked = data.filter((t) => t.linked_ride_task_id);
      if (linked.length) {
        const views = await Promise.all(linked.map((t) => api.get(`/tasks/${t.task_id}/ride`).then((r) => [t.task_id, r.data]).catch(() => null)));
        setRides(Object.fromEntries(views.filter(Boolean)));
      } else {
        setRides({});
      }
    } catch {
      toast.error(`Could not load ${title.toLowerCase()}`);
    } finally {
      setLoading(false);
    }
  }, [adminMode, department, title]);

  useEffect(() => {
    load();
    api.get("/staff/assignable", { params: { department } })
      .then(({ data }) => { setRoster(data); setRosterState("ok"); }).catch(() => { setRoster([]); setRosterState("error"); });
    const t = setInterval(load, 20000);
    return () => clearInterval(t);
  }, [load, department]);

  // Older open requests (server: operations_currency "review", opened > 14 days ago) are kept out of the
  // working buckets by default and counted, so current work is not buried; one click shows them.
  const [showOlder, setShowOlder] = useState(false);
  const isOlder = (t) => ["review", "sim_past"].includes(t.currency?.bucket);
  const olderCount = tasks.filter(isOlder).length;
  const visible = useMemo(() => (showOlder ? tasks : tasks.filter((t) => !isOlder(t))), [tasks, showOlder]); // eslint-disable-line react-hooks/exhaustive-deps
  const b = useMemo(() => workOrderBuckets(visible, { meId: user?.user_id, department }), [visible, user, department]);

  const act = async (id, path, body) => {
    try {
      await api.post(`/tasks/${id}/${path}`, body);
      toast.success("Done");
      load();
      return true;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Action failed");
      return false;
    }
  };
  const claim = (id) => act(id, "assign", { assigned_to: user?.user_id });
  const assignTo = (id, uid) => act(id, "assign", { assigned_to: uid || null });
  const start = (id) => act(id, "start");
  const doComplete = async () => {
    if (!completeFor || completingRef.current) return;          // a double click must not send two completions
    completingRef.current = true; setCompleting(true);
    const ok = await act(completeFor, "complete", { notes });
    completingRef.current = false; setCompleting(false);
    if (!ok) return;                                 // keep the dialog and the typed note so the user can retry
    setCompleteFor(null);
    setNotes("");
  };

  const saveNote = async () => {
    if (!noteFor || !noteText.trim()) return;
    try {
      await api.patch(`/tasks/${noteFor}`, { notes: noteText });
      toast.success("Note saved");
      setNoteFor(null);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save the note");
    }
  };
  const canNote = (t) => ["owner", "admin"].includes(user?.role) || t.assigned_to === user?.user_id;
  const isAdmin = ["owner", "admin"].includes(user?.role);
  const canPlan = (t) => isAdmin || showAssign || t.assigned_to === user?.user_id;
  const review = useExceptionReview(load);
  const inspection = useInspection(load);
  // Planned visit window: PATCH /tasks/{id} with the same two fields the detail dialog saves (receipted as task_schedule_updated).
  // Save the plan. An overlap with the resident's other planned work comes back as a
  // 409 (schedule_conflict); staff then choose explicitly to save anyway, which the
  // server records on the receipt. A time the server cannot read is saved, with the
  // honest note that overlap was not checked.
  const savePlan = async (fields) => {
    if (!planFor) return;
    try {
      await api.patch(`/tasks/${planFor}`, fields);
      let note = "";
      if (fields.requested_for_date && fields.requested_for_time_label && !fields.conflict_override) {
        try { const { data } = await api.get(`/tasks/${planFor}/conflicts`); note = conflictSummary(data); } catch { /* the save already happened; no note */ }
      }
      toast.success((fields.requested_for_date || fields.requested_for_time_label || fields.provider_name || fields.location ? "Plan saved — the resident and Aria will see it" : "Plan cleared") + (note ? ` ${note}` : ""));
      setPlanFor(null); setConflict(null);
      load();
    } catch (err) {
      const d = conflictDetail(err);
      if (d) { setConflict({ fields, summary: conflictSummary(d) }); return; }
      toast.error(err?.response?.data?.detail?.message || err?.response?.data?.detail || "Could not save the plan");
    }
  };
  // Ride needed = create-or-attach exactly one transportation request for this planned request.
  const requestRide = async (id) => {
    try {
      const { data } = await api.post(`/tasks/${id}/ride`);
      toast.success(data.already_linked ? "A ride is already on file for this" : data.attached_existing ? "Attached to the resident's existing ride that day" : data.booked ? "Ride requested and booked" : "Ride requested — transportation will book it");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not request a ride");
    }
  };
  // Cancel = the canonical skip with a stated reason (receipted as task_cancelled).
  const cancelRequest = async (reason) => {
    if (!cancelFor) return;
    try {
      await api.post(`/tasks/${cancelFor}/skip`, { notes: reason });
      toast.success("Cancelled");
      setCancelFor(null);
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not cancel the request");
    }
  };
  const reopen = async () => {
    if (!reopenFor || !reopenReason.trim()) return;
    try {
      await api.post(`/tasks/${reopenFor}/reopen`, { reason: reopenReason.trim() });
      toast.success("Reopened");
      setReopenFor(null);
      setReopenReason("");
      load();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not reopen the request");
    }
  };

  const showAssign = canAssign(user, department);

  // Everything a row needs to act (one object; rows are a module-level
  // component, so a parent re-render updates them in place).
  const rowCtx = {
    user, act, claim, start, assignTo, review, isAdmin, canNote, canPlan, showAssign, roster, isOlder, requestRide,
    openComplete: (id) => { setCompleteFor(id); setNotes(""); },
    openNote: (id) => { setNoteFor(id); setNoteText(""); },
    openPlan: (id) => setPlanFor(id),
    openCancel: (id) => setCancelFor(id),
    openHistory: (id) => setHistoryFor(id),
  };
  const renderRow = (t) => <QueueTaskRow t={t} ride={rides[t.task_id]} ctx={rowCtx} />;

  const section = (title, rows, tone) => rows.length === 0 ? null : (
    <section data-testid={`wo-section-${title.replace(/\s+/g, "-").toLowerCase()}`}>
      <h3 className={`font-display text-lg font-medium mb-2 ${tone === "warn" ? "text-caos-terracotta" : "text-caos-forest"}`}>
        {title} <span className="text-caos-mute text-sm">({rows.length})</span>
      </h3>
      <div className="mb-6 divide-y divide-caos-line overflow-hidden rounded-xl border border-caos-line">
        {rows.map((t) => <React.Fragment key={t.task_id}>{renderRow(t)}</React.Fragment>)}
      </div>
    </section>
  );

  return (
    <div className="space-y-4" data-testid={`${department}-queue`}>
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="font-display text-2xl font-medium text-caos-forest">{title}</h2>
          {["open", "unassigned", "in_progress", "overdue"].map((k) => (
            <Badge key={k} variant="outline" className="uppercase text-[10px]" data-testid={`wo-count-${k}`}>
              {b.counts[k]} {k.replace("_", " ")}
            </Badge>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={load} data-testid="wo-refresh"><RefreshCw className="w-4 h-4 mr-2" /> Refresh</Button>
          {allowCreate && (
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" onClick={() => setShowForm(true)} data-testid="wo-new-btn">
              <Plus className="w-4 h-4 mr-2" /> New {itemName}
            </Button>
          )}
        </div>
      </div>

      {adminMode && <DepartmentDispatchNote label={title.replace(/ requests$/i, "")} roster={roster} rosterState={rosterState} />}
      <DepartmentRoster department={department} label={title.replace(/ requests$/i, "")} refreshKey={tasks.length} />

      {olderCount > 0 && (
        <div className="text-xs text-caos-mute bg-[#F3F1EE] rounded-lg p-3 flex flex-wrap items-center gap-2" data-testid="wo-older-banner">
          {showOlder
            ? <>Showing {olderCount} older open request{olderCount === 1 ? "" : "s"} too (opened more than 14 days ago; marked "needs review").</>
            : <>{olderCount} older open request{olderCount === 1 ? " is" : "s are"} hidden (opened more than 14 days ago, mostly test or mock residents). Nothing was closed.</>}
          <Button size="sm" variant="outline" className="border-2 h-7" onClick={() => setShowOlder((v) => !v)} data-testid="wo-older-toggle">{showOlder ? "Hide older" : "Show older"}</Button>
        </div>
      )}

      {!loading && b.all.length === 0 && (
        <Card className="p-10 text-center border-caos-line text-caos-mute" data-testid="wo-empty">
          No open {title.toLowerCase()}.
        </Card>
      )}

      {section("Overdue", b.overdue, "warn")}
      {section("Unassigned", b.unassigned)}
      {!adminMode && section("Assigned to me", b.mine)}
      {section("In progress", b.inProgress)}
      {adminMode && section("Assigned, not started", b.assigned)}

      {b.closed.length > 0 && (
        <details data-testid="wo-completed" open={adminMode}>
          <summary className="text-xs font-bold uppercase tracking-widest text-caos-mute cursor-pointer">
            Recently closed ({b.closed.length})
          </summary>
          <div className="mt-2 space-y-1 text-sm">
            {b.closed.map((t) => (
              <div key={t.task_id} className="border-b border-caos-line py-1.5" data-testid={`wo-closed-${t.task_id}`}>
                <div className="flex flex-wrap justify-between gap-2">
                  <span className="text-caos-ink">{t.title}{t.room ? ` · Rm ${t.room}` : ""}</span>
                  <span className="text-xs flex items-center gap-2 text-caos-mute">
                    <span className={t.status === "skipped" ? "text-caos-terracotta" : ""}>{closedLabel(t)}</span> · {ageLabel(t.completed_at)}
                    {(showAssign || isAdmin) && (
                      <Button size="sm" variant="ghost" className="h-6 px-2" onClick={() => { setReopenFor(t.task_id); setReopenReason(""); }} data-testid={`wo-reopen-${t.task_id}`}>Reopen</Button>
                    )}
                    {inspection.button(t, isAdmin)}
                    <Button size="sm" variant="ghost" className="h-6 px-2" onClick={() => setHistoryFor(t.task_id)} data-testid={`wo-history-${t.task_id}`}>History</Button>
                  </span>
                </div>
                {t.notes && <div className="text-xs text-caos-mute mt-0.5" data-testid={`wo-closed-note-${t.task_id}`}>Note: {t.notes}</div>}
                {inspectionText(t) && <div className="text-xs text-caos-forest mt-0.5" data-testid={`wo-inspection-${t.task_id}`}>{inspectionText(t)}</div>}
              </div>
            ))}
          </div>
        </details>
      )}

      {allowCreate && <MaintenanceWorkOrderForm open={showForm} onOpenChange={setShowForm} roster={roster} onCreated={load} />}

      <Dialog open={!!completeFor} onOpenChange={(o) => { if (!o) setCompleteFor(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle className="font-display">Complete {itemName}</DialogTitle></DialogHeader>
          <p className="text-sm text-caos-mute" data-testid="wo-complete-visibility">The resident sees this text on their screen and Aria may read it to them.</p>
          <Textarea placeholder="What was done / outcome (optional)…" value={notes}
            onChange={(e) => setNotes(e.target.value)} rows={4} data-testid="wo-complete-notes" />
          <DialogFooter>
            <Button onClick={doComplete} disabled={completing} className="bg-caos-forest" data-testid="wo-complete-submit">Mark complete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!noteFor} onOpenChange={(o) => { if (!o) setNoteFor(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle className="font-display">Add a note</DialogTitle></DialogHeader>
          <p className="text-sm text-caos-mute">The resident can hear the latest note when they ask Aria about the request. Earlier notes stay in History.</p>
          <Textarea value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={4} data-testid="wo-note-text" />
          <DialogFooter>
            <Button onClick={saveNote} disabled={!noteText.trim()} className="bg-caos-forest" data-testid="wo-note-save">Save note</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={!!reopenFor} onOpenChange={(o) => { if (!o) setReopenFor(null); }}>
        <DialogContent className="max-w-md">
          <DialogHeader><DialogTitle className="font-display">Reopen {itemName}</DialogTitle></DialogHeader>
          <p className="text-sm text-caos-mute">The request goes back to the queue with its assignee kept. The reason is recorded in its history. The resident sees this text on their screen and Aria may read it to them.</p>
          <Textarea placeholder="Why is this being reopened? (required)" value={reopenReason}
            onChange={(e) => setReopenReason(e.target.value)} rows={3} data-testid="wo-reopen-reason" />
          <DialogFooter>
            <Button onClick={reopen} disabled={!reopenReason.trim()} className="bg-caos-forest" data-testid="wo-reopen-submit">Reopen</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PlanWindowDialog open={!!planFor} onOpenChange={(o) => { if (!o) setPlanFor(null); }} itemName={itemName}
        initialDate={tasks.find((t) => t.task_id === planFor)?.requested_for_date || ""}
        initialLabel={tasks.find((t) => t.task_id === planFor)?.requested_for_time_label || ""}
        initialDetails={tasks.find((t) => t.task_id === planFor) || {}} onSave={savePlan} />
      <ConflictDialog open={!!conflict} onOpenChange={(o) => { if (!o) setConflict(null); }} summary={conflict?.summary}
        onSaveAnyway={() => savePlan(overridePayload(conflict.fields))} />
      {review.dialogs}
      {inspection.dialog}
      <ReasonDialog open={!!cancelFor} onOpenChange={(o) => { if (!o) setCancelFor(null); }} title={`Cancel ${itemName}`}
        description="The request is closed as cancelled; the reason is recorded in its history and receipts. The resident sees this text on their screen and Aria may read it to them." placeholder="Why is it cancelled? (required)"
        submitLabel="Cancel request" testId="wo-cancel" onSubmit={cancelRequest} />

      <RequestHistoryDialog taskId={historyFor} onClose={() => setHistoryFor(null)} />
    </div>
  );
}
