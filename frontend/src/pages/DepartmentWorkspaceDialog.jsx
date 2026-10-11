import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Textarea } from "../components/ui/textarea";
import { Loader2, Mail } from "lucide-react";
import { toast } from "sonner";
import RequestHistoryDialog from "./RequestHistoryDialog";
import { MembersSection, WorkByWorkerSection, CompletedSection } from "./DepartmentBoardSections";

/**
 * Department workspace (Admin → Departments → a department). Owner review
 * 2026-10-11, P1: members and roles, open work by named worker with its
 * dispatch trail, completed history with receipts; a manager assigns or
 * reassigns, staff act within scope. One read (GET /departments/{slug}/board)
 * over the canonical StaffTask / users / receipts records; every action still
 * goes through the task routes, which authorize and receipt it.
 */
export default function DepartmentWorkspaceDialog({ department, onClose }) {
  const { user } = useAuth();
  const [board, setBoard] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const [completeFor, setCompleteFor] = useState(null);
  const [notes, setNotes] = useState("");
  const [historyFor, setHistoryFor] = useState(null);

  const load = useCallback(() => {
    if (!department) return;
    setLoading(true); setError(null);
    api.get(`/departments/${department.slug}/board`)
      .then(({ data }) => setBoard(data))
      .catch((err) => setError(err?.response?.status === 403 ? "You can see this department's board only if you belong to it or are an administrator." : "Could not load this department's board."))
      .finally(() => setLoading(false));
  }, [department]);
  useEffect(() => { setBoard(null); load(); }, [department, load]);

  if (!department) return null;

  const act = async (id, path, body) => {
    try { await api.post(`/tasks/${id}/${path}`, body); toast.success("Done"); load(); }
    catch (err) { toast.error(err?.response?.data?.detail?.message || err?.response?.data?.detail || "Action failed"); }
  };
  const actions = {
    acknowledge: (id) => act(id, "acknowledge"),
    start: (id) => act(id, "start"),
    assign: (id, uid) => act(id, "assign", { assigned_to: uid || null }),
    complete: (id) => { setCompleteFor(id); setNotes(""); },
  };
  const doComplete = async () => { if (!completeFor) return; await act(completeFor, "complete", { notes }); setCompleteFor(null); setNotes(""); };
  const c = board?.counts;

  return (
    <>
    <Dialog open={!!department} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto" data-testid="dept-workspace-dialog">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            {department.label}
            <Badge variant="outline" className={department.active ? "" : "text-caos-mute"}>{department.active ? "Active" : "Inactive"}</Badge>
          </DialogTitle>
        </DialogHeader>
        <p className="text-caos-mute text-sm">
          Who works here, what each person holds right now, how each request was dispatched, and what was finished.
          Assigning, acknowledging, starting and completing here are the same receipted steps the staff queue uses.
        </p>
        {department.contact_email && <p className="text-sm flex items-center gap-2 text-caos-ink/80"><Mail className="w-3.5 h-3.5 text-caos-mute" /> {department.contact_email}</p>}

        {loading && !board && <div className="py-8 text-center"><Loader2 className="w-6 h-6 animate-spin text-caos-forest mx-auto" /></div>}
        {error && <div className="text-sm text-red-700 mt-2" data-testid="dept-board-error">{error} <Button size="sm" variant="outline" className="ml-2 h-7" onClick={load}>Try again</Button></div>}
        {board && (
          <>
            <div className="flex gap-2 flex-wrap mt-2" data-testid="dept-workspace-counts">
              <Badge variant="outline">{c.open} open</Badge>
              <Badge variant="outline" className={c.unassigned ? "text-caos-terracotta border-caos-terracotta" : "text-caos-mute"}>{c.unassigned} unassigned</Badge>
              <Badge variant="outline" className="text-caos-mute">{c.in_progress} in progress</Badge>
              <Badge variant="outline" className="text-caos-mute">{c.completed_today} completed today</Badge>
            </div>
            <MembersSection members={board.members} />
            <WorkByWorkerSection byWorker={board.by_worker} members={board.members} canAssign={board.can_assign} me={user?.user_id} actions={actions} onHistory={setHistoryFor} />
            <CompletedSection history={board.history} onHistory={setHistoryFor} />
          </>
        )}
      </DialogContent>
    </Dialog>

    <Dialog open={!!completeFor} onOpenChange={(o) => { if (!o) setCompleteFor(null); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">Complete request</DialogTitle></DialogHeader>
        <Textarea placeholder="What was done / outcome (optional)…" value={notes} onChange={(e) => setNotes(e.target.value)} rows={4} data-testid="dept-complete-notes" />
        <DialogFooter><Button onClick={doComplete} className="bg-caos-forest" data-testid="dept-complete-submit">Mark complete</Button></DialogFooter>
      </DialogContent>
    </Dialog>
    <RequestHistoryDialog taskId={historyFor} onClose={() => setHistoryFor(null)} />
    </>
  );
}
