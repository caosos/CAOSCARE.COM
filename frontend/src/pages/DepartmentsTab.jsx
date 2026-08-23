import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import DepartmentWorkspaceDialog from "./DepartmentWorkspaceDialog";

export default function DepartmentsTab() {
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const [workspaceDept, setWorkspaceDept] = useState(null);
  const empty = { label: "", description: "", contact_email: "" };
  const [form, setForm] = useState(empty);

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/departments");
      setItems(data);
    } catch {
      toast.error("Could not load departments");
    }
  };
  useEffect(() => { fetchAll(); }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/departments", form);
      toast.success("Department added");
      setOpen(false);
      setForm(empty);
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const toggleActive = async (dept) => {
    try {
      await api.patch(`/departments/${dept.department_id}`, { active: !dept.active });
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this department? Existing requests already routed to it keep their history.")) return;
    try {
      await api.delete(`/departments/${id}`);
      toast.success("Deleted");
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  return (
    <Card className="border-caos-line p-6" data-testid="departments-tab-root">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Departments</h2>
          <p className="text-caos-mute text-sm mt-1">
            Who a staff request can route to. Staff pick one of these as their department, and Aria's request
            categories validate against this same list. Deactivating a department stops it from being offered
            for new requests without touching anything already routed to it.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-department-btn">
              Add department
            </Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-display">New department</DialogTitle></DialogHeader>
            <form onSubmit={create} className="space-y-3">
              <div><Label>Name</Label><Input required placeholder="Kitchen" value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} data-testid="dept-label" /></div>
              <div><Label>Description (optional)</Label><Textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} data-testid="dept-desc" /></div>
              <div><Label>Contact email (optional)</Label><Input type="email" placeholder="kitchen@facility.com" value={form.contact_email} onChange={(e) => setForm({ ...form, contact_email: e.target.value })} data-testid="dept-email" /></div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="dept-save">Add</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead><TableHead>Contact</TableHead><TableHead>Status</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((d) => (
            <TableRow
              key={d.department_id}
              className="cursor-pointer hover:bg-caos-bone/60"
              onClick={() => setWorkspaceDept(d)}
              data-testid={`dept-row-${d.department_id}`}
            >
              <TableCell>
                <div className="font-medium">{d.label}</div>
                {d.description && <div className="text-caos-mute text-xs">{d.description}</div>}
              </TableCell>
              <TableCell className="text-sm">{d.contact_email || "—"}</TableCell>
              <TableCell>
                <Badge
                  variant="outline"
                  className={`cursor-pointer ${d.active ? "" : "text-caos-mute"}`}
                  onClick={(e) => { e.stopPropagation(); toggleActive(d); }}
                  data-testid={`dept-toggle-${d.department_id}`}
                >
                  {d.active ? "Active" : "Inactive"}
                </Badge>
              </TableCell>
              <TableCell>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => { e.stopPropagation(); remove(d.department_id); }}
                  data-testid={`del-dept-${d.department_id}`}
                >
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={4} className="text-center text-caos-mute py-6">No departments yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <DepartmentWorkspaceDialog department={workspaceDept} onClose={() => setWorkspaceDept(null)} />
    </Card>
  );
}
