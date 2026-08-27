import React, { useEffect, useState } from "react";

/**
 * The resident Home screen's "at a glance" identity strip - name, room,
 * and live local time. Deliberately small/compact: this is context, not
 * the main event (the CALL FOR HELP / talk actions and the info cards own
 * that role) - see docs/reports for the 2026-08-27 resident-home rationale.
 */
export default function ProfileHeader({ resident, kiosk, facilityTz }) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 30000);
    return () => clearInterval(t);
  }, []);

  const name = resident?.preferred_name || resident?.name?.split(" ")[0] || "";
  const timeStr = (() => {
    try {
      return new Intl.DateTimeFormat("en-US", {
        timeZone: facilityTz || undefined,
        weekday: "long", month: "long", day: "numeric",
        hour: "numeric", minute: "2-digit",
      }).format(now);
    } catch {
      return now.toLocaleString();
    }
  })();

  return (
    <div
      data-testid="resident-profile-header"
      className="w-full max-w-4xl mx-auto flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-caos-line bg-white/60 px-6 py-4 mb-8"
    >
      <div>
        <p className="font-display text-2xl font-semibold text-caos-forest leading-tight">
          {name ? `${name}'s room` : "Your room"}
        </p>
        <p className="text-sm text-caos-mute">Room {kiosk?.room || "—"}</p>
      </div>
      <p className="text-sm md:text-base text-caos-mute text-right">{timeStr}</p>
    </div>
  );
}
