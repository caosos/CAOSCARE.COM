import React, { useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";

// Small dialogs used by the shared department queue (DepartmentQueue.jsx).
// They hold no request state of their own: each hands its values back to the
// queue, which calls the canonical task routes.

// The planned visit window - the SAME two fields the admin/front-desk detail
// dialog saves (requested_for_date / requested_for_time_label), the fields the
// resident's Home screen and Aria's check_request_status read.
export function PlanWindowDialog({ open, onOpenChange, initialDate = "", initialLabel = "", itemName = "request", onSave }) {
  const [date, setDate] = useState(initialDate);
  const [label, setLabel] = useState(initialLabel);
  useEffect(() => { if (open) { setDate(initialDate || ""); setLabel(initialLabel || ""); } }, [open, initialDate, initialLabel]);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">Plan this {itemName}</DialogTitle></DialogHeader>
        <p className="text-sm text-caos-mute">The resident's screen and Aria show this window. Leave it empty to clear it.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div><Label>Date</Label><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="wo-plan-date" /></div>
          <div><Label>Time</Label><Input placeholder="e.g. 10:00 AM" value={label} onChange={(e) => setLabel(e.target.value)} data-testid="wo-plan-label" /></div>
        </div>
        <DialogFooter>
          <Button onClick={() => onSave({ requested_for_date: date || null, requested_for_time_label: label.trim() || null })}
            className="bg-caos-forest" data-testid="wo-plan-save">Save plan</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// A required free-text reason (cancel, reopen). Submit stays disabled until typed.
export function ReasonDialog({ open, onOpenChange, title, description, placeholder, submitLabel, testId, onSubmit }) {
  const [text, setText] = useState("");
  useEffect(() => { if (open) setText(""); }, [open]);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">{title}</DialogTitle></DialogHeader>
        {description && <p className="text-sm text-caos-mute">{description}</p>}
        <Textarea placeholder={placeholder} value={text} onChange={(e) => setText(e.target.value)} rows={3} data-testid={`${testId}-reason`} />
        <DialogFooter>
          <Button onClick={() => onSubmit(text.trim())} disabled={!text.trim()} className="bg-caos-forest" data-testid={`${testId}-submit`}>{submitLabel}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
