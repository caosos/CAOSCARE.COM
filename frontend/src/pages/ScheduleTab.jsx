import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Table, TableHeader, TableRow, TableHead, TableBody, TableCell } from "../components/ui/table";
import { Badge } from "../components/ui/badge";
import { Plus, Trash2, Pencil, Check } from "lucide-react";
import { toast } from "sonner";
import { scheduleStatusView } from "../lib/communityServices";
import ScheduleItemDialog, { SCHEDULE_CATEGORY_LABELS } from "./ScheduleItemDialog";
import ScheduleReviewPanel from "./ScheduleReviewPanel";

const TONE = {
  live: "bg-caos-moss text-white",
  draft: "border border-caos-amber text-[#8B5A20] bg-caos-amber/10",
  old: "border border-caos-line text-caos-mute line-through",
};

function todayLocal() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Activities / admin schedule workspace. Residents' room screens and Aria
// read only published, resident-facing entries
// (routes/schedule.py::public_today); the server returns clock order.
export default function ScheduleTab() {
  const [date, setDate] = useState(todayLocal());
  const [items, setItems] = useState([]);
  const [editing, setEditing] = useState(null); // null | "new" | item
  const [refreshKey, setRefreshKey] = useState(0);

  const fetchAll = async () => {
    try {
      const { data } = await api.get("/schedule", { params: { date } });
      setItems(data);
    } catch {
      toast.error("Could not load schedule");
    }
  };
  useEffect(() => { fetchAll(); }, [date]); // eslint-disable-line react-hooks/exhaustive-deps

  const changed = () => { fetchAll(); setRefreshKey((k) => k + 1); };

  const publish = async (id) => {
    try {
      await api.post(`/schedule/${id}/publish`);
      toast.success("Published — residents see this now");
      changed();
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not publish"); }
  };

  const remove = async (i) => {
    if (!window.confirm("Delete this schedule entry?")) return;
    try {
      await api.delete(`/schedule/${i.schedule_id}`);
      toast.success("Deleted");
      changed();
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not delete"); }
  };

  return (
    <Card className="border-caos-line p-6" data-testid="schedule-tab-root">
      <div className="flex flex-wrap justify-between items-start gap-y-3 mb-4">
        <div>
          <h2 className="font-display text-xl font-medium text-caos-forest">Daily schedule</h2>
          <p className="text-caos-mute text-sm mt-1">
            What residents see on their room screen and what Aria says when asked "what's happening today." Only published entries are shown or spoken; staff notes never are.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="w-auto" data-testid="schedule-date-picker" />
          <Button className="bg-caos-forest hover:bg-caos-forest-hover rounded-full" onClick={() => setEditing("new")} data-testid="add-schedule-btn">
            <Plus className="w-4 h-4 mr-2" /> Add
          </Button>
        </div>
      </div>

      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Status</TableHead><TableHead>Time</TableHead><TableHead>Entry</TableHead><TableHead className="hidden sm:table-cell">Type</TableHead><TableHead></TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((i) => {
            const view = scheduleStatusView(i.status);
            return (
              <TableRow key={i.schedule_id} data-testid={`sched-row-${i.schedule_id}`} className={view.tone === "old" ? "opacity-60" : ""}>
                <TableCell><Badge className={`uppercase text-[10px] ${TONE[view.tone]}`}>{view.label}</Badge></TableCell>
                <TableCell className="text-sm tabular-nums">{i.time_label || "—"}</TableCell>
                <TableCell>
                  <div className="font-medium">{i.title}</div>
                  {i.description && <div className="text-caos-mute text-xs">{i.description}</div>}
                  {i.category !== "activity" && (
                    <div className="sm:hidden text-caos-mute text-xs">{SCHEDULE_CATEGORY_LABELS[i.category] || i.category}</div>
                  )}
                </TableCell>
                <TableCell className="hidden sm:table-cell"><Badge variant="outline">{SCHEDULE_CATEGORY_LABELS[i.category] || i.category}</Badge></TableCell>
                <TableCell className="flex flex-wrap gap-1 justify-end">
                  {view.canPublish && (
                    <Button variant="outline" size="sm" className="border-2" onClick={() => publish(i.schedule_id)} aria-label="Publish" title="Publish" data-testid={`publish-sched-${i.schedule_id}`}>
                      <Check className="w-4 h-4 sm:mr-1" /><span className="hidden sm:inline">Publish</span>
                    </Button>
                  )}
                  {view.tone !== "old" && (
                    <Button variant="ghost" size="sm" onClick={() => setEditing(i)} data-testid={`edit-sched-${i.schedule_id}`}>
                      <Pencil className="w-4 h-4" />
                    </Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => remove(i)} data-testid={`del-sched-${i.schedule_id}`}>
                    <Trash2 className="w-4 h-4 text-caos-terracotta" />
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
          {items.length === 0 && (
            <TableRow><TableCell colSpan={5} className="text-center text-caos-mute py-6">Nothing scheduled for this date yet.</TableCell></TableRow>
          )}
        </TableBody>
      </Table>

      <ScheduleReviewPanel refreshKey={refreshKey} onChanged={fetchAll} />

      <ScheduleItemDialog open={!!editing} onOpenChange={(o) => { if (!o) setEditing(null); }}
        date={date} item={editing === "new" ? null : editing} onSaved={changed} />
    </Card>
  );
}
