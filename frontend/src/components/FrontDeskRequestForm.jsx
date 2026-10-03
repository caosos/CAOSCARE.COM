import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Label } from "./ui/label";
import { Textarea } from "./ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "./ui/dialog";
import { toast } from "sonner";

// Front desk enters a request on a resident's behalf (a phone call, a
// family member at the desk, a callback). Goes through the same
// resident-request bus Aria uses (POST /tasks/resident-request, source
// "front_desk"), so it gets the same routing, duplicate detection, receipt
// and department notification. Rides use the ride form instead so they go
// through the booking engine.
export default function FrontDeskRequestForm({ open, onOpenChange, residentId = "", onSaved }) {
  const [residents, setResidents] = useState([]);
  const [categories, setCategories] = useState([]);
  const [form, setForm] = useState({});
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    setForm({ resident_id: residentId, category: "administration", summary: "", resident_words: "", priority: "normal" });
    api.get("/residents").then(({ data }) => setResidents(data)).catch(() => setResidents([]));
    api.get("/front-desk/request-categories")
      .then(({ data }) => setCategories(data.filter((c) => c.slug !== "transportation")))
      .catch(() => setCategories([]));
  }, [open, residentId]);

  const set = (patch) => setForm((f) => ({ ...f, ...patch }));
  const resident = residents.find((r) => r.resident_id === form.resident_id);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/tasks/resident-request", {
        category: form.category, resident_id: form.resident_id, room: resident?.room || null,
        summary: form.summary, resident_words: form.resident_words || null,
        priority: form.priority, source: "front_desk",
      });
      if (data.duplicate) {
        toast.info(`${resident?.name || "This resident"} already has an open ${form.category} request — added as a re-request (asked ${data.re_request_count + 1}x).`);
      } else {
        toast.success("Request sent to the department");
      }
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      const d = err?.response?.data?.detail;
      toast.error(d?.reason ? `Not saved: ${d.reason}` : (typeof d === "string" ? d : "Could not create the request"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle className="font-display">New request</DialogTitle></DialogHeader>
        <form onSubmit={submit} className="space-y-3">
          <div>
            <Label>Resident</Label>
            <Select value={form.resident_id || ""} onValueChange={(v) => set({ resident_id: v })}>
              <SelectTrigger data-testid="fd-request-resident"><SelectValue placeholder="Choose a resident" /></SelectTrigger>
              <SelectContent>
                {residents.map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Room {r.room}</SelectItem>)}
              </SelectContent>
            </Select>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <Label>Department</Label>
              <Select value={form.category || ""} onValueChange={(v) => set({ category: v })}>
                <SelectTrigger data-testid="fd-request-category"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {categories.map((c) => <SelectItem key={c.slug} value={c.slug}>{c.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Priority</Label>
              <Select value={form.priority || "normal"} onValueChange={(v) => set({ priority: v })}>
                <SelectTrigger data-testid="fd-request-priority"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {["low", "normal", "high", "urgent"].map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>What is needed</Label>
            <Input required value={form.summary || ""} placeholder="e.g. Callback about the September bill"
              onChange={(e) => set({ summary: e.target.value })} data-testid="fd-request-summary" />
          </div>
          <div>
            <Label>Who asked / exact words (optional)</Label>
            <Textarea rows={2} value={form.resident_words || ""} placeholder="e.g. Daughter Karen called: 'Mom's bill looks double-charged'"
              onChange={(e) => set({ resident_words: e.target.value })} data-testid="fd-request-words" />
          </div>
          <p className="text-caos-mute text-xs">Rides go through Transportation → New ride so they can be booked.</p>
          <DialogFooter>
            <Button type="submit" disabled={busy || !form.resident_id} className="bg-caos-forest" data-testid="fd-request-save">
              {busy ? "Sending…" : "Send request"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
