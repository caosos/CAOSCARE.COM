import React from "react";

// Admin view of a department queue: how work reaches this department and who
// can take it. If nobody works in the department, nobody can claim its work
// and the Assign list is empty, so say that plainly with the fix.
export default function DepartmentDispatchNote({ label, roster, rosterState }) {
  return (
    <div className="text-sm rounded-lg border border-caos-line p-3 space-y-1" data-testid="dept-dispatch-note">
      <div className="text-caos-ink">
        <b>How work reaches {label}:</b> requests from residents (Aria or the room screen), the front desk, or staff are routed here,
        and the department's staff are notified (each request shows whether that notice was delivered).
        A staff member takes a request with <b>Claim</b>, or you hand it to someone with <b>Assign to…</b>.
      </div>
      {rosterState === "error" && <div className="text-caos-terracotta" data-testid="dept-roster-error">Could not load who works in {label}.</div>}
      {rosterState === "ok" && roster.length === 0 && (
        <div className="text-caos-terracotta" data-testid="dept-roster-empty">
          No one works in {label} yet with a staff account, so no person can claim this work and the Assign list is empty
          (simulated workers, if any, are listed below and do their own work).
          Add staff in Departments &amp; staff → Users &amp; access and set their department to {label}.
        </div>
      )}
      {rosterState === "ok" && roster.length > 0 && (
        <div className="text-caos-mute" data-testid="dept-roster">Works in {label}: {roster.map((u) => u.name).join(", ")}.</div>
      )}
    </div>
  );
}
