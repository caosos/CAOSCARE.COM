import React, { useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card } from "../components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

/* -------------- Zones -------------- */
export default function ZonesTab({ zones, onChange }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", floor: "", description: "", is_restricted: false });

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/zones", form);
      toast.success("Zone added");
      setOpen(false);
      setForm({ name: "", floor: "", description: "", is_restricted: false });
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this zone?")) return;
    await api.delete(`/zones/${id}`);
    toast.success("Deleted");
    onChange();
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Geo zones</h2>
          <p className="text-caos-mute text-sm mt-1">Mark a zone as <b>Restricted</b> to fire a wander/elopement alert if a resident enters it.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-zone-btn">
              <Plus className="w-4 h-4 mr-2" /> Add zone
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-display">New zone</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div><Label>Name</Label><Input required data-testid="zone-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div><Label>Floor</Label><Input data-testid="zone-floor" value={form.floor} onChange={(e) => setForm({ ...form, floor: e.target.value })} /></div>
              <div><Label>Description</Label><Textarea data-testid="zone-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="zone-restricted-toggle">
                <Checkbox checked={form.is_restricted} onCheckedChange={(v) => setForm({ ...form, is_restricted: !!v })} />
                <span className="text-sm font-semibold text-caos-forest">Restricted zone (fires wander alert on entry)</span>
              </label>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="zone-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Table>
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Floor</TableHead><TableHead>Description</TableHead><TableHead>Access</TableHead><TableHead></TableHead></TableRow></TableHeader>
        <TableBody>
          {zones.map((z) => (
            <TableRow key={z.zone_id} data-testid={`zone-row-${z.zone_id}`}>
              <TableCell className="font-medium">{z.name}</TableCell>
              <TableCell>{z.floor}</TableCell>
              <TableCell className="text-caos-mute text-sm">{z.description}</TableCell>
              <TableCell>
                {z.is_restricted
                  ? <Badge className="bg-caos-terracotta text-white uppercase tracking-wider text-xs font-bold">Restricted</Badge>
                  : <Badge variant="outline" className="uppercase tracking-wider text-xs">Open</Badge>}
              </TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(z.zone_id)} data-testid={`del-zone-${z.zone_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}
