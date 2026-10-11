import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Badge } from "./ui/badge";
import { detailsLine } from "../lib/appointmentDetails";
import { groupByDay, timeOf, rideLineFor, lifecycleLabel } from "../lib/upcomingSchedule";
import { conflictSummary } from "../lib/scheduleConflict";

/**
 * Date-ordered upcoming schedule for a department's staff — a READ over the
 * same StaffTask rows the queue works (GET /tasks/upcoming, backend-ordered by
 * facility day → planned time → created). Shows the planned time, who/what/
 * where, lifecycle and the linked ride's real facts. Nothing is edited here;
 * the queue is where work changes.
 */
export default function UpcomingSchedule({ department, days = 14, reloadKey }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  useEffect(() => {
    let stop = false;
    setError(false);
    const load = () => api.get(`/tasks/upcoming`, { params: { department, days } })
      .then(({ data: d }) => { if (!stop) { setData(d); setError(false); } })
      .catch(() => { if (!stop) setError(true); });
    load();
    const id = setInterval(load, 20000);   // the queue next to it changes plans; keep this read current
    return () => { stop = true; clearInterval(id); };
  }, [department, days, reloadKey]);

  const groups = data ? groupByDay(data.items, data.today) : [];
  return (
    <div className="rounded-2xl border border-caos-line bg-white p-4" data-testid="upcoming-schedule">
      <div className="flex items-baseline justify-between mb-2">
        <h3 className="font-display text-lg font-medium text-caos-forest">Upcoming</h3>
        <span className="text-xs text-caos-mute">next {days} days · facility time</span>
      </div>
      {error && <div className="text-sm text-red-700" data-testid="upcoming-error">Could not load the upcoming schedule.</div>}
      {!error && !data && <div className="text-sm text-caos-mute">Loading…</div>}
      {data && !groups.length && <div className="text-sm text-caos-mute" data-testid="upcoming-empty">Nothing planned in the next {days} days.</div>}
      {groups.map((g) => (
        <div key={g.date || "none"} className="mb-3" data-testid={`upcoming-day-${g.date}`}>
          <div className="text-xs uppercase tracking-widest text-caos-mute mb-1">{g.label}</div>
          <ul className="space-y-2">
            {g.items.map((it) => (
              <li key={it.task_id} className="rounded-xl border border-caos-line p-3 text-sm" data-testid={`upcoming-item-${it.task_id}`}>
                <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                  <span className="font-semibold text-caos-forest min-w-[5.5rem]" data-testid={`upcoming-time-${it.task_id}`}>{timeOf(it)}</span>
                  <span className="flex-1 min-w-0 break-words">{it.resident_name || "Resident"}{it.room ? ` (Rm ${it.room})` : ""} — {it.resident_words || it.description || it.title}</span>
                  <Badge className="bg-caos-sand text-caos-forest" data-testid={`upcoming-status-${it.task_id}`}>{lifecycleLabel(it)}</Badge>
                </div>
                {detailsLine(it) && <div className="text-caos-ink/80 mt-1" data-testid={`upcoming-details-${it.task_id}`}>{detailsLine(it)}</div>}
                {rideLineFor(it) && <div className="text-caos-ink/80 mt-1" data-testid={`upcoming-ride-${it.task_id}`}>{rideLineFor(it)}</div>}
                {conflictSummary({ checked: !it.conflict_check, reason: it.conflict_check, conflicts: it.conflicts }) && (
                  <div className={`mt-1 ${it.conflicts?.length ? "text-amber-800 font-medium" : "text-caos-mute"}`} data-testid={`upcoming-conflict-${it.task_id}`}>
                    {conflictSummary({ checked: !it.conflict_check, reason: it.conflict_check, conflicts: it.conflicts })}
                  </div>
                )}
                {it.assigned_name && <div className="text-xs text-caos-mute mt-1">With staff: {it.assigned_name}</div>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}
