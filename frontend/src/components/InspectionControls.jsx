import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Textarea } from "./ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { toast } from "sonner";
export { inspectionText } from "../lib/inspection";

// Owner/admin inspection of completed work (POST /tasks/{id}/inspect,
// backend task_review.py): Pass records it; Return reopens the same request
// for correction with the reason.
export function useInspection(reload) {
  const [forId, setForId] = useState(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const send = async (result) => {
    if (result === "return" && !note.trim()) return;
    setBusy(true);
    try {
      await api.post(`/tasks/${forId}/inspect`, { result, note: note.trim() });
      toast.success(result === "pass" ? "Inspection recorded: passed" : "Returned for correction");
      setForId(null); setNote(""); reload();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "That didn't go through. Nothing was changed.");
    } finally { setBusy(false); }
  };
  const button = (t, isAdmin) => (isAdmin && t.status === "completed" && t.inspection_result !== "passed") ? (
    <Button size="sm" variant="ghost" className="h-6 px-2" onClick={() => { setForId(t.task_id); setNote(""); }} data-testid={`wo-inspect-${t.task_id}`}>Inspect</Button>
  ) : null;
  const dialog = (
    <Dialog open={!!forId} onOpenChange={(o) => { if (!o) setForId(null); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">Inspect completed work</DialogTitle></DialogHeader>
        <p className="text-sm text-caos-mute">Pass records the inspection. Return sends the same request back to the department for correction — say what needs correcting.</p>
        <Textarea placeholder="Note (required to return)" value={note} onChange={(e) => setNote(e.target.value)} rows={3} data-testid="wo-inspect-note" />
        <DialogFooter className="gap-2">
          <Button variant="outline" className="border-2" disabled={busy || !note.trim()} onClick={() => send("return")} data-testid="wo-inspect-return">Return for correction</Button>
          <Button className="bg-caos-forest" disabled={busy} onClick={() => send("pass")} data-testid="wo-inspect-pass">Pass</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
  return { button, dialog };
}
