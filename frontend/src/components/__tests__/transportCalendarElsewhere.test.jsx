// careops-transport-calendar-001: the calendar says where the rides are when the shown day is empty.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
import TransportCalendarElsewhere from "../TransportCalendarElsewhere";
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("lists next dates as jump buttons and states past-dated open requests", async () => {
  const onJump = jest.fn();
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => { root.render(<TransportCalendarElsewhere fmtDay={(d) => `D:${d}`} onJump={onJump}
    elsewhere={{ next_dates: [{ date: "2026-10-14", count: 2 }], earlier_open_unbooked: 9 }} />); });
  const jump = el.querySelector("[data-testid=calendar-jump-2026-10-14]");
  expect(jump.textContent).toBe("D:2026-10-14 (2)");
  await act(async () => { jump.click(); });
  expect(onJump).toHaveBeenCalledWith("2026-10-14");
  expect(el.querySelector("[data-testid=calendar-earlier-open]").textContent).toMatch(/^9 open ride requests are dated before today/);
  await act(async () => { root.unmount(); });
});

test("renders nothing when there is nothing elsewhere", async () => {
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => { root.render(<TransportCalendarElsewhere fmtDay={(d) => d} onJump={() => {}} elsewhere={{ next_dates: [], earlier_open_unbooked: 0 }} />); });
  expect(el.innerHTML).toBe("");
  await act(async () => { root.unmount(); });
});
