import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogFooter } from "../components/ui/dialog";
import { Badge } from "../components/ui/badge";
import { toast } from "sonner";

const EXAMPLE = "Breakfast: Scrambled eggs, bacon, toast\nLunch: Grilled cheese, tomato soup\nDinner: Baked chicken, mashed potatoes, green beans";

// Menu intake batches for one service date: menus that arrived by email
// (routes/email_inbound.py) or were pasted here. Both go through the same
// parser (menu_ingest.py::create_menu_upload) and land as drafts; approving
// a batch publishes its items and replaces any earlier published items for
// the same meals on that date.
export default function MenuUploadsPanel({ date, refreshKey, onChanged }) {
  const [uploads, setUploads] = useState([]);
  const [itemsById, setItemsById] = useState({});
  const [open, setOpen] = useState(false);
  const [rawText, setRawText] = useState("");

  const load = async () => {
    try {
      const [{ data: ups }, { data: items }] = await Promise.all([
        api.get("/menu/uploads", { params: { service_date: date } }),
        api.get("/menu", { params: { date } }),
      ]);
      setUploads(ups);
      setItemsById(Object.fromEntries(items.map((i) => [i.menu_id, i])));
    } catch { setUploads([]); }
  };
  useEffect(() => { load(); }, [date, refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps

  const ingest = async (e) => {
    e.preventDefault();
    try {
      await api.post("/menu/ingest/paste", { service_date: date, raw_text: rawText });
      toast.success("Menu added as a draft — review it below, then publish");
      setOpen(false);
      setRawText("");
      load();
      onChanged?.();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Could not read that menu");
    }
  };

  const approve = async (uploadId) => {
    try {
      await api.post(`/menu/uploads/${uploadId}/approve`);
      toast.success("Published — residents and Aria see this menu now");
      load();
      onChanged?.();
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not publish"); }
  };

  return (
    <div className="mt-8 pt-6 border-t border-caos-line" data-testid="menu-uploads">
      <div className="flex flex-wrap justify-between items-start gap-3 mb-3">
        <div>
          <h3 className="font-display text-lg font-medium text-caos-forest">Menus received for {date}</h3>
          <p className="text-caos-mute text-xs mt-1">
            Emailed or pasted menus arrive as drafts. Nothing reaches residents until you publish it.
          </p>
        </div>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button variant="outline" className="border-2 rounded-full" data-testid="menu-paste-btn">Paste a menu</Button>
          </DialogTrigger>
          <DialogContent className="max-w-lg">
            <DialogHeader><DialogTitle className="font-display">Paste the menu for {date}</DialogTitle></DialogHeader>
            <form onSubmit={ingest} className="space-y-3">
              <div>
                <Label>Menu text</Label>
                <Textarea rows={8} required placeholder={EXAMPLE} value={rawText} onChange={(e) => setRawText(e.target.value)} data-testid="menu-paste-body" />
                <p className="text-xs text-caos-mute mt-1">Start each meal with "Breakfast:", "Lunch:" or "Dinner:"; separate dishes with commas or new lines.</p>
              </div>
              <DialogFooter><Button type="submit" className="bg-caos-forest" data-testid="menu-paste-submit">Add as draft</Button></DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <div className="space-y-2">
        {uploads.map((u) => (
          <div key={u.upload_id} className="p-3 rounded-xl border border-caos-line" data-testid={`upload-row-${u.upload_id}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium">
                  {u.source === "email" ? "Emailed menu" : "Pasted menu"} · {u.item_ids.length} item{u.item_ids.length === 1 ? "" : "s"}
                  <span className="text-caos-mute font-normal"> · {new Date(u.created_at).toLocaleString()}</span>
                </div>
                {u.parse_status === "needs_review" && (
                  <div className="text-xs text-caos-terracotta">Check before publishing — {u.parse_notes}</div>
                )}
                <ul className="mt-1 text-sm text-caos-ink/90">
                  {u.item_ids.map((id) => itemsById[id]).filter(Boolean).map((i) => (
                    <li key={i.menu_id}><span className="uppercase text-[10px] tracking-wider text-caos-mute mr-2">{i.meal_period}</span>{i.item_name}</li>
                  ))}
                </ul>
                <details className="mt-1">
                  <summary className="text-xs text-caos-mute cursor-pointer">Original text</summary>
                  <pre className="whitespace-pre-wrap text-xs text-caos-mute mt-1">{u.raw_text}</pre>
                </details>
              </div>
              <div className="shrink-0">
                {u.status === "approved"
                  ? <Badge className="bg-caos-moss text-white">PUBLISHED</Badge>
                  : <Button size="sm" className="bg-caos-forest" onClick={() => approve(u.upload_id)} disabled={!u.item_ids.length} data-testid={`approve-upload-${u.upload_id}`}>Publish menu</Button>}
              </div>
            </div>
          </div>
        ))}
        {uploads.length === 0 && <div className="text-center text-caos-mute py-4 text-sm">No emailed or pasted menus for this date.</div>}
      </div>
    </div>
  );
}
