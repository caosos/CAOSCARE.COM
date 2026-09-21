import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { CATEGORIES, SHIFTS } from "../lib/taskConstants";

// Extracted verbatim out of TasksTab.jsx 2026-09-21 (Track 1 Lane 2, see
// AGENTS.md's file-size/modularity rule) - recurring-template management is
// a distinct responsibility from the day-to-day task board, and this
// component was never used anywhere else, so the split is a clean
// domain boundary, not arbitrary chopping. Behavior unchanged.
export default function TaskTemplatesBoard({ templates, residents, onChange }) {
  const [open, setOpen] = useState(false);
  const empty = { title: "", description: "", category: "other", shift: "any", recur: "daily", active: true, resident_id: "" };
  const [form, setForm] = useState(empty);

  const create = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form };
      if (!payload.resident_id) delete payload.resident_id;
      await api.post("/tasks/templates", payload);
      toast.success("Template created");
      setOpen(false);
      setForm(empty);
      onChange();
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this template?")) return;
    await api.delete(`/tasks/templates/${id}`);
    toast.success("Deleted");
    onChange();
  };

  return (
    <div>
      <div className="flex justify-end mb-3">
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-template-btn">
              <Plus className="w-4 h-4 mr-2" /> New template
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-display">New recurring template</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-3">
              <div><Label>Title</Label><Input required data-testid="tpl-title" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
              <div><Label>Description</Label><Textarea data-testid="tpl-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
              <div className="grid grid-cols-3 gap-3">
                <div><Label>Category</Label>
                  <Select value={form.category} onValueChange={(v) => setForm({ ...form, category: v })}>
                    <SelectTrigger data-testid="tpl-cat"><SelectValue /></SelectTrigger>
                    <SelectContent>{CATEGORIES.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label>Shift</Label>
                  <Select value={form.shift} onValueChange={(v) => setForm({ ...form, shift: v })}>
                    <SelectTrigger data-testid="tpl-shift"><SelectValue /></SelectTrigger>
                    <SelectContent>{SHIFTS.map((s) => <SelectItem key={s} value={s}>{s}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div><Label>Recur</Label>
                  <Select value={form.recur} onValueChange={(v) => setForm({ ...form, recur: v })}>
                    <SelectTrigger data-testid="tpl-recur"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="daily">Daily</SelectItem>
                      <SelectItem value="weekly">Weekly</SelectItem>
                      <SelectItem value="per_shift">Per shift</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div>
                <Label>Resident (optional)</Label>
                <Select value={form.resident_id || "__none"} onValueChange={(v) => setForm({ ...form, resident_id: v === "__none" ? "" : v })}>
                  <SelectTrigger data-testid="tpl-resident"><SelectValue placeholder="None" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="__none">None</SelectItem>
                    {(residents || []).map((r) => <SelectItem key={r.resident_id} value={r.resident_id}>{r.name} · Rm {r.room}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="tpl-active">
                <Checkbox checked={form.active} onCheckedChange={(v) => setForm({ ...form, active: !!v })} />
                <span className="text-sm font-semibold text-caos-forest">Active (will spawn)</span>
              </label>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="tpl-save">Create</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Table>
        <TableHeader><TableRow>
          <TableHead>Title</TableHead><TableHead>Category</TableHead><TableHead>Shift</TableHead>
          <TableHead>Recur</TableHead><TableHead>Active</TableHead><TableHead></TableHead>
        </TableRow></TableHeader>
        <TableBody>
          {templates.map((t) => (
            <TableRow key={t.template_id} data-testid={`tpl-row-${t.template_id}`}>
              <TableCell>
                <div className="font-medium">{t.title}</div>
                <div className="text-caos-mute text-xs">{t.description}</div>
              </TableCell>
              <TableCell className="text-xs uppercase tracking-wider">{t.category}</TableCell>
              <TableCell className="text-xs uppercase tracking-wider">{t.shift}</TableCell>
              <TableCell className="text-xs uppercase tracking-wider">{t.recur}</TableCell>
              <TableCell>{t.active ? <Badge className="bg-caos-moss text-white">ACTIVE</Badge> : <Badge variant="outline">paused</Badge>}</TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(t.template_id)} data-testid={`del-tpl-${t.template_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {templates.length === 0 && (
            <TableRow><TableCell colSpan={6} className="text-center text-caos-mute py-6">No templates yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </div>
  );
}
