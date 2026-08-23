import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Textarea } from "../components/ui/textarea";
import { DoorOpen } from "lucide-react";
import { toast } from "sonner";

// Add/Edit resident - split out of ResidentsTab.jsx to keep both under the
// 300-line cap. Owns its own form state, initialized from `resident` (null
// for a new one). Surfaces the room's real kiosk status inline (Terminal 9
// "click the resident, I'm in the room" - a resident record must not be a
// dead end) and can provision the logical kiosk via the same POST /kiosks
// Admin -> Kiosks' own "Add kiosk" already uses - no separate system.

const EMPTY_THRESHOLDS = { hr_resting_min: "", hr_resting_max: "", hr_exertion_max: "", spo2_min: "", inactivity_minutes: "", notes: "" };
const EMPTY_FORM = { name: "", preferred_name: "", room: "", pendant_id: "", medical_notes: "", emergency_contact: "", preferences: "", memory: "", participation_level: "pendant_enhanced", clinical_thresholds: { ...EMPTY_THRESHOLDS } };

export default function ResidentFormDialog({ open, onOpenChange, resident, kiosks, onSaved }) {
  const [form, setForm] = useState(EMPTY_FORM);
  const [settingUpRoom, setSettingUpRoom] = useState(null);

  useEffect(() => {
    if (!open) return;
    if (resident) {
      const ct = resident.clinical_thresholds || {};
      setForm({
        name: resident.name || "",
        preferred_name: resident.preferred_name || "",
        room: resident.room || "",
        pendant_id: resident.pendant_id || "",
        medical_notes: resident.medical_notes || "",
        emergency_contact: resident.emergency_contact || "",
        preferences: resident.preferences || "",
        memory: resident.memory || "",
        participation_level: resident.participation_level || "pendant_enhanced",
        clinical_thresholds: {
          hr_resting_min: ct.hr_resting_min ?? "",
          hr_resting_max: ct.hr_resting_max ?? "",
          hr_exertion_max: ct.hr_exertion_max ?? "",
          spo2_min: ct.spo2_min ?? "",
          inactivity_minutes: ct.inactivity_minutes ?? "",
          notes: ct.notes || "",
        },
      });
    } else {
      setForm(EMPTY_FORM);
    }
  }, [open, resident]);

  const kioskForRoom = (room) => (kiosks || []).find((k) => k.room === room);
  const setUpRoom = async (room) => {
    if (!room || settingUpRoom) return;
    setSettingUpRoom(room);
    try {
      await api.post("/kiosks", { name: room, room, zone: "" });
      toast.success(`Room ${room} is set up — Enter room is now available.`);
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not set up the room");
    } finally {
      setSettingUpRoom(null);
    }
  };

  const save = async (e) => {
    e.preventDefault();
    try {
      // Normalize thresholds: blank strings → null; numbers → int; drop empty
      const ct = form.clinical_thresholds || {};
      const toNumOrNull = (v) => (v === "" || v === null || v === undefined ? null : Number(v));
      const normalized = {
        hr_resting_min: toNumOrNull(ct.hr_resting_min),
        hr_resting_max: toNumOrNull(ct.hr_resting_max),
        hr_exertion_max: toNumOrNull(ct.hr_exertion_max),
        spo2_min: toNumOrNull(ct.spo2_min),
        inactivity_minutes: toNumOrNull(ct.inactivity_minutes),
        notes: ct.notes || "",
      };
      const anySet = Object.entries(normalized).some(([k, v]) => k !== "notes" ? v !== null : !!v);
      const payload = { ...form, clinical_thresholds: anySet ? normalized : null };
      if (resident) {
        await api.put(`/residents/${resident.resident_id}`, payload);
        toast.success("Updated");
      } else {
        await api.post("/residents", payload);
        toast.success("Resident added");
      }
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display">{resident ? "Edit resident" : "New resident"}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Full name</Label><Input required data-testid="res-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
            <div><Label>Preferred name (used by AI)</Label><Input data-testid="res-preferred" value={form.preferred_name} onChange={(e) => setForm({ ...form, preferred_name: e.target.value })} placeholder="Maggie" /></div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Room</Label><Input required data-testid="res-room" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} /></div>
            <div><Label>Pendant ID</Label><Input required data-testid="res-pendant" value={form.pendant_id} onChange={(e) => setForm({ ...form, pendant_id: e.target.value })} /></div>
          </div>
          {form.room.trim() && (
            kioskForRoom(form.room) ? (
              <div className="rounded-xl border border-caos-line bg-caos-ambient/40 p-3 text-sm flex items-center justify-between" data-testid="res-kiosk-status-mapped">
                <span>Room <strong>{form.room}</strong> has a kiosk: <span className="font-mono text-xs">{kioskForRoom(form.room).kiosk_id}</span></span>
                <DoorOpen className="w-4 h-4 text-caos-forest" />
              </div>
            ) : (
              <div className="rounded-xl border-2 border-caos-terracotta bg-caos-terracotta/5 p-3 text-sm flex items-center justify-between gap-3" data-testid="res-kiosk-status-unmapped">
                <span>Room <strong>{form.room}</strong> has no kiosk yet — this resident won't have a usable Enter Room until one exists.</span>
                <Button type="button" size="sm" variant="outline" className="border-2 border-caos-terracotta text-caos-terracotta shrink-0"
                  disabled={settingUpRoom === form.room} onClick={() => setUpRoom(form.room)} data-testid="res-setup-room-btn">
                  {settingUpRoom === form.room ? "Setting up…" : "Set up room"}
                </Button>
              </div>
            )
          )}
          <div>
            <Label>Participation level</Label>
            <Select value={form.participation_level} onValueChange={(v) => setForm({ ...form, participation_level: v })}>
              <SelectTrigger data-testid="res-participation"><SelectValue /></SelectTrigger>
              <SelectContent>
                <SelectItem value="room_only">Room only</SelectItem>
                <SelectItem value="pendant_enhanced">Pendant enhanced</SelectItem>
                <SelectItem value="wearable_enhanced">Wearable enhanced</SelectItem>
                <SelectItem value="family_connected">Family connected</SelectItem>
                <SelectItem value="full">Full (all layers)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div><Label>Emergency contact</Label><Input data-testid="res-contact" value={form.emergency_contact} onChange={(e) => setForm({ ...form, emergency_contact: e.target.value })} /></div>
          <div><Label>Medical notes</Label><Textarea data-testid="res-notes" value={form.medical_notes} onChange={(e) => setForm({ ...form, medical_notes: e.target.value })} /></div>
          <div>
            <Label>Comfort topics they love <span className="text-caos-mute text-xs">(AI personalizes chat)</span></Label>
            <Textarea data-testid="res-preferences" value={form.preferences} onChange={(e) => setForm({ ...form, preferences: e.target.value })} placeholder="Piano hymns, her grandkids Liam & Aoife, rainy days…" />
          </div>
          <div>
            <Label>Things CAOS should remember <span className="text-caos-mute text-xs">(AI memory)</span></Label>
            <Textarea data-testid="res-memory" value={form.memory} onChange={(e) => setForm({ ...form, memory: e.target.value })} placeholder="Her late husband Frank passed in 2019. She was a schoolteacher in Boston." />
          </div>

          {/* Per-resident clinical thresholds — optional, suppresses false-positive
              wearable alerts on residents with unusual baseline vitals. */}
          <div className="border-t border-caos-line pt-4">
            <div className="flex items-baseline justify-between mb-1">
              <Label className="text-caos-forest font-semibold">Clinical thresholds <span className="text-caos-mute text-xs font-normal">(optional — wearable alerts only)</span></Label>
              <span className="text-[10px] uppercase tracking-[0.2em] text-caos-mute">Not diagnostic</span>
            </div>
            <p className="text-xs text-caos-mute mb-3 leading-relaxed">
              Leave blank to use generic wearable defaults. Set these for residents whose baseline vitals fall outside normal ranges (e.g. chronic AFib, athlete, COPD) so CAOS doesn't page staff for non-events.
            </p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <Label className="text-xs">Resting HR min (bpm)</Label>
                <Input type="number" min="20" max="200" data-testid="res-hr-min" value={form.clinical_thresholds.hr_resting_min} onChange={(e) => setForm({ ...form, clinical_thresholds: { ...form.clinical_thresholds, hr_resting_min: e.target.value } })} placeholder="50" />
              </div>
              <div>
                <Label className="text-xs">Resting HR max (bpm)</Label>
                <Input type="number" min="20" max="220" data-testid="res-hr-max" value={form.clinical_thresholds.hr_resting_max} onChange={(e) => setForm({ ...form, clinical_thresholds: { ...form.clinical_thresholds, hr_resting_max: e.target.value } })} placeholder="95" />
              </div>
              <div>
                <Label className="text-xs">Exertion ceiling (bpm)</Label>
                <Input type="number" min="40" max="240" data-testid="res-hr-exert" value={form.clinical_thresholds.hr_exertion_max} onChange={(e) => setForm({ ...form, clinical_thresholds: { ...form.clinical_thresholds, hr_exertion_max: e.target.value } })} placeholder="130" />
              </div>
              <div>
                <Label className="text-xs">SpO₂ floor (%)</Label>
                <Input type="number" min="50" max="100" data-testid="res-spo2" value={form.clinical_thresholds.spo2_min} onChange={(e) => setForm({ ...form, clinical_thresholds: { ...form.clinical_thresholds, spo2_min: e.target.value } })} placeholder="92" />
              </div>
              <div>
                <Label className="text-xs">Inactivity window (min)</Label>
                <Input type="number" min="5" max="720" data-testid="res-inactivity" value={form.clinical_thresholds.inactivity_minutes} onChange={(e) => setForm({ ...form, clinical_thresholds: { ...form.clinical_thresholds, inactivity_minutes: e.target.value } })} placeholder="90" />
              </div>
            </div>
            <div className="mt-3">
              <Label className="text-xs">Clinician note</Label>
              <Input data-testid="res-ct-notes" value={form.clinical_thresholds.notes} onChange={(e) => setForm({ ...form, clinical_thresholds: { ...form.clinical_thresholds, notes: e.target.value } })} placeholder="Chronic afib — expect resting 100–120" />
            </div>
          </div>

          <DialogFooter><Button type="submit" data-testid="res-save" className="bg-caos-forest">Save</Button></DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
