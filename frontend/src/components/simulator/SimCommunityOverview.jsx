import React from "react";
import { Card } from "../ui/card";
import { Badge } from "../ui/badge";

const shown = (value) => (value === 0 || value ? value : "\u2014");

function Metric({ label, value, detail, testid }) {
  return (
    <div className="rounded-lg border border-caos-line bg-white p-3" data-testid={testid}>
      <dt className="text-xs font-bold uppercase tracking-widest text-caos-mute">{label}</dt>
      <dd className="mt-1 font-display text-2xl text-caos-forest">{shown(value)}</dd>
      {detail && <dd className="mt-1 text-xs text-caos-mute">{detail}</dd>}
    </div>
  );
}

function capabilityRows(items) {
  return (items || []).map((item, index) => {
    if (typeof item === "string") return { key: `${item}-${index}`, name: item, reason: null };
    return {
      key: item.id || item.key || `${item.name || item.label || "capability"}-${index}`,
      name: item.name || item.label || item.id || "Unnamed capability",
      reason: item.reason || item.detail || null,
    };
  });
}

function routineRows(routines) {
  if (Array.isArray(routines)) {
    return routines.map((row, index) => ({
      key: row.id || row.key || `${row.label || row.name || "routine"}-${index}`,
      label: row.label || row.name || row.id || "Routine",
      count: row.count,
    }));
  }
  return Object.entries(routines || {}).map(([key, count]) => ({
    key,
    label: key.replaceAll("_", " "),
    count,
  }));
}

function coverageLabel(department) {
  if (typeof department.coverage === "string") return department.coverage;
  if (department.operating_hours) {
    const hours = department.operating_hours === "24 hours" ? "Open 24 hours" : `Open ${department.operating_hours}`;
    return department.after_hours_on_call ? `${hours} · on call after hours` : hours;
  }
  if (department.coverage_24h === true) return "24-hour coverage";
  if (department.coverage_24h === false) return "Coverage gap";
  return "Coverage not reported";
}

function hasGap(department) {
  return department.status_now === "uncovered" || department.coverage_24h === false;
}

/**
 * Presentation-only summary of a living-community simulation. The caller
 * supplies canonical simulator state; this component never fetches, mutates,
 * or infers operational facts.
 */
