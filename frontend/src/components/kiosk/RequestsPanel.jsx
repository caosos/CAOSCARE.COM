import React, { useEffect, useState } from "react";
import { Wrench, Sparkles, Stethoscope, Car, HelpCircle, CheckCircle2 } from "lucide-react";
import { API } from "../../lib/api";

const CATEGORY_ICON = {
  maintenance: Wrench, housekeeping: Sparkles, nursing: Stethoscope, transportation: Car,
};

const STATUS_LABEL = {
  pending: "Received", in_progress: "In progress", completed: "Completed", skipped: "Closed",
};

/**
 * Human-readable request/service cards for the resident Home screen - the
 * SAME underlying StaffTask state Aria reads via check_request_status
 * (routes/resident_requests.py's _resident_safe_view), so a staff update
 * and Aria's spoken answer can never show the resident two different
 * truths. Polls rather than pushing - simplest mechanism that still feels
 * "alive" without new realtime infrastructure (see 2026-08-27 report).
 */
export default function RequestsPanel({ residentId, room }) {
  const [items, setItems] = useState([]);

  useEffect(() => {
    if (!residentId && !room) return;
    let stop = false;
    const load = async () => {
      try {
        const qs = residentId ? `resident_id=${encodeURIComponent(residentId)}` : `room=${encodeURIComponent(room)}`;
        const r = await fetch(`${API}/tasks/resident-request/mine?${qs}`);
        if (!r.ok || stop) return;
        const data = await r.json();
        // Recently-completed items stay visible briefly for closure, but
        // don't clutter the screen indefinitely once resolved.
        const relevant = data.filter((t) => t.status !== "completed" && t.status !== "skipped").concat(
          data.filter((t) => t.status === "completed" || t.status === "skipped").slice(0, 1)
        );
        setItems(relevant);
      } catch { /* silent - keep last known state on a transient network blip */ }
    };
    load();
    const t = setInterval(load, 20000);
    return () => { stop = true; clearInterval(t); };
  }, [residentId, room]);

  if (!items.length) return null;

  return (
    <div className="w-full max-w-4xl mx-auto mb-8" data-testid="resident-requests-panel">
      <p className="text-xs font-bold uppercase tracking-[0.3em] text-caos-mute mb-3">Your requests</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {items.map((t) => {
          const Icon = CATEGORY_ICON[t.category] || HelpCircle;
          const done = t.status === "completed";
          return (
            <div
              key={t.task_id}
              data-testid={`request-card-${t.task_id}`}
              className={`rounded-2xl border-2 p-4 ${done ? "border-caos-line bg-white/40 opacity-70" : "border-caos-line bg-white"}`}
            >
              <div className="flex items-start gap-3">
                {done ? <CheckCircle2 className="w-6 h-6 text-caos-forest shrink-0 mt-0.5" /> : <Icon className="w-6 h-6 text-caos-forest shrink-0 mt-0.5" />}
                <div className="min-w-0 flex-1">
                  <p className="font-display font-semibold text-caos-forest leading-snug">{t.what_for || "Request"}</p>
                  <p className="text-xs uppercase tracking-wider text-caos-mute mt-1">
                    {t.category.replace(/_/g, " ")} · {STATUS_LABEL[t.status] || t.status}
                  </p>
                  {t.assigned_to_name && (
                    <p className="text-sm text-caos-ink/80 mt-1">Assigned: {t.assigned_to_name}</p>
                  )}
                  {(t.scheduled_date || t.scheduled_time_label) ? (
                    <p className="text-sm text-caos-ink/80 mt-1">
                      Planned: {[t.scheduled_time_label, t.scheduled_date].filter(Boolean).join(" · ")}
                    </p>
                  ) : !done && (
                    <p className="text-sm text-caos-mute italic mt-1">No service time scheduled yet</p>
                  )}
                  {t.latest_update && (
                    <p className="text-sm text-caos-ink/70 mt-1 border-t border-caos-line pt-1">{t.latest_update}</p>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
