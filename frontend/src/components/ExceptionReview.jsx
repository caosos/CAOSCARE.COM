import React, { useState } from "react";
import { api } from "../lib/api";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { AlertTriangle, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { ReasonDialog } from "../pages/QueueDialogs";

// "Can't complete" and supervisor review for a queued request
// (POST /tasks/{id}/escalate, /review - backend task_review.py).
export function ReviewBadge({ t }) {
  if (!t.needs_review && t.unclaimed_escalated_at && !t.assigned_to) {
    return (
      <div className="text-sm text-caos-terracotta font-semibold" data-testid={`wo-unclaimed-${t.task_id}`}>
        Flagged to a supervisor: nobody claimed it{t.unclaimed_minutes != null ? ` in ${t.unclaimed_minutes} min` : ""}
      </div>
    );
  }
  if (!t.needs_review) return null;
  return (
    <div className="text-sm text-caos-amber font-semibold" data-testid={`wo-needs-review-${t.task_id}`}>
      Needs supervisor review{t.escalated_by_name ? ` (from ${t.escalated_by_name})` : ""}: {t.escalation_reason}
    </div>
  );
}

export function useExceptionReview(reload) {
  const [escalateFor, setEscalateFor] = useState(null);
  const [reviewFor, setReviewFor] = useState(null);
  const send = async (id, path, reason, ok, close) => {
    try {
      await api.post(`/tasks/${id}/${path}`, { reason });
      toast.success(ok);
      close(null);
      reload();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "That didn't go through. Nothing was changed.");
    }
  };
  const buttons = (t, { canAct, isAdmin }) => {
    const open = t.status !== "completed" && t.status !== "skipped";
    return (
      <>
        {open && canAct && !t.needs_review && (
          <Button size="sm" variant="ghost" className="text-caos-amber" onClick={() => setEscalateFor(t.task_id)} data-testid={`wo-escalate-${t.task_id}`}>
            <AlertTriangle className="w-4 h-4 mr-1" /> Can't complete
          </Button>
        )}
        {open && isAdmin && t.needs_review && (
          <Button size="sm" variant="outline" className="border-2" onClick={() => setReviewFor(t.task_id)} data-testid={`wo-review-${t.task_id}`}>
            <ShieldCheck className="w-4 h-4 mr-1" /> Mark reviewed
          </Button>
        )}
      </>
    );
  };
  const dialogs = (
    <>
      <ReasonDialog open={!!escalateFor} onOpenChange={(o) => { if (!o) setEscalateFor(null); }}
        title="Can't complete this request"
        description="Say why. The request stays open, goes back to unassigned, and a supervisor is asked to review it."
        placeholder="e.g. Needs a second person or equipment we don't have" submitLabel="Send to supervisor" testId="wo-escalate"
        onSubmit={(r) => send(escalateFor, "escalate", r, "Sent to a supervisor for review", setEscalateFor)} />
      <ReasonDialog open={!!reviewFor} onOpenChange={(o) => { if (!o) setReviewFor(null); }}
        title="Supervisor review"
        description="Record what you decided. Then assign it to someone, or cancel it with a reason."
        placeholder="e.g. Reassigning to the evening shift with the right equipment" submitLabel="Mark reviewed" testId="wo-review"
        onSubmit={(r) => send(reviewFor, "review", r, "Review recorded", setReviewFor)} />
    </>
  );
  return { buttons, dialogs };
}