export default function SimCommunityOverview({ community = {} }) {
  const residents = community.residents || {};
  const apartments = community.apartments || {};
  const workers = community.workers || {};
  const departments = community.departments || [];
  const routines = routineRows(community.routines);
  const shiftEvents = routineRows(community.shift_events);
  const attendance = routineRows(community.worker_attendance);
  const blocked = capabilityRows(community.blocked_capabilities);
  const unsafe = capabilityRows(community.unsafe_capabilities);

  return (
    <Card className="border-caos-line p-4 sm:p-5 space-y-5" data-testid="sim-community-overview">
      <header>
        <h2 className="font-display text-2xl text-caos-forest">Community overview</h2>
        <p className="mt-1 text-sm text-caos-mute">
          Declared simulation scale and coverage. Missing values stay unreported rather than being estimated.
        </p>
      </header>

      <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4" aria-label="Community scale">
        <Metric
          label="Burn-in residents"
          value={residents.count}
          detail={residents.burn_in_target === 0 || residents.burn_in_target
            ? `of ${residents.burn_in_target} burn-in target`
            : "Burn-in target not reported"}
          testid="sim-resident-count"
        />
        <Metric
          label="Resident target"
          value={residents.target}
          detail="Planned full-community population"
          testid="sim-resident-target"
        />
        <Metric
          label="Apartments"
          value={apartments.total}
          detail={`${shown(apartments.occupied)} occupied · ${shown(apartments.occupancy_target)} occupancy target`}
          testid="sim-apartment-count"
        />
        <Metric
          label="Workers"
          value={workers.count}
          detail="Declared simulated workforce"
          testid="sim-worker-count"
        />
      </dl>

      <section aria-labelledby="sim-department-heading">
        <h3 id="sim-department-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">
          Department coverage
        </h3>
        {!departments.length ? (
          <p className="mt-2 text-sm italic text-caos-mute">No department coverage reported.</p>
        ) : (
          <ul className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-3" data-testid="sim-department-coverage">
            {departments.map((department, index) => {
              const key = department.slug || department.id || `${department.label || "department"}-${index}`;
              const covered = !hasGap(department);
              return (
                <li key={key} className="rounded-lg border border-caos-line bg-white p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-caos-forest">
                      {department.label || department.name || department.slug || "Department"}
                    </span>
                    <Badge variant="outline" className={covered ? "text-caos-forest" : "text-caos-terracotta"}>
                      {coverageLabel(department)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-xs text-caos-mute">
                    {shown(department.worker_count)} workers
                    {department.shift_count === 0 || department.shift_count ? ` · ${department.shift_count} shifts` : ""}
                  </p>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <section aria-labelledby="sim-routines-heading">
        <h3 id="sim-routines-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">
          Routine events
        </h3>
        {!routines.length ? (
          <p className="mt-2 text-sm italic text-caos-mute">No routine counts reported.</p>
        ) : (
          <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" data-testid="sim-routine-counts">
            {routines.map((routine) => (
              <div key={routine.key} className="rounded-lg bg-caos-bone px-3 py-2">
                <dt className="text-xs capitalize text-caos-mute">{routine.label}</dt>
                <dd className="font-display text-xl text-caos-forest">{shown(routine.count)}</dd>
              </div>
            ))}
          </dl>
        )}
      </section>

      <section aria-labelledby="sim-shift-events-heading">
        <h3 id="sim-shift-events-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">
          Planned shift events
        </h3>
        {!shiftEvents.length ? (
          <p className="mt-2 text-sm italic text-caos-mute">No shift-event counts reported.</p>
        ) : (
          <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" data-testid="sim-shift-event-counts">
            {shiftEvents.map((event) => (
              <div key={event.key} className="rounded-lg bg-caos-bone px-3 py-2">
                <dt className="text-xs capitalize text-caos-mute">{event.label}</dt>
                <dd className="font-display text-xl text-caos-forest">{shown(event.count)}</dd>
              </div>
            ))}
          </dl>
        )}
        <p className="mt-2 text-xs text-caos-mute">
          These are projected clock-ins, handoffs, clock-outs, and coverage observations. Executed work requires a receipt.
        </p>
      </section>

      <section aria-labelledby="sim-attendance-heading">
        <h3 id="sim-attendance-heading" className="text-xs font-bold uppercase tracking-widest text-caos-mute">
          Planned worker attendance
        </h3>
        {!attendance.length ? (
          <p className="mt-2 text-sm italic text-caos-mute">No worker-attendance plan reported.</p>
        ) : (
          <dl className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5" data-testid="sim-attendance-counts">
            {attendance.filter((event) => event.key !== "truth").map((event) => (
              <div key={event.key} className="rounded-lg bg-caos-bone px-3 py-2">
                <dt className="text-xs capitalize text-caos-mute">{event.label}</dt>
                <dd className="font-display text-xl text-caos-forest">{shown(event.count)}</dd>
              </div>
            ))}
          </dl>
        )}
        <p className="mt-2 text-xs text-caos-mute">
          Login is a simulation-session marker only. It creates no staff account or authentication token, and every event remains unexecuted until receipted.
        </p>
      </section>

      <aside
        role="note"
        className="rounded-lg border-2 border-caos-amber bg-[#FDF3E3] p-4 text-sm text-caos-ink"
        data-testid="sim-medication-boundary"
      >
        <strong className="text-caos-forest">Medication boundary:</strong>{" "}
        simulated medication events are reminders only. They do not document administration, change medication orders,
        or replace a qualified staff member's confirmation.
      </aside>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <CapabilityList title="Blocked capabilities" items={blocked} kind="blocked" />
        <CapabilityList title="Unsafe / disabled capabilities" items={unsafe} kind="unsafe" />
      </div>
    </Card>
  );
}

function CapabilityList({ title, items, kind }) {
  return (
    <section className="rounded-lg border border-caos-line p-3" aria-labelledby={`sim-${kind}-heading`}>
      <h3 id={`sim-${kind}-heading`} className="text-xs font-bold uppercase tracking-widest text-caos-mute">{title}</h3>
      {!items.length ? (
        <p className="mt-2 text-sm italic text-caos-mute">None reported.</p>
      ) : (
        <ul className="mt-2 space-y-2" data-testid={`sim-${kind}-capabilities`}>
          {items.map((item) => (
            <li key={item.key} className="text-sm">
              <span className="font-semibold text-caos-terracotta">{item.name}</span>
              {item.reason && <span className="text-caos-mute"> — {item.reason}</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
