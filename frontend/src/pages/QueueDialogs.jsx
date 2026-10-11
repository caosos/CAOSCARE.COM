import React, { useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { detailsPayload } from "../lib/appointmentDetails";

// Small dialogs used by the shared department queue (DepartmentQueue.jsx).
// They hold no request state of their own: each hands its values back to the
// queue, which calls the canonical task routes.

// The planned visit window - the SAME two fields the admin/front-desk detail
// dialog saves (requested_for_date / requested_for_time_label), the fields the
// resident's Home screen and Aria's check_request_status read.
export function PlanWindowDialog({ open, onOpenChange, initialDate = "", initialLabel = "", initialDetails = {}, itemName = "request", onSave }) {
  const [date, setDate] = useState(initialDate);
  const [label, setLabel] = useState(initialLabel);
  const [provider, setProvider] = useState(initialDetails.provider_name || "");
  const [discipline, setDiscipline] = useState(initialDetails.discipline || "");
  const [location, setLocation] = useState(initialDetails.location || "");
  useEffect(() => {
    if (open) {
      setDate(initialDate || ""); setLabel(initialLabel || "");
      setProvider(initialDetails.provider_name || ""); setDiscipline(initialDetails.discipline || ""); setLocation(initialDetails.location || "");
    }
  }, [open, initialDate, initialLabel, initialDetails.provider_name, initialDetails.discipline, initialDetails.location]);
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">Plan this {itemName}</DialogTitle></DialogHeader>
        <p className="text-sm text-caos-mute">The resident's screen and Aria show this window. Leave it empty to clear it.</p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div><Label>Date</Label><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} data-testid="wo-plan-date" /></div>
          <div><Label>Time</Label><Input placeholder="e.g. 10:00 AM" value={label} onChange={(e) => setLabel(e.target.value)} data-testid="wo-plan-label" /></div>
          <div><Label>With (optional)</Label><Input placeholder="provider or staff name" maxLength={120} value={provider} onChange={(e) => setProvider(e.target.value)} data-testid="wo-plan-provider" /></div>
          <div><Label>Kind (optional)</Label><Input placeholder="e.g. physical therapy" maxLength={60} value={discipline} onChange={(e) => setDiscipline(e.target.value)} data-testid="wo-plan-discipline" /></div>
          <div className="sm:col-span-2"><Label>Where (optional)</Label><Input placeholder="e.g. Therapy room, 2nd floor" maxLength={160} value={location} onChange={(e) => setLocation(e.target.value)} data-testid="wo-plan-location" /></div>
        </div>
        <DialogFooter>
          <Button onClick={() => onSave({ requested_for_date: date || null, requested_for_time_label: label.trim() || null,
            ...detailsPayload({ provider, discipline, location }) })}
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

// Overlap warning before a plan is kept: staff must choose "Save anyway" explicitly.
export function ConflictDialog({ open, onOpenChange, summary, onSaveAnyway, testId = "wo-conflict" }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" data-testid={`${testId}-dialog`}>
        <DialogHeader><DialogTitle className="font-display">This time overlaps other planned work</DialogTitle></DialogHeader>
        <p className="text-sm text-caos-ink" data-testid={`${testId}-summary`}>{summary}</p>
        <p className="text-sm text-caos-mute">The plan is not saved yet. Pick another time, or save anyway; saving anyway is recorded on the receipt.</p>
        <DialogFooter>
          <Button variant="outline" className="border-2" onClick={() => onOpenChange(false)} data-testid={`${testId}-back`}>Pick another time</Button>
          <Button onClick={onSaveAnyway} className="bg-caos-forest" data-testid={`${testId}-save-anyway`}>Save anyway</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
