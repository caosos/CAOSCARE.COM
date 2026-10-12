import React from "react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Activity, Heart } from "lucide-react";
import { CATEGORY_META, fmtSeconds } from "../lib/clinician";
import { isLikelyStale } from "../lib/alertsView";

// Recent assistance events for one resident. Each row opens the same alert
// detail / close-out dialog the Alerts board uses; open records older than 72 h
// are marked "older, needs review" (likely test debris), never hidden.
export default function ClinicianRecentEvents({ events = [], summary, summaryState, onOpen }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card className="p-5 border-caos-line md:col-span-2" data-testid="clinician-recent">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-3">
          <Activity className="w-4 h-4 text-caos-forest" /> Recent events
        </div>
        {events.length === 0 ? (
          <p className="text-caos-mute italic text-sm">No events yet.</p>
        ) : (
          <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1">
            {events.map((e) => {
              const meta = CATEGORY_META[e.category] || { label: e.category, color: "#7A6B56" };
              return (
                <button type="button" key={e.alert_id} onClick={() => onOpen(e.alert_id)} title="Open this event and its close-out"
                  data-testid={`event-${e.alert_id}`} className="w-full text-left flex items-start gap-3 p-3 bg-caos-ambient/40 hover:bg-caos-ambient rounded-lg">
                  <div className="w-1.5 self-stretch rounded-full" style={{ backgroundColor: meta.color }} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <Badge variant="outline" className="uppercase text-[10px] tracking-wider">{meta.label}</Badge>
                      <span className="text-xs text-caos-mute">{new Date(e.created_at).toLocaleString()}</span>
                      <SeverityBadge sev={e.severity} />
                      {e.status !== "resolved" && <Badge className="bg-caos-amber/30 text-caos-forest text-[10px] uppercase tracking-wider">{e.status}</Badge>}
                      {isLikelyStale(e) && <Badge className="bg-caos-mute/20 text-caos-mute text-[10px] uppercase" data-testid={`event-older-${e.alert_id}`}>older, needs review</Badge>}
                    </div>
                    {e.ai_summary && <p className="text-sm text-caos-forest mt-1 leading-snug">{e.ai_summary}</p>}
                    {e.resident_stated_reason && (
                      <p className="text-xs text-caos-mute mt-0.5 italic">"{e.resident_stated_reason}"</p>
                    )}
                    {e.outcome && <p className="text-xs text-caos-ink/80 mt-1">→ {e.outcome}</p>}
                    <div className="text-[10px] text-caos-mute mt-1 font-mono">
                      response {fmtSeconds(e.response_seconds)} · duration {fmtSeconds(e.duration_seconds)}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </Card>

      <Card className="p-5 border-caos-line" data-testid="clinician-narrative">
        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-caos-mute mb-3">
          <Heart className="w-4 h-4 text-caos-forest" /> Summary
        </div>
        {summaryState === "error" && <p className="text-caos-terracotta text-sm" data-testid="clinician-summary-error">Could not load the summary.</p>}
        {summaryState === "loading" && <p className="text-caos-mute text-sm">Loading…</p>}
        {summaryState === "ok" && (summary ? <p className="text-sm text-caos-forest leading-relaxed" data-testid="clinician-summary">{summary}</p>
          : <p className="text-caos-mute italic text-sm">No summary for this resident yet.</p>)}
        <p className="text-[10px] text-caos-mute mt-3">Built from this resident's records (recent alerts, pinned notes, last known place), the same text as "Brief".</p>
      </Card>
    </div>
  );
}

function SeverityBadge({ sev }) {
  const map = {
    emergency: "bg-caos-terracotta text-white",
    assist:    "bg-caos-forest/15 text-caos-forest border border-caos-forest",
    comfort:   "bg-caos-mute/15 text-caos-ink",
  };
  return <Badge className={`uppercase text-[10px] tracking-widest ${map[sev] || ""}`}>{sev}</Badge>;
}

