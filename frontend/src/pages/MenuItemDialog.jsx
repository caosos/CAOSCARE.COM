import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { MEAL_PERIODS, MENU_LABELS_NOTE, parseMenuLabels } from "../lib/communityServices";

// Add a menu item, or correct an existing one. A correction to a published
// item is a new version that replaces it (routes/menu.py): published straight
// away (the editor is the reviewer), or saved as a draft while the published
// version stays on the residents' menu until the correction is published
// (routes/menu.py::update_menu_item).
export default function MenuItemDialog({ open, onOpenChange, date, item = null, onSaved }) {
  const blank = { date, meal_period: "lunch", item_name: "", description: "", availability: "", dietary_labels: "", allergens: "" };
  const [form, setForm] = useState(blank);

  useEffect(() => {
    if (!open) return;
    setForm(item
      ? { date: item.date, meal_period: item.meal_period, item_name: item.item_name,
          description: item.description || "", availability: item.availability || "",
          dietary_labels: (item.dietary_labels || []).join(", "), allergens: (item.allergens || []).join(", ") }
      : { ...blank, date });
  }, [open, item, date]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (publish) => {
    if (!form.item_name.trim()) { toast.error("Item name is required"); return; }
    const body = { ...form, dietary_labels: parseMenuLabels(form.dietary_labels), allergens: parseMenuLabels(form.allergens) };
    try {
      if (item) {
        await api.patch(`/menu/${item.menu_id}`, { ...body, publish });
      } else {
        const { data } = await api.post("/menu", body);
        if (publish) await api.post(`/menu/${data.menu_id}/approve`);
      }
      toast.success(publish ? "Published — residents and Aria see this now"
        : item?.status === "approved" ? "Correction saved as draft — residents still see the published version until you publish it"
        : "Saved as draft — not visible to residents yet");
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      const detail = err?.response?.data?.detail;
      toast.error(Array.isArray(detail) ? detail.map((d) => d.msg).join("; ") : detail || "Could not save");
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="font-display">{item ? "Correct menu item" : "New menu item"}</DialogTitle>
        </DialogHeader>
        {item?.status === "approved" && (
          <p className="text-sm text-caos-mute">
            This item is published. Your correction becomes a new version: "Save as draft" keeps the published version on the
            residents' menu until you publish the correction; "Save and publish" replaces it now. The old version stays listed as Replaced.
          </p>
        )}
        <form onSubmit={(e) => { e.preventDefault(); save(true); }} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div><Label>Date</Label><Input type="date" required value={form.date} onChange={(e) => setForm({ ...form, date: e.target.value })} data-testid="menu-date" /></div>
            <div>
              <Label>Meal</Label>
              <Select value={form.meal_period} onValueChange={(v) => setForm({ ...form, meal_period: v })}>
                <SelectTrigger data-testid="menu-meal"><SelectValue /></SelectTrigger>
                <SelectContent>{MEAL_PERIODS.map((m) => <SelectItem key={m} value={m}>{m}</SelectItem>)}</SelectContent>
              </Select>
            </div>
          </div>
          <div><Label>Item</Label><Input required placeholder="Roast chicken with rice" value={form.item_name} onChange={(e) => setForm({ ...form, item_name: e.target.value })} data-testid="menu-item-name" /></div>
          <div><Label>Description (optional)</Label><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="menu-desc" /></div>
          <div><Label>Availability (optional)</Label><Input placeholder="while supplies last" value={form.availability} onChange={(e) => setForm({ ...form, availability: e.target.value })} data-testid="menu-availability" /></div>
          <div><Label>Dietary labels (optional, comma-separated)</Label><Input placeholder="Vegetarian, Low sodium" value={form.dietary_labels} onChange={(e) => setForm({ ...form, dietary_labels: e.target.value })} data-testid="menu-dietary-labels" /></div>
          <div><Label>Contains allergens (optional, comma-separated)</Label><Input placeholder="Milk, Wheat" value={form.allergens} onChange={(e) => setForm({ ...form, allergens: e.target.value })} data-testid="menu-allergens" /></div>
          <p className="text-xs text-caos-mute" data-testid="menu-labels-note">Residents and Aria repeat these labels exactly. {MENU_LABELS_NOTE}</p>
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" className="border-2" onClick={() => save(false)} data-testid="menu-save-draft">Save as draft</Button>
            <Button type="submit" className="bg-caos-forest" data-testid="menu-save-publish">Save and publish</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
