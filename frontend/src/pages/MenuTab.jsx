import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Plus, Trash2, Check, Pencil } from "lucide-react";
import { toast } from "sonner";
import { MEAL_PERIODS, menuStatusView } from "../lib/communityServices";
import MenuItemDialog from "./MenuItemDialog";
import MenuUploadsPanel from "./MenuUploadsPanel";

const TONE = {
  live: "bg-caos-moss text-white",
  draft: "border border-caos-amber text-[#8B5A20] bg-caos-amber/10",
  old: "border border-caos-line text-caos-mute line-through",
};

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

const mealOrder = (m) => MEAL_PERIODS.indexOf(m);

// Kitchen / admin menu workspace: one date at a time. Residents (room
// screen) and Aria read only Published items (routes/menu.py::public_today).
export default function MenuTab() {
  const [date, setDate] = useState(todayLocal());
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null); // null | "new" | item
  const [refreshKey, setRefreshKey] = useState(0);

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/menu", { params: { date } });
      setItems([...data].sort((a, b) => mealOrder(a.meal_period) - mealOrder(b.meal_period)));
    } catch {
      toast.error("Could not load menu");
    }
  };
  useEffect(() => { fetchAll(); }, [date]); // eslint-disable-line react-hooks/exhaustive-deps

  const changed = () => { fetchAll(); setRefreshKey((k) => k + 1); };

  const approve = async (id) => {
    try {
      await api.post(`/menu/${id}/approve`);
      toast.success("Published — Aria can read this now");
      changed();
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not publish"); }
  };

  const remove = async (i) => {
    const live = i.status === "approved";
    if (!window.confirm(live ? "Remove this published item from the residents' menu?" : "Delete this menu item?")) return;
    try {
      await api.delete(`/menu/${i.menu_id}`);
      toast.success("Deleted");
      changed();
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not delete"); }
  };

  const published = items.filter((i) => i.status === "approved").length;
  const drafts = items.filter((i) => i.status === "draft").length;

  return (
    <Card className="border-caos-line p-6" data-testid="menu-tab-root">
      <div className="flex flex-wrap justify-between items-start gap-y-3 mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Menu</h2>
          <p className="text-caos-mute text-sm mt-1">
            Residents and Aria only ever see <strong>published</strong> items. Drafts stay here until someone publishes them.
          </p>
          <p className="text-sm mt-1" data-testid="menu-summary">
            <span className="text-caos-forest font-medium">{published} published</span>
            {drafts > 0 && <span className="text-[#8B5A20]"> · {drafts} waiting for review</span>}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto shrink-0" data-testid="menu-date-picker" />
          <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" onClick={() => setEditing("new")} data-testid="add-menu-btn">
            <Plus className="w-4 h-4 mr-2" /> Add
          </Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Status</TableHead><TableHead className="hidden sm:table-cell">Meal</TableHead><TableHead>Item</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((i) => {
            const view = menuStatusView(i.status);
            return (
              <TableRow key={i.menu_id} data-testid={`menu-row-${i.menu_id}`} className={view.tone === "old" ? "opacity-60" : ""}>
                <TableCell><Badge className={`uppercase text-[10px] ${TONE[view.tone]}`}>{view.label}</Badge></TableCell>
                <TableCell className="hidden sm:table-cell text-xs uppercase tracking-wider">{i.meal_period}</TableCell>
                <TableCell>
                  <div className="sm:hidden text-[10px] uppercase tracking-wider text-caos-mute">{i.meal_period}</div>
                  <div className="font-medium">{i.item_name}</div>
                  {i.description && <div className="text-caos-mute text-xs">{i.description}</div>}
                  {i.availability && <div className="text-caos-mute text-xs italic">{i.availability}</div>}
                </TableCell>
                <TableCell className="flex flex-wrap gap-1 justify-end">
                  {view.canApprove && (
                    <Button variant="outline" size="sm" onClick={() => approve(i.menu_id)} className="border-2" aria-label="Publish" title="Publish" data-testid={`approve-menu-${i.menu_id}`}>
                      <Check className="w-4 h-4 sm:mr-1" /><span className="hidden sm:inline">Publish</span>
                    </Button>
                  )}
                  {view.tone !== "old" && (
                    <Button variant="ghost" size="sm" onClick={() => setEditing(i)} data-testid={`edit-menu-${i.menu_id}`}>
                      <Pencil className="w-4 h-4" />
                    </Button>
                  )}
                  {view.tone !== "old" && (
                    <Button variant="ghost" size="sm" onClick={() => remove(i)} data-testid={`del-menu-${i.menu_id}`}>
                      <Trash2 className="w-4 h-4 text-caos-terracotta" />
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            );
          })}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={4} className="text-center text-caos-mute py-6">No menu items for this date yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <MenuUploadsPanel date={date} refreshKey={refreshKey} onChanged={fetchAll} />

      <MenuItemDialog open={!!editing} onOpenChange={(o) => { if (!o) setEditing(null); }}
        date={date} item={editing === "new" ? null : editing} onSaved={changed} />
    </Card>
  );
}
