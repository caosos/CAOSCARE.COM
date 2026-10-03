import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Checkbox } from "./ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { toast } from "sonner";
import { WEEKDAYS } from "../lib/transportation";

// A driver's regular working days and hours. The booking engine only books
// a driver for a pickup inside these hours. "No hours set" (Clear) means
// unrestricted - shown as such, never guessed.
export default function DriverHoursDialog({ driver, onClose, onSaved }) {
  const [days, setDays] = useState([]);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");

  useEffect(() => {
    if (!driver) return;
    setDays(Array.isArray(driver.work_days) ? driver.work_days : [0, 1, 2, 3, 4]);
    setStart(driver.shift_start || "");
    setEnd(driver.shift_end || "");
  }, [driver]);
  if (!driver) return null;

  const patch = async (body, msg) => {
    try {
      await api.patch(`/transportation/drivers/${driver.driver_id}`, body);
      toast.success(msg);
      onClose();
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save hours");
    }
  };
  const save = () => patch({ work_days: [...days].sort(), shift_start: start || null, shift_end: end || null }, "Hours saved");
  const clear = () => patch({ work_days: null, shift_start: null, shift_end: null }, "Hours cleared");
  const toggle = (n) => setDays((d) => (d.includes(n) ? d.filter((x) => x !== n) : [...d, n]));

  return (
    <Dialog open={!!driver} onOpenChange={(o) => { if (!o) onClose(); }}>
      <DialogContent className="max-w-md">
        <DialogHeader><DialogTitle className="font-display">Working hours — {driver.name}</DialogTitle></DialogHeader>
        <div className="flex flex-wrap gap-3" data-testid="driver-hours-days">
          {WEEKDAYS.map(([n, l]) => (
            <label key={n} className="flex items-center gap-1.5 text-sm">
              <Checkbox checked={days.includes(n)} onCheckedChange={() => toggle(n)} data-testid={`driver-day-${n}`} /> {l}
            </label>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><Label>Shift start</Label><Input type="time" value={start} onChange={(e) => setStart(e.target.value)} data-testid="driver-shift-start" /></div>
          <div><Label>Shift end</Label><Input type="time" value={end} onChange={(e) => setEnd(e.target.value)} data-testid="driver-shift-end" /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={clear} data-testid="driver-hours-clear">No set hours</Button>
          <Button onClick={save} className="bg-caos-forest" data-testid="driver-hours-save">Save</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
