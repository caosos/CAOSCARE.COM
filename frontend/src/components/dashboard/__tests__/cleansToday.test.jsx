import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import { CleansToday } from "../WorkerFacts";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const row = (room, hh_mm, state) => ({ room, housekeeper_name: "SIM - Housekeeper 01", planned: { hh_mm }, state, task_id: null });

test("a clean due before the run started says it was not simulated, not remaining", () => {
  const host = document.createElement("div");
  const root = createRoot(host);
  act(() => root.render(
    <CleansToday rows={[row("SIM-001", "08:15", "not_simulated"), row("SIM-006", "20:10", "remaining")]}
      counts={{ completed: 0, in_progress: 0, remaining: 1, not_simulated: 1 }} />));
  const text = host.textContent;
  expect(text).toContain("1 remaining · 1 not simulated (before run start)");
  expect(text).toContain("08:15 · Not simulated (due before this run started)");
  expect(text).toContain("20:10 · Remaining");
  act(() => root.unmount());
});
