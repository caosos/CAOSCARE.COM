import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../components/ui/select";
import { Badge } from "../components/ui/badge";
import { Plus, Trash2, Check } from "lucide-react";
import { toast } from "sonner";

const MEAL_PERIODS = ["breakfast", "lunch", "dinner"];

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export default function MenuTab() {
  const [date, setDate] = useState(todayLocal());
  const [items, setItems] = useState([]);
  const [open, setOpen] = useState(false);
  const empty = { date: todayLocal(), meal_period: "lunch", item_name: "", description: "", availability: "" };
  const [form, setForm] = useState(empty);

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/menu", { params: { date } });
      setItems(data);
    } catch {
      toast.error("Could not load menu");
    }
  };
  useEffect(() => { fetchAll(); }, [date]); // eslint-disable-line react-hooks/exhaustive-deps

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/menu", form);
      toast.success("Added as draft — approve it to make it live");
      setOpen(false);
      setForm({ ...empty, date });
      fetchAll();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed");
    }
  };

  const approve = async (id) => {
    try {
      await api.post(`/menu/${id}/approve`);
      toast.success("Approved — Aria can read this now");
      fetchAll();
    } catch { toast.error("Could not approve"); }
  };

  const remove = async (id) => {
    if (!window.confirm("Delete this menu item?")) return;
    await api.delete(`/menu/${id}`);
    toast.success("Deleted");
    fetchAll();
  };

  return (
    <Card className="border-caos-line p-6" data-testid="menu-tab-root">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Menu</h2>
          <p className="text-caos-mute text-sm mt-1">
            Aria only ever speaks from <strong>approved</strong> items. New entries start as drafts — nothing is live until you approve it.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto" data-testid="menu-date-picker" />
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" data-testid="add-menu-btn">
                <Plus className="w-4 h-4 mr-2" /> Add
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader><DialogTitle className="font-display">New menu item (draft)</DialogTitle></DialogHeader>
              <form onSubmit={create} className="space-y-3">
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
                <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="menu-save">Add as draft</Button></DialogFooter>
              </form>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Status</TableHead><TableHead>Meal</TableHead><TableHead>Item</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((i) => (
            <TableRow key={i.menu_id} data-testid={`menu-row-${i.menu_id}`}>
              <TableCell>
                {i.status === "approved"
                  ? <Badge className="bg-caos-moss text-white">APPROVED</Badge>
                  : <Badge variant="outline">draft</Badge>}
              </TableCell>
              <TableCell className="text-xs uppercase tracking-wider">{i.meal_period}</TableCell>
              <TableCell>
                <div className="font-medium">{i.item_name}</div>
                {i.description && <div className="text-caos-mute text-xs">{i.description}</div>}
                {i.availability && <div className="text-caos-mute text-xs italic">{i.availability}</div>}
              </TableCell>
              <TableCell className="flex gap-1 justify-end">
                {i.status !== "approved" && (
                  <Button variant="outline" size="sm" onClick={() => approve(i.menu_id)} className="border-2" data-testid={`approve-menu-${i.menu_id}`}>
                    <Check className="w-4 h-4 mr-1" /> Approve
                  </Button>
                )}
                <Button variant="ghost" size="sm" onClick={() => remove(i.menu_id)} data-testid={`del-menu-${i.menu_id}`}>
                  <Trash2 className="w-4 h-4 text-caos-terracotta" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
    {items.length === 0 && (
            <TableRow><TableCell colSpan={4} className="text-center text-caos-mute py-6">No menu items for this date yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <MenuUploadsPanel onApproved={fetchAll} />
    </Card>
  );
}

function MenuUploadsPanel({ onApproved }) {
  const [uploads, setUploads] = useState([]);
  const [open, setOpen] = useState(false);
  const [serviceDate, setServiceDate] = useState(todayLocal());
  const [rawText, setRawText] = useState(
    "Breakfast: Scrambled eggs, bacon, toast, orange juice\nLunch: Grilled cheese, tomato soup, apple slices\nDinner: Baked chicken, mashed potatoes, green beans, apple crisp"
  );

  const fetchUploads = async () => {
    try {
      const { data } = await api.get("/menu/uploads");
      setUploads(data);
    } catch { /* silent - dev panel */ }
  };
  useEffect(() => { fetchUploads(); }, []);

  const ingest = async (e) => {
    e.preventDefault();
    try {
      await api.post("/menu/ingest/dev-test", { service_date: serviceDate, raw_text: rawText, source_ref: "dev-test" });
      toast.success("Ingested — review below, then approve to publish");
      setOpen(false);
      fetchUploads();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to ingest");
    }
  };

  const approve = async (uploadId) => {
    try {
      await api.post(`/menu/uploads/${uploadId}/approve`);
      toast.success("Upload approved — items are live");
      fetchUploads();
      onApproved?.();
    } catch { toast.error("Could not approve upload"); }
  };

  return (
    <div className="mt-8 pt-6 border-t border-caos-line">
      <div className="flex justify-between items-center mb-3">
        <div>
          <h3 className="font-display text-lg font-medium text-caos-forest">Menu email ingestion</h3>
          <p className="text-caos-mute text-xs mt-1">
            No real mailbox is connected yet — this simulates "an email arrived" so the parse → draft → approve pipeline can be proven before real inbound email is wired up.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" className="border-2 rounded-full" data-testid="ingest-test-email-btn">Ingest test email</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-display">Simulate incoming menu email</DialogTitle></DialogHeader>
            <form onSubmit={ingest} className="space-y-3">
              <div><Label>Service date</Label><Input type="date" required value={serviceDate} onChange={(e) => setServiceDate(e.target.value)} data-testid="ingest-date" /></div>
              <div><Label>Email body</Label><Textarea rows={8} required value={rawText} onChange={(e) => setRawText(e.target.value)} data-testid="ingest-body" /></div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="ingest-submit">Ingest</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-2">
        {uploads.map((u) => (
          <div key={u.upload_id} className="flex items-center justify-between p-3 rounded-xl border border-caos-line" data-testid={`upload-row-${u.upload_id}`}>
            <div className="min-w-0">
              <div className="text-sm font-medium">{u.service_date} · {u.item_ids.length} item{u.item_ids.length === 1 ? "" : "s"}</div>
              <div className="text-xs text-caos-mute">
                {u.parse_status === "needs_review"
                  ? <span className="text-caos-terracotta">needs review — {u.parse_notes}</span>
                  : "parsed cleanly"}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {u.status === "approved"
                ? <Badge className="bg-caos-moss text-white">APPROVED</Badge>
                : <Button size="sm" variant="outline" className="border-2" onClick={() => approve(u.upload_id)} data-testid={`approve-upload-${u.upload_id}`}>Approve upload</Button>}
            </div>
          </div>
        ))}
        {uploads.length === 0 && <div className="text-center text-caos-mute py-4 text-sm">No ingested emails yet.</div>}
      </div>
    </div>
  );
}
