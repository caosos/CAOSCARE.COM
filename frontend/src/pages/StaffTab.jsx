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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Trash2, Plus } from "lucide-react";
import { SetPasswordDialog } from "../components/PasswordDialogs";
import { toast } from "sonner";

/* -------------- Staff -------------- */
export default function StaffTab({ staff, onChange }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "staff" });

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/staff", form);
      toast.success("Staff added");
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "staff" });
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this staff member?")) return;
    try {
      await api.delete(`/staff/${id}`);
      toast.success("Deleted");
      onChange();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Card className="border-caos-line p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="font-display text-xl font-medium text-caos-forest">Staff accounts</h2>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-staff-btn">
              <Plus className="w-4 h-4 mr-2" /> Add staff
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader><DialogTitle className="font-display">New staff</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-4">
              <div><Label>Name</Label><Input required data-testid="staff-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
              <div><Label>Email</Label><Input required type="email" data-testid="staff-email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></div>
              <div><Label>Password</Label><Input required type="password" minLength={6} data-testid="staff-password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></div>
              <div>
                <Label>Role</Label>
                <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                  <SelectTrigger data-testid="staff-role"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="staff">Staff</SelectItem>
                    <SelectItem value="front_desk">Front desk</SelectItem>
                    <SelectItem value="admin">Admin</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="staff-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <Table>
        <TableHeader>
          <TableRow><TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead><TableHead>Provider</TableHead><TableHead></TableHead></TableRow>
        </TableHeader>
        <TableBody>
          {staff.map((s) => (
            <TableRow key={s.user_id} data-testid={`staff-row-${s.user_id}`}>
              <TableCell className="font-medium">{s.name}</TableCell>
              <TableCell>{s.email}</TableCell>
              <TableCell><span className="uppercase text-xs font-bold tracking-wider">{s.role}</span></TableCell>
              <TableCell className="text-caos-mute">{s.auth_provider}</TableCell>
              <TableCell className="flex gap-1 justify-end">
                <SetPasswordDialog userId={s.user_id} name={s.name} />
                <Button variant="ghost" size="sm" onClick={() => remove(s.user_id)} data-testid={`del-staff-${s.user_id}`}>
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
