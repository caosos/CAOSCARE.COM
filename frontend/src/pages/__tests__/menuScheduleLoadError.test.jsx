// careops-activities-calendar-001: a failed menu/schedule load is shown as a failure with Try again,
// never as "nothing scheduled" / "no menu items".
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a), post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../../components/ContentCoverageNote", () => () => null);
jest.mock("../ScheduleReviewPanel", () => () => null);
jest.mock("../MenuUploadsPanel", () => () => null);

import ScheduleTab from "../ScheduleTab";
import MenuTab from "../MenuTab";
globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); });

test.each([["schedule", ScheduleTab], ["menu", MenuTab]])("%s: failure is not shown as empty, Try again recovers", async (thing, Screen) => {
  mockGet.mockReset();
  mockGet.mockRejectedValueOnce(new Error("down"));
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => { root.render(<Screen />); }); await flush();
  expect(el.querySelector(`[data-testid=${thing}-load-error]`)).not.toBeNull();
  expect(el.querySelector(`[data-testid=${thing}-empty]`)).toBeNull();
  mockGet.mockResolvedValue({ data: [] });
  await act(async () => { el.querySelector(`[data-testid=${thing}-load-error] button`).click(); }); await flush();
  expect(el.querySelector(`[data-testid=${thing}-load-error]`)).toBeNull();
  expect(el.querySelector(`[data-testid=${thing}-empty]`)).not.toBeNull();
  await act(async () => { root.unmount(); });
});
