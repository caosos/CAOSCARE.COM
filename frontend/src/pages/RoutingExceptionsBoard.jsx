import React, { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { RefreshCw, Send } from "lucide-react";
import { toast } from "sonner";
import RequestDetailDialog from "./RequestDetailDialog";
import { CLASS_LABEL, CLASS_ORDER, ageText, latestActionText } from "../lib/routingExceptions";

/**
 * Requests whose handoff to a department is in trouble: not delivered, unassigned, overdue, or a failed handoff.
 * One read over the canonical requests, notifications and receipts (GET /ops/routing-exceptions). Recovery uses
 * the normal paths: open the request to assign or act, or re-send the department notification (receipted).
 */
export default function RoutingExceptionsBoard() {
  const [data, setData] = useState(null);
  const [kind, setKind] = useState("");
  const [includeReview, setIncludeReview] = useState(false);
  const [error, setError] = useState(false);
  const [openId, setOpenId] = useState(null);

  const load = useCallback(() => {
    setError(false);
    api.get("/ops/routing-exceptions", { params: { kind: kind || undefined, include_review: includeReview } })
      .then(({ data: d }) => setData(d)).catch(() => setError(true));
  }, [kind, includeReview]);
  useEffect(() => { load(); const t = setInterval(load, 20000); return () => clearInterval(t); }, [load]);

  const renotify = async (id) => {
    try {
      const { data: r } = await api.post(`/ops/routing-exceptions/${id}/renotify`);
      toast.success(r.delivery?.reached ? "Department notified" : `Re-sent: ${r.delivery?.label || r.delivery?.state}`);
      load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Could not re-send"); }
  };

  return (
    <div className="space-y-4" data-testid="routing-exceptions">
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h2 className="font-display text-2xl font-medium text-caos-forest">Routing exceptions</h2>
          <p className="text-caos-mute text-sm mt-1">Requests that may not reach or move through their department. Open one to assign it or act; "Re-send" repeats the department notification and records it.</p>
        </div>
        <Button variant="ghost" onClick={load} data-testid="rx-refresh"><RefreshCw className="w-4 h-4 mr-2" /> Refresh</Button>
      </div>
      <div className="flex flex-wrap gap-2 items-center" data-testid="rx-filters">
        <button className={`px-3 py-1 rounded-full border-2 text-sm ${!kind ? "bg-caos-forest text-white border-caos-forest" : "border-caos-line"}`} onClick={() => setKind("")} data-testid="rx-kind-all">All ({data?.total ?? "…"})</button>
        {CLASS_ORDER.map((c) => (
          <button key={c} className={`px-3 py-1 rounded-full border-2 text-sm ${kind === c ? "bg-caos-forest text-white border-caos-forest" : "border-caos-line"}`} onClick={() => setKind(c)} data-testid={`rx-kind-${c}`}>
            {CLASS_LABEL[c]} ({data?.counts?.[c] ?? "…"})
          </button>
        ))}
        <label className="flex items-center gap-2 text-sm text-caos-mute cursor-pointer ml-2">
          <input type="checkbox" checked={includeReview} onChange={(e) => setIncludeReview(e.target.checked)} data-testid="rx-include-review" /> Include older records
        </label>
      </div>
      {error && <Card className="p-4 text-sm text-red-700" data-testid="rx-error">Could not load routing exceptions. <Button size="sm" variant="outline" className="ml-2 h-7" onClick={load}>Try again</Button></Card>}
      {data && data.items.length === 0 && <Card className="p-8 text-center text-caos-mute italic" data-testid="rx-empty">No routing exceptions{kind ? ` of this kind` : ""}.</Card>}
      <div className="space-y-2">
        {data?.items.map((r) => (
          <Card key={r.task_id} className="p-4 border-2 border-caos-line" data-testid={`rx-row-${r.task_id}`}>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div className="min-w-0">
                <div className="flex flex-wrap gap-1.5 items-center">
                  {r.classes.map((c) => <Badge key={c} className={c === "failed_handoff" || c === "undelivered" ? "bg-[#FDECE9] text-[#98392F] border border-[#B6463A]" : "bg-[#FDF3E3] text-[#8B5A20] border border-[#D28D38]"} data-testid={`rx-class-${r.task_id}-${c}`}>{CLASS_LABEL[c]}</Badge>)}
                  <span className="text-xs text-caos-mute uppercase">{r.department}</span>
                  {r.simulated && <Badge variant="outline" className="text-[10px]">SIM</Badge>}
                  {r.currency?.bucket === "review" && <Badge variant="outline" className="text-[10px]">older</Badge>}
                </div>
                <div className="font-semibold text-caos-forest mt-1 break-words">{r.what}</div>
                <div className="text-xs text-caos-mute mt-0.5">{[r.resident_name, r.room ? `Room ${r.room}` : null, `open ${ageText(r.age_seconds)}`, r.owner ? `owner ${r.owner}` : "no owner", r.times_asked > 1 ? `asked ${r.times_asked}x` : null].filter(Boolean).join(" · ")}</div>
                <div className="text-xs mt-1" data-testid={`rx-latest-${r.task_id}`}>Latest: {latestActionText(r.latest_action)}</div>
                <div className={`text-xs mt-0.5 ${r.delivery?.reached ? "text-caos-mute" : "text-caos-terracotta font-semibold"}`} data-testid={`rx-delivery-${r.task_id}`}>{r.delivery?.label} · {r.notification_attempts} attempt{r.notification_attempts === 1 ? "" : "s"} · {r.receipts_count} receipt{r.receipts_count === 1 ? "" : "s"}{r.escalation?.refused_steps ? ` · ${r.escalation.refused_steps} refused step${r.escalation.refused_steps === 1 ? "" : "s"}` : ""}</div>
              </div>
              <div className="flex gap-2">
                {!r.delivery?.reached && !r.simulated && <Button size="sm" variant="outline" className="border-2" onClick={() => renotify(r.task_id)} data-testid={`rx-renotify-${r.task_id}`}><Send className="w-3.5 h-3.5 mr-1" /> Re-send</Button>}
                <Button size="sm" className="bg-caos-forest" onClick={() => setOpenId(r.task_id)} data-testid={`rx-open-${r.task_id}`}>Open</Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
      <RequestDetailDialog taskId={openId} open={!!openId} onOpenChange={(o) => { if (!o) setOpenId(null); }} onChange={load} />
    </div>
  );
}
