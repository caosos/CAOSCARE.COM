import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { toast } from "sonner";
import { groupDraftsByBatch } from "../lib/communityServices";
import { SCHEDULE_CATEGORY_LABELS } from "./ScheduleItemDialog";

const EXAMPLE = "Monday 2026-10-05:\n10:00 AM Chair Yoga - Sunroom\n2:00 PM Bingo - Main activity room\n\nTuesday 2026-10-06:\n1:00 PM Movie Afternoon";

// Emailed or pasted activity calendars waiting for review. Each calendar is
// one batch; publishing it makes its entries visible to residents and Aria
// and replaces earlier emailed/pasted entries for the same dates
// (routes/schedule.py::publish_batch).
export default function ScheduleReviewPanel({ refreshKey, onChanged }) {
  const [drafts, setDrafts] = useState([]);
  const [open, setOpen] = useState(false);
  const [rawText, setRawText] = useState("");

  const load = async () => {
    try { setDrafts((await api.get("/schedule/drafts")).data); } catch { setDrafts([]); }
  };
  useEffect(() => { load(); }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const paste = async (e) => {
    e.preventDefault();
    try {
      const { data } = await api.post("/schedule/ingest/paste", { raw_text: rawText });
      const skipped = data.skipped_lines?.length ? ` · ${data.skipped_lines.length} line(s) not understood` : "";
      toast.success(`${data.created_count} entr${data.created_count === 1 ? "y" : "ies"} added as drafts${skipped}`);
      setOpen(false);
      setRawText("");
      load();
      onChanged?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not read that calendar");
    }
  };

  const publish = async (ingestId) => {
    try {
      const { data } = await api.post(`/schedule/batches/${ingestId}/publish`);
      toast.success(`Published ${data.published_count} entr${data.published_count === 1 ? "y" : "ies"}` +
        (data.replaced_count ? ` · replaced ${data.replaced_count} older` : ""));
      load();
      onChanged?.();
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not publish"); }
  };

  const groups = groupDraftsByBatch(drafts);

  return (
    <div className="mt-8 pt-6 border-t border-caos-line" data-testid="schedule-review">
      <div className="flex flex-wrap justify-between items-start gap-3 mb-3">
        <div>
          <h3 className="font-display text-lg font-medium text-caos-forest">Calendars waiting for review</h3>
          <p className="text-caos-mute text-xs mt-1">Emailed or pasted calendars arrive as drafts. Nothing reaches residents until you publish it.</p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" className="border-2 rounded-full" data-testid="schedule-paste-btn">Paste a calendar</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-display">Paste an activities calendar</DialogTitle></DialogHeader>
            <form onSubmit={paste} className="space-y-3">
              <div>
                <Label>Calendar text</Label>
                <Textarea rows={10} required placeholder={EXAMPLE} value={rawText} onChange={(e) => setRawText(e.target.value)} data-testid="schedule-paste-body" />
                <p className="text-xs text-caos-mute mt-1">
                  Start each day with its date (e.g. "Monday 2026-10-05:"), then one line per entry: time, title, and " - where". Add [facility_note] for an announcement.
                </p>
              </div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="schedule-paste-submit">Add as drafts</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-2">
        {groups.map((g) => (
          <div key={g.ingest_id || g.items[0].schedule_id} className="p-3 rounded-xl border border-caos-line" data-testid={`schedule-batch-${g.ingest_id}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium">
                  {g.source === "email" ? "Emailed calendar" : "Pasted calendar"} · {g.items.length} entr{g.items.length === 1 ? "y" : "ies"}
                  <span className="text-caos-mute font-normal"> · {g.items[0].date} to {g.items[g.items.length - 1].date}</span>
                </div>
                <ul className="mt-1 text-sm text-caos-ink/90 max-h-48 overflow-y-auto">
                  {g.items.map((i) => (
                    <li key={i.schedule_id}>
                      <span className="text-caos-mute tabular-nums mr-2">{i.date}{i.time_label ? ` ${i.time_label}` : ""}</span>
                      {i.title}{i.description ? ` — ${i.description}` : ""}
                      {i.category !== "activity" && <span className="text-xs text-caos-mute"> ({SCHEDULE_CATEGORY_LABELS[i.category] || i.category})</span>}
                    </li>
                  ))}
                </ul>
              </div>
              {g.ingest_id && (
                <Button size="sm" className="bg-caos-forest shrink-0" onClick={() => publish(g.ingest_id)} data-testid={`schedule-publish-${g.ingest_id}`}>Publish calendar</Button>
              )}
            </div>
          </div>
        ))}
        {groups.length === 0 && <div className="text-center text-caos-mute py-4 text-sm">Nothing waiting for review.</div>}
      </div>
    </div>
  );
}
