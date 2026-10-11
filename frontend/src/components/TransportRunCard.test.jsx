import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("../lib/api", () => ({ api: { post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...args) => args.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import TransportRunCard from "./TransportRunCard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("the trip card has a clear open-details action", async () => {
  const onOpen = jest.fn();
  const run = {
    run_id: "run-1", depart_time: "10:00", status: "confirmed",
    driver: { name: "Pete Nash" }, vehicle: { name: "Demo Van", capacity: 4 },
    riders: [{ task_id: "task-1", resident_name: "Demo Resident", purpose: "clinic", status: "pending" }],
  };
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => {
    root.render(<TransportRunCard run={run} canOperate canBook onOpen={onOpen} />);
  });

  const open = el.querySelector("[data-testid=run-open-run-1]");
  expect(open).not.toBeNull();
  expect(open.textContent).toContain("Open trip details");
  await act(async () => { open.click(); });
  expect(onOpen).toHaveBeenCalledWith(run);

  await act(async () => { root.unmount(); });
});
