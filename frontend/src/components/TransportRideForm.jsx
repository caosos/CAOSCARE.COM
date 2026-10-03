import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { toast } from "sonner";
import TransportResourceFields, { resourcePayload } from "./TransportResourceFields";
import { todayLocal } from "../lib/transportation";

// Front desk books a ride for a resident (phone call, walk-up, a family
// note) or changes an existing one. Both go through the authenticated
// /transportation/staff/* endpoints, which reuse the exact booking/change
// logic Aria's resident path uses, and are recorded as the front desk.
//
// ride = null -> new ride; ride = {task_id, requested_for_date,
// requested_for_time_label, purpose, resident_name} -> change that ride.
export default function TransportRideForm({ open, onOpenChange, ride = null, residentId = "", onSaved }) {
  const [residents, setResidents] = useState([]);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);
  const isChange = !!ride;

  useEffect(() => {
    if (!open) return;
    setForm(isChange
      ? { requested_for_date: ride.requested_for_date || todayLocal(), requested_for_time_label: ride.requested_for_time_label || "" }
      : { resident_id: residentId, purpose: "", requested_for_date: todayLocal(), requested_for_time_label: "" });
    if (!isChange) api.get("/residents").then(({ data }) => setResidents(data)).catch(() => setResidents([]));
  }, [open, isChange, ride, residentId]);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    const body = {
      requested_for_date: form.requested_for_date,
      requested_for_time_label: form.requested_for_time_label || null,
      ...resourcePayload(form),
    };
    try {
      const { data } = isChange
        ? await api.post(`/transportation/staff/request/${ride.task_id}/change`, body)
        : await api.post("/transportation/staff/request", { ...body, resident_id: form.resident_id, purpose: form.purpose });
      if (data.duplicate) toast.info("This resident already has an open ride that day — recorded as a re-request.");
      else if (data.booked) toast.success(`Booked — pickup ${data.run.depart_time} on ${data.run.date}${data.shared ? " (shared ride)" : ""}`);
      else toast.success(form.start_time ? "Saved — no free driver/vehicle for that time; it stays in Needs coordination." : "Saved — no pickup time yet; it stays in Needs coordination.");
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save the ride");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="font-display">{isChange ? `Change ride — ${ride.resident_name || ride.purpose}` : "New ride"}</DialogTitle>
        </DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          {!isChange && (
            <>
              <div>
                <Label>Resident</Label>
                <Select value={form.resident_id || ""} onValueChange={(v) => set({ resident_id: v })}>
                  <SelectTrigger data-testid="ride-resident-select"><SelectValue placeholder="Choose a resident" /></SelectTrigger>
                  <SelectContent>
                    {residents.map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Room {r.room}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label>What for</Label>
                <Input required value={form.purpose || ""} placeholder="e.g. doctor appointment"
                  onChange={(e) => set({ purpose: e.target.value })} data-testid="ride-purpose-input" />
              </div>
            </>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label>Date</Label>
              <Input type="date" required value={form.requested_for_date || ""}
                onChange={(e) => set({ requested_for_date: e.target.value })} data-testid="ride-date-input" />
            </div>
            <div>
              <Label>Appointment / time as said</Label>
              <Input value={form.requested_for_time_label || ""} placeholder="e.g. 9:30 appointment"
                onChange={(e) => set({ requested_for_time_label: e.target.value })} data-testid="ride-time-label-input" />
            </div>
          </div>
          <TransportResourceFields value={form} onChange={setForm} />
          <DialogFooter>
            <Button type="submit" disabled={busy || (!isChange && !form.resident_id)} className="bg-caos-forest" data-testid="ride-save-btn">
              {busy ? "Saving…" : isChange ? "Save change" : "Book ride"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
