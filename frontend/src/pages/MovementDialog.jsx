import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Badge } from "../components/ui/badge";
import { MapPin, Clock } from "lucide-react";
import { toast } from "sonner";

// Zone-visit timeline for one resident. Folded into the Resident hub
// (ResidentRecordDialog -> "Movement" section); it used to be its own dialog
// opened from a button in the Residents row.

function humanTime(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}
function duration(fromIso, untilIso) {
  if (!fromIso || !untilIso) return "";
  const s = Math.floor((new Date(untilIso) - new Date(fromIso)) / 1000);
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
}

export default function MovementPanel({ resident }) {
  const [data, setData] = useState(null);
  const [hours, setHours] = useState(24);

  useEffect(() => {
    if (!resident) return;
    setData(null);
    (async () => {
      try {
        const { data: d } = await api.get(`/residents/${resident.resident_id}/movement?hours=${hours}`);
        setData(d);
      } catch {
        toast.error("Could not load movement");
      }
    })();
  }, [resident, hours]);

  return (
    <div data-testid="hub-movement">
      <div className="flex items-center gap-2 mb-4 flex-wrap">
        <Clock className="w-4 h-4 text-caos-mute" />
        <span className="text-caos-mute text-sm">Window:</span>
        {[24, 72, 168].map((h) => (
          <button
            key={h}
            onClick={() => setHours(h)}
            className={`px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider transition-colors ${
              hours === h ? "bg-caos-forest text-white" : "bg-caos-ambient text-caos-forest hover:bg-caos-forest/10"
            }`}
            data-testid={`movement-window-${h}`}
          >
            {h === 24 ? "24 hours" : h === 72 ? "3 days" : "7 days"}
          </button>
        ))}
        <span className="ml-auto text-caos-mute text-sm">
          {data ? `${data.total_pings} pings · ${data.visits.length} visits` : ""}
        </span>
      </div>

      {!data && <div className="text-center py-10 text-caos-mute">Loading…</div>}

      {data && data.visits.length === 0 && (
        <div className="text-center py-10 text-caos-mute">No location data in this window.</div>
      )}

      {data && data.visits.length > 0 && (
        <div className="relative border-l-2 border-caos-line ml-2 pl-5 space-y-4">
          {[...data.visits].reverse().map((v, i) => (
            <div key={i} className="relative" data-testid={`visit-${i}`}>
              <div className="absolute -left-[1.65rem] top-1 w-4 h-4 rounded-full bg-caos-forest border-4 border-caos-bone" />
              <div className="flex items-center gap-2">
                <MapPin className="w-4 h-4 text-caos-forest" />
                <span className="font-semibold text-caos-forest">{v.zone}</span>
                <Badge variant="outline" className="text-xs">{v.pings} pings</Badge>
                {v.source && <Badge variant="outline" className="text-xs">{v.source}</Badge>}
              </div>
              <p className="text-caos-mute text-sm mt-1">
                {humanTime(v.from)} — {humanTime(v.until)}
                {v.from !== v.until && <span className="ml-2 font-mono">· {duration(v.from, v.until)}</span>}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
