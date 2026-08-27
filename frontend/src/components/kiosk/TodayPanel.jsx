import React, { useEffect, useState } from "react";
import { CalendarDays, Megaphone, UtensilsCrossed } from "lucide-react";
import { API } from "../../lib/api";

/**
 * "What's going on today" - activities + facility notices (same
 * ScheduleItem domain/endpoint Aria's get_todays_schedule tool already
 * uses, see routes/schedule.py) plus today's approved menu highlights.
 * Extending the existing schedule domain rather than a parallel
 * announcements feature - see 2026-08-27 report.
 */
export default function TodayPanel({ pollMs = 60000 }) {
  const [schedule, setSchedule] = useState([]);
  const [menu, setMenu] = useState([]);

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const [s, m] = await Promise.all([
          fetch(`${API}/schedule/public/today`).then((r) => (r.ok ? r.json() : [])),
          fetch(`${API}/menu/public/today`).then((r) => (r.ok ? r.json() : [])),
        ]);
        if (stop) return;
        setSchedule(s);
        setMenu(m);
      } catch { /* silent */ }
    };
    load();
    const t = setInterval(load, pollMs);
    return () => { stop = true; clearInterval(t); };
  }, [pollMs]);

  const notices = schedule.filter((i) => i.category === "facility_note");
  const activities = schedule.filter((i) => i.category !== "facility_note");
  const nextMeal = menu[0]?.meal_period;
  const mealLines = menu.filter((m) => m.meal_period === nextMeal);

  if (!schedule.length && !menu.length) return null;

  return (
    <div className="w-full max-w-4xl mx-auto mb-8 grid grid-cols-1 md:grid-cols-2 gap-3" data-testid="resident-today-panel">
      {notices.length > 0 && (
        <div className="rounded-2xl border-2 border-caos-amber/60 bg-caos-amber/10 p-4 md:col-span-2">
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-caos-forest mb-2">
            <Megaphone className="w-4 h-4" /> Announcements
          </p>
          {notices.map((n) => (
            <p key={n.title} className="text-sm text-caos-ink/90 leading-snug">
              {n.time_label && <span className="font-semibold">{n.time_label}: </span>}
              {n.title}{n.description ? ` — ${n.description}` : ""}
            </p>
          ))}
        </div>
      )}
      {activities.length > 0 && (
        <div className="rounded-2xl border-2 border-caos-line bg-white p-4">
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-caos-mute mb-2">
            <CalendarDays className="w-4 h-4" /> Today's activities
          </p>
          <ul className="space-y-1">
            {activities.map((a) => (
              <li key={a.title} className="text-sm text-caos-ink/90">
                {a.time_label && <span className="font-semibold">{a.time_label}: </span>}{a.title}
              </li>
            ))}
          </ul>
        </div>
      )}
      {mealLines.length > 0 && (
        <div className="rounded-2xl border-2 border-caos-line bg-white p-4">
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-caos-mute mb-2">
            <UtensilsCrossed className="w-4 h-4" /> {nextMeal ? nextMeal[0].toUpperCase() + nextMeal.slice(1) : "Meal"}
          </p>
          <p className="text-sm text-caos-ink/90">{mealLines.map((m) => m.item_name).join(", ")}</p>
        </div>
      )}
    </div>
  );
}
