import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import SimCommunityOverview from "../SimCommunityOverview";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function render(community) {
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<SimCommunityOverview community={community} />); });
  return { el, root };
}

const text = (el) => el.textContent.replace(/\s+/g, " ").trim();

const community = {
  residents: { count: 10, burn_in_target: 10, target: 75 },
  apartments: { total: 80, occupied: 70, occupancy_target: 70 },
  workers: { count: 50 },
  departments: [
    { slug: "nursing", label: "Nursing / Care", worker_count: 18, shift_count: 3, coverage_24h: true },
    { slug: "activities", label: "Activities", worker_count: 4, shift_count: 1, coverage_24h: false },
  ],
  routines: { scheduled: 42, due: 7, completed: 31, blocked: 4 },
  shift_events: { clock_in: 32, handoff: 32, clock_out: 32, executed: 0 },
  blocked_capabilities: [{ id: "external-calls", name: "External calls", reason: "No simulated-safe adapter" }],
  unsafe_capabilities: ["Medication administration"],
};

test("shows declared community scale, department coverage, and routine counts", async () => {
  const { el, root } = await render(community);
  expect(text(el.querySelector("[data-testid=sim-resident-count]"))).toMatch(/10.*10.*burn-in target/);
  expect(text(el.querySelector("[data-testid=sim-resident-target]"))).toContain("75");
  expect(text(el.querySelector("[data-testid=sim-apartment-count]"))).toMatch(/80.*70 occupied.*70 occupancy target/);
  expect(text(el.querySelector("[data-testid=sim-worker-count]"))).toContain("50");
  expect(text(el.querySelector("[data-testid=sim-department-coverage]"))).toMatch(/Nursing \/ Care.*24-hour coverage.*18 workers.*3 shifts/);
  expect(text(el.querySelector("[data-testid=sim-department-coverage]"))).toMatch(/Activities.*Coverage gap/);
  expect(text(el.querySelector("[data-testid=sim-routine-counts]"))).toMatch(/scheduled.*42.*due.*7.*completed.*31.*blocked.*4/);
  expect(text(el.querySelector("[data-testid=sim-shift-event-counts]"))).toMatch(/clock in.*32.*handoff.*32.*clock out.*32.*executed.*0/);
  await act(async () => { root.unmount(); });
});

test("states the medication boundary and names blocked and unsafe capabilities", async () => {
  const { el, root } = await render(community);
  const boundary = el.querySelector("[data-testid=sim-medication-boundary]");
  expect(boundary.getAttribute("role")).toBe("note");
  expect(boundary.textContent).toMatch(/reminders only/i);
  expect(boundary.textContent).toMatch(/do not document administration/i);
  expect(el.querySelector("[data-testid=sim-blocked-capabilities]").textContent).toMatch(/External calls.*No simulated-safe adapter/);
  expect(el.querySelector("[data-testid=sim-unsafe-capabilities]").textContent).toContain("Medication administration");
  await act(async () => { root.unmount(); });
});

test("keeps missing simulator facts visibly unreported", async () => {
  const { el, root } = await render({});
  expect(el.querySelector("[data-testid=sim-resident-count]").textContent).toContain("\u2014");
  expect(el.textContent).toContain("Burn-in target not reported");
  expect(el.textContent).toContain("No department coverage reported");
  expect(el.textContent).toContain("No routine counts reported");
  expect(el.querySelector("[data-testid=sim-medication-boundary]")).not.toBeNull();
  await act(async () => { root.unmount(); });
});
