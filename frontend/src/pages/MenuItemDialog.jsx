import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "../components/ui/dialog";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { toast } from "sonner";
import { MEAL_PERIODS } from "../lib/communityServices";

// Add a menu item, or correct an existing one. A correction to a published
// item is either published straight away (the editor is the reviewer) or
// saved as a draft, which takes it off the residents' menu until approved
// (routes/menu.py::update_menu_item).
export default function MenuItemDialog({ open, onOpenChange, date, item = null, onSaved }) {
  const blank = { date, meal_period: "lunch", item_name: "", description: "", availability: "" };
  const [form, setForm] = useState(blank);

  useEffect(() => {
    if (!open) return;
    setForm(item
      ? { date: item.date, meal_period: item.meal_period, item_name: item.item_name,
          description: item.description || "", availability: item.availability || "" }
      : { ...blank, date });
  }, [open, item, date]); // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (publish) => {
    if (!form.item_name.trim()) { toast.error("Item name is required"); return; }
    try {
      if (item) {
        await api.patch(`/menu/${item.menu_id}`, { ...form, publish });
      } else {
        const { data } = await api.post("/menu", form);
        if (publish) await api.post(`/menu/${data.menu_id}/approve`);
      }
      toast.success(publish ? "Published — residents and Aria see this now" : "Saved as draft — not visible to residents yet");
      onOpenChange(false);
      onSaved?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not save");
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
            This item is published. "Save as draft" removes it from the residents' menu until it is approved again.
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
          <DialogFooter className="gap-2">
            <Button type="button" variant="outline" className="border-2" onClick={() => save(false)} data-testid="menu-save-draft">Save as draft</Button>
            <Button type="submit" className="bg-caos-forest" data-testid="menu-save-publish">Save and publish</Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
