import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("../lib/api", () => ({ api: { get: jest.fn(), put: jest.fn(), post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...args) => args.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import { api } from "../lib/api";
import { toast } from "sonner";
import EscalationTab from "./EscalationTab";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const RULE = { facility_id: null, level_2_seconds: 90, level_3_seconds: 150, enabled: true };

function type(input, value) {
  const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  set.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

async function mount() {
  api.get.mockResolvedValue({ data: RULE });
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<EscalationTab />); });
  return { el, root };
}

test("a refused policy edit shows the server's reason and keeps what was typed", async () => {
  api.put.mockRejectedValue({ response: { status: 422, data: { detail: [
    { msg: "Value error, Level 3 must come later than Level 2." }] } } });
  const { el, root } = await mount();
  const l3 = el.querySelector("[data-testid=esc-l3-seconds]");
  await act(async () => { type(l3, "60"); });
  await act(async () => { el.querySelector("[data-testid=esc-save]").click(); });
  expect(api.put).toHaveBeenCalledWith("/escalation/rule", expect.objectContaining({ level_3_seconds: "60" }));
  expect(toast.error).toHaveBeenCalledWith("Level 3 must come later than Level 2.");
  // a blank field is not silently replaced by a default
  await act(async () => { type(l3, ""); });
  expect(l3.value).toBe("");
  await act(async () => { root.unmount(); });
});

test("a saved edit shows when the policy last changed", async () => {
  api.put.mockResolvedValue({ data: { ...RULE, level_2_seconds: 20, level_3_seconds: 40,
    updated_by: "user_1", receipt_id: "rcpt_1", updated_at: "2026-10-12T13:00:00+00:00" } });
  const { el, root } = await mount();
  expect(el.querySelector("[data-testid=esc-last-change]")).toBeNull();
  await act(async () => { el.querySelector("[data-testid=esc-save]").click(); });
  expect(toast.success).toHaveBeenCalledWith("Saved");
  expect(el.querySelector("[data-testid=esc-last-change]").textContent).toContain("Last changed");
  await act(async () => { root.unmount(); });
});
