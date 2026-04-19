import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Radio } from "lucide-react";

const URGENCY_STYLE = {
  code: "bg-caos-terracotta text-white",
  stat: "bg-caos-amber text-white",
  page: "bg-caos-forest text-white",
  info: "bg-caos-line text-caos-forest",
};

function timeAgo(iso) {
  if (!iso) return "";
  const s = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h`;
  return `${Math.floor(s / 86400)}d`;
}

export default function PagerFeedCard() {
  const [items, setItems] = useState([]);

  const fetchAll = async () => {
    try { const { data } = await api.get("/paging/feed", { params: { minutes: 30 } }); setItems(data); }
    catch { /* silent */ }
  };
  useEffect(() => {
    fetchAll();
    const t = setInterval(fetchAll, 3000);
    return () => clearInterval(t);
  }, []);

  return (
    <Card className="border-caos-line bg-white p-5" data-testid="pager-feed-card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-display text-xl font-medium text-caos-forest flex items-center gap-2">
          <Radio className="w-5 h-5" /> Facility pages
        </h3>
        <span className="text-xs font-bold uppercase tracking-widest text-caos-mute">Last 30 min</span>
      </div>

      <div className="space-y-2" data-testid="pager-feed-list">
        {items.map((p) => (
          <div key={p.page_id} data-testid={`pager-row-${p.page_id}`} className="flex items-start gap-3 p-3 rounded-xl border border-caos-line hover:bg-caos-ambient/40">
            <Badge className={`uppercase tracking-wider text-[10px] font-bold ${URGENCY_STYLE[p.urgency] || URGENCY_STYLE.page}`}>{p.urgency}</Badge>
            <div className="min-w-0 flex-1">
              <div className="font-semibold text-caos-forest truncate">{p.message}</div>
              <div className="text-xs text-caos-mute">
                {p.resident_name && <span>{p.resident_name} · </span>}
                {p.room && <span>Rm {p.room} · </span>}
                <span className="uppercase tracking-wider">{p.source.replace("_", " ")}</span>
              </div>
            </div>
            <span className="text-xs text-caos-mute shrink-0 tabular-nums">{timeAgo(p.created_at)}</span>
          </div>
        ))}
        {items.length === 0 && (
          <div className="text-center text-caos-mute py-4 italic text-sm">No pages in the last 30 minutes.</div>
        )}
      </div>
    </Card>
  );
}
