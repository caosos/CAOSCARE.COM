import { useState } from "react";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "./ui/dialog";

// What moving a request does (#168), mirroring backend/routes/task_work_rules.assignment_kind:
// taking work from someone needs a reason; an in-progress request handed off waits until the
// new holder starts it.
export function assignmentKind(t, uid) {
  const prev = t?.assigned_to || null;
  const next = uid || null;
  if (prev === next) return null;
  if (t?.status === "in_progress") return "handoff";
  if (!prev) return "assign";
  return next ? "reassign" : "release";
}

const COPY = {
  reassign: { title: "Reassign", ask: "Why is it being moved to someone else? (required)" },
  release: { title: "Put back in the queue", ask: "Why is it going back to the queue? (required)" },
  handoff: { title: "Hand off", ask: "Why is it being handed off, and what is left to do? (required)" },
};

// assignTo(id, uid) sends a plain assignment, or first asks for the reason the server requires.
export default function useAssignWithReason(tasks, act) {
  const [pending, setPending] = useState(null);
  const [reason, setReason] = useState("");
  const assignTo = (id, uid) => {
    const kind = assignmentKind((tasks || []).find((t) => t.task_id === id), uid);
    if (!kind) return;
    if (!COPY[kind]) return act(id, "assign", { assigned_to: uid || null });
    setReason("");
    setPending({ id, uid: uid || null, kind });
  };
  const submit = async () => {
    if (!pending || !reason.trim()) return;
    const ok = await act(pending.id, "assign", { assigned_to: pending.uid, reason: reason.trim() });
    if (ok) setPending(null);
  };
  const copy = COPY[pending?.kind] || COPY.reassign;
  const dialog = (
    <Dialog open={!!pending} onOpenChange={(o) => { if (!o) setPending(null); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">{copy.title}</DialogTitle></DialogHeader>
        {pending?.kind === "handoff" && (
          <p className="text-sm text-caos-mute">The request goes back to waiting; whoever has it next starts it again. The reason is kept in its history.</p>
        )}
        <Textarea placeholder={copy.ask} value={reason} onChange={(e) => setReason(e.target.value)} rows={3}
                  data-testid="wo-assign-reason" />
        <DialogFooter>
          <Button onClick={submit} disabled={!reason.trim()} className="bg-caos-forest" data-testid="wo-assign-reason-submit">{copy.title}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
  return { assignTo, dialog };
}
