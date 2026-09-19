import React, { useEffect, useState } from "react";
import { CalendarDays, Megaphone, UtensilsCrossed } from "lucide-react";
import { API } from "../../lib/api";

// Shared facility content (menu/activities/notices) has one authoritative
// source: whichever backend the facility's real kitchen/activities staff
// actually enter it into via the real ingestion pathways
// (menu_ingest.py/schedule_ingest.py) - today that's production. A room
// node (this EliteDesk dev rig included) reads that same content rather
// than maintaining its own independently-seeded copy. Everything else
// (resident identity, conversations, device control, RF/pendant, Aria
// voice) stays fully local - only these two PUBLIC, unauthenticated,
// non-resident-specific reads are affected. REACT_APP_FACILITY_CONTENT_URL
// is unset in every real deployment (falls back to the local API, so
// production/staging behavior is completely unchanged); set it only in a
// local dev .env (gitignored, never committed) to point a local/dev room
// node's shared-content panel at the real facility's live data instead of
// requiring a second, separately-maintained local seed.
const FACILITY_CONTENT_URL = (process.env.REACT_APP_FACILITY_CONTENT_URL || "").trim().replace(/\/+$/, "");
const FACILITY_API = FACILITY_CONTENT_URL ? `${FACILITY_CONTENT_URL}/api` : API;

const MEAL_ORDER = ["breakfast", "lunch", "dinner"];
const MEAL_LABEL = { breakfast: "Breakfast", lunch: "Lunch", dinner: "Dinner" };

/**
 * "What's going on today" - activities + facility notices (same
 * ScheduleItem domain/endpoint Aria's get_todays_schedule tool already
 * uses, see routes/schedule.py) plus today's approved menu, ALL THREE
 * meals when available - not just whichever meal happens to sort first
 * in the array (a real defect this replaces: a resident with dinner
 * already posted alongside breakfast/lunch would never see dinner here
 * at all).
 */
export default function TodayPanel({ pollMs = 60000 }) {
  const [schedule, setSchedule] = useState([]);
  const [menu, setMenu] = useState([]);

  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const [s, m] = await Promise.all([
          fetch(`${FACILITY_API}/schedule/public/today`).then((r) => (r.ok ? r.json() : [])),
          fetch(`${FACILITY_API}/menu/public/today`).then((r) => (r.ok ? r.json() : [])),
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
  // Every meal present today, in a fixed, understandable order - not just
  // whichever the API happened to return first.
  const meals = MEAL_ORDER
    .map((period) => ({ period, items: menu.filter((m) => m.meal_period === period) }))
    .filter((m) => m.items.length > 0);

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
      {meals.length > 0 && (
        <div className="rounded-2xl border-2 border-caos-line bg-white p-4 md:col-span-2">
          <p className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.2em] text-caos-mute mb-2">
            <UtensilsCrossed className="w-4 h-4" /> Today's menu
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {meals.map(({ period, items }) => (
              <div key={period}>
                <p className="text-xs font-bold uppercase tracking-wider text-caos-forest mb-1">
                  {MEAL_LABEL[period] || period}
                </p>
                <p className="text-sm text-caos-ink/90">{items.map((m) => m.item_name).join(", ")}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
