import React, { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Card } from "../components/ui/card";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter,
} from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Checkbox } from "../components/ui/checkbox";
import { Badge } from "../components/ui/badge";
import { Trash2, Plus } from "lucide-react";
import { toast } from "sonner";

/* -------------- Kiosks -------------- */
export default function KiosksTab({ kiosks, zones, onChange }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", room: "", zone: "", mac_address: "", is_central: false });

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/kiosks", form);
      toast.success("Kiosk added");
      setOpen(false);
      setForm({ name: "", room: "", zone: "", mac_address: "", is_central: false });
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this kiosk?")) return;
    await api.delete(`/kiosks/${id}`);
    toast.success("Deleted");
    onChange();
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Wall kiosks</h2>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-kiosk-btn">
              <Plus className="w-4 h-4 mr-2" /> Add kiosk
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-display">New kiosk</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div><Label>Display name</Label><Input required data-testid="kiosk-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div className="grid grid-cols-2 gap-3">
                <div><Label>Room</Label><Input required data-testid="kiosk-room" value={form.room} onChange={(e) => setForm({ ...form, room: e.target.value })} /></div>
                <div>
                  <Label>Zone</Label>
                  <Select value={form.zone} onValueChange={(v) => setForm({ ...form, zone: v })}>
                    <SelectTrigger data-testid="kiosk-zone"><SelectValue placeholder="Select zone" /></SelectTrigger>
                    <SelectContent>
                      {zones.map((z) => <SelectItem key={z.zone_id} value={z.name}>{z.name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div><Label>MAC address (optional)</Label><Input data-testid="kiosk-mac" value={form.mac_address} onChange={(e) => setForm({ ...form, mac_address: e.target.value })} /></div>
              <label className="flex items-center gap-2 cursor-pointer" data-testid="kiosk-central-toggle">
                <Checkbox checked={form.is_central} onCheckedChange={(v) => setForm({ ...form, is_central: !!v })} />
                <span className="text-sm font-semibold text-caos-forest">Central nurse station <span className="text-caos-mute font-normal">(listens for any facility emergency)</span></span>
              </label>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="kiosk-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Table>
        <TableHeader><TableRow><TableHead>Name</TableHead><TableHead>Room</TableHead><TableHead>Zone</TableHead><TableHead>MAC</TableHead><TableHead>Kiosk link</TableHead><TableHead></TableHead></TableRow></TableHeader>
        <TableBody>
          {kiosks.map((k) => (
            <TableRow key={k.kiosk_id} data-testid={`kiosk-row-${k.kiosk_id}`}>
              <TableCell className="font-medium">
                {k.name}
                {k.is_central && <Badge className="ml-2 bg-caos-terracotta text-white uppercase text-[10px] tracking-wider">Central</Badge>}
              </TableCell>
              <TableCell>{k.room}</TableCell>
              <TableCell>{k.zone}</TableCell>
              <TableCell className="font-mono text-xs">{k.mac_address || "—"}</TableCell>
              <TableCell>
                <Link to={`/kiosk/${k.kiosk_id}`} className="text-caos-forest underline text-sm" data-testid={`kiosk-open-${k.kiosk_id}`}>Open →</Link>
              </TableCell>
              <TableCell>
                <Button variant="ghost" size="sm" onClick={() => remove(k.kiosk_id)} data-testid={`del-kiosk-${k.kiosk_id}`}>
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
