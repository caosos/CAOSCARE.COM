import React, { useEffect, useState } from "react";
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
import { Badge } from "../components/ui/badge";
import { Trash2, Plus, Pencil } from "lucide-react";
import { SetPasswordDialog } from "../components/PasswordDialogs";
import { toast } from "sonner";

const NONE = "__none";
const ROLES = [
  { value: "staff", label: "Staff" },
  { value: "front_desk", label: "Front desk" },
  { value: "admin", label: "Admin" },
];

// Shared department picker fed by the real Department list (routes/
// departments.py). Value is a Department.slug, or NONE for "no department".
function DepartmentSelect({ value, onChange, departments, testid }) {
  return (
    <Select value={value || NONE} onValueChange={(v) => onChange(v === NONE ? "" : v)}>
      <SelectTrigger data-testid={testid}><SelectValue placeholder="No department" /></SelectTrigger>
      <SelectContent>
        <SelectItem value={NONE}>No department</SelectItem>
        {departments.map((d) => (
          <SelectItem key={d.slug} value={d.slug}>
            {d.label}{d.active === false ? " (inactive)" : ""}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/* -------------- Staff -------------- */
export default function StaffTab({ staff, onChange }) {
  const [open, setOpen] = useState(false);
  const [departments, setDepartments] = useState([]);
  const [editing, setEditing] = useState(null); // staff row being edited
  const [form, setForm] = useState({ name: "", email: "", password: "", role: "staff", department: "" });

  const fetchDepartments = async () => {
    try {
      const { data } = await api.get("/departments");
      setDepartments(data);
    } catch {
      // Non-fatal - the picker just shows "No department" only.
      setDepartments([]);
    }
  };
  useEffect(() => { fetchDepartments(); }, []);

  const deptLabel = (slug) => {
    if (!slug) return null;
    const d = departments.find((x) => x.slug === slug);
    return d ? d.label : slug;
  };

  const create = async (e) => {
    e.preventDefault();
    try {
      const payload = { ...form };
      if (!payload.department) delete payload.department;
      await api.post("/staff", payload);
      toast.success("Staff added");
      setOpen(false);
      setForm({ name: "", email: "", password: "", role: "staff", department: "" });
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
      <div className="flex justify-between items-center mb-2">
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
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label>Role</Label>
                  <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                    <SelectTrigger data-testid="staff-role"><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Department</Label>
                  <DepartmentSelect
                    value={form.department}
                    onChange={(v) => setForm({ ...form, department: v })}
                    departments={departments}
                    testid="staff-department"
                  />
                </div>
              </div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="staff-save">Save</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>
      <p className="text-caos-mute text-sm mb-4">
        Department decides which requests a staff member sees and where they land after signing in —
        Maintenance, Housekeeping, Transportation and Kitchen each get their own workspace; Nursing / Care
        and unassigned staff get the resident-assistance board.
      </p>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead><TableHead>Email</TableHead><TableHead>Role</TableHead>
            <TableHead>Department</TableHead><TableHead>Provider</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {staff.map((s) => (
            <TableRow key={s.user_id} data-testid={`staff-row-${s.user_id}`}>
              <TableCell className="font-medium">{s.name}</TableCell>
              <TableCell>{s.email}</TableCell>
              <TableCell><span className="uppercase text-xs font-bold tracking-wider">{s.role}</span></TableCell>
              <TableCell data-testid={`staff-dept-${s.user_id}`}>
                {s.department
                  ? <Badge variant="outline">{deptLabel(s.department)}</Badge>
                  : <span className="text-caos-mute text-xs italic">—</span>}
              </TableCell>
              <TableCell className="text-caos-mute">{s.auth_provider}</TableCell>
              <TableCell className="flex gap-1 justify-end">
                <Button variant="ghost" size="sm" onClick={() => setEditing(s)} data-testid={`edit-staff-${s.user_id}`}>
                  <Pencil className="w-4 h-4 text-caos-forest" />
                </Button>
                <SetPasswordDialog userId={s.user_id} name={s.name} />
                <Button variant="ghost" size="sm" onClick={() => remove(s.user_id)} data-testid={`del-staff-${s.user_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      <EditStaffDialog
        staff={editing}
        departments={departments}
        onClose={() => setEditing(null)}
        onSaved={() => { setEditing(null); onChange(); }}
      />
    </Card>
  );
}

function EditStaffDialog({ staff, departments, onClose, onSaved }) {
  const [form, setForm] = useState({ name: "", role: "staff", department: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (staff) setForm({ name: staff.name || "", role: staff.role || "staff", department: staff.department || "" });
  }, [staff]);

  if (!staff) return null;

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      // Send only what changed; "" for department is a real value (clear it).
      const patch = {};
      if (form.name !== staff.name) patch.name = form.name;
      if (form.role !== staff.role) patch.role = form.role;
      if ((form.department || "") !== (staff.department || "")) patch.department = form.department || "";
      if (Object.keys(patch).length === 0) { onClose(); return; }
      await api.patch(`/staff/${staff.user_id}`, patch);
      toast.success("Staff updated");
      onSaved();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to update");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={!!staff} onOpenChange={(v) => !v && onClose()}>
      <DialogContent data-testid="edit-staff-dialog">
        <DialogHeader><DialogTitle className="font-display">Edit {staff.name}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="space-y-4">
          <div><Label>Name</Label><Input required data-testid="edit-staff-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="text-sm text-caos-mute">{staff.email}</div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Role</Label>
              <Select value={form.role} onValueChange={(v) => setForm({ ...form, role: v })}>
                <SelectTrigger data-testid="edit-staff-role"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {ROLES.map((r) => <SelectItem key={r.value} value={r.value}>{r.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label>Department</Label>
              <DepartmentSelect
                value={form.department}
                onChange={(v) => setForm({ ...form, department: v })}
                departments={departments}
                testid="edit-staff-department"
              />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" className="bg-caos-forest" disabled={saving} data-testid="edit-staff-save">
              {saving ? "Saving…" : "Save changes"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
