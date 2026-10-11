import React, { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import { API } from "../../lib/api";
import { groupByDay, timeOf, rideLineFor } from "../../lib/upcomingSchedule";

/**
 * "Coming up" on the resident Home screen: the resident's own planned
 * requests in date order (GET /tasks/resident-request/upcoming), the same
 * rows and the same resident-safe view Aria speaks from. Polls like the
 * other panels; nothing is edited here.
 */
export default function UpcomingPanel({ residentId, room, days = 14 }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!residentId && !room) return;
    let stop = false;
    const load = async () => {
      try {
        const qs = residentId ? `resident_id=${encodeURIComponent(residentId)}` : `room=${encodeURIComponent(room)}`;
        const r = await fetch(`${API}/tasks/resident-request/upcoming?${qs}&days=${days}`);
        if (!r.ok || stop) return;
        setData(await r.json());
      } catch { /* keep the last known state on a transient blip */ }
    };
    load();
    const id = setInterval(load, 30000);
    return () => { stop = true; clearInterval(id); };
  }, [residentId, room, days]);

  if (!data || !data.items?.length) return null;
  const groups = groupByDay(data.items, data.today);
  return (
    <section className="mb-10" data-testid="kiosk-upcoming">
      <h2 className="font-display text-2xl text-caos-forest mb-4 flex items-center gap-2"><CalendarDays className="w-6 h-6" /> Coming up</h2>
      {groups.map((g) => (
        <div key={g.date} className="mb-4" data-testid={`kiosk-upcoming-day-${g.date}`}>
          <div className="text-lg text-caos-mute mb-2">{g.label}</div>
          <ul className="space-y-3">
            {g.items.map((t) => (
              <li key={t.task_id} className="rounded-2xl border-2 border-caos-line bg-white p-4" data-testid={`kiosk-upcoming-${t.task_id}`}>
                <div className="text-xl font-semibold text-caos-forest">{timeOf(t)} <span className="font-normal text-caos-ink">— {t.what_for}</span></div>
                {(t.provider_name || t.discipline) && <p className="text-lg text-caos-ink/80 mt-1">With: {[t.provider_name, t.discipline && `(${t.discipline})`].filter(Boolean).join(" ")}</p>}
                {t.location && <p className="text-lg text-caos-ink/80 mt-1">Where: {t.location}</p>}
                {rideLineFor(t) && <p className="text-lg text-caos-ink/80 mt-1">{rideLineFor(t)}</p>}
              </li>
            ))}
          </ul>
        </div>
      ))}
    </section>
  );
}
