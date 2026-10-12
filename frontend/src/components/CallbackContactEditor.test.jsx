import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("../lib/api", () => ({ api: { patch: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...args) => args.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import { api } from "../lib/api";
import { toast } from "sonner";
import CallbackContactEditor from "./CallbackContactEditor";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function type(input, value) {
  const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  set.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

const task = { task_id: "t1", callback_phone: "+15550104321", callback_window: "after 2 pm" };

test("staff edit the callback phone and time through the request PATCH; labelled staff-only", async () => {
  api.patch.mockResolvedValue({ data: {} });
  const onSaved = jest.fn();
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<CallbackContactEditor task={task} canEdit onSaved={onSaved} />); });
  const q = (id) => el.querySelector(`[data-testid="${id}"]`);
  expect(q("callback-editor").textContent).toMatch(/staff only/);
  expect(q("callback-phone").value).toBe("+15550104321");
  await act(async () => { type(q("callback-window"), "tomorrow morning"); });
  await act(async () => { q("callback-save").click(); });
  expect(api.patch).toHaveBeenCalledWith("/tasks/t1", { callback_phone: "+15550104321", callback_window: "tomorrow morning" });
  expect(onSaved).toHaveBeenCalled();
  await act(async () => { root.unmount(); });
});

test("a refused phone shows the reason; a viewer who cannot edit sees it read-only", async () => {
  api.patch.mockRejectedValue({ response: { data: { detail: [{ msg: "Value error, Callback phone needs 7 to 15 digits." }] } } });
  const el = document.createElement("div");
  const root = createRoot(el);
  await act(async () => { root.render(<CallbackContactEditor task={task} canEdit />); });
  await act(async () => { el.querySelector('[data-testid="callback-save"]').click(); });
  expect(toast.error).toHaveBeenCalledWith("Callback phone needs 7 to 15 digits.");
  await act(async () => { root.render(<CallbackContactEditor task={task} canEdit={false} />); });
  expect(el.querySelector('[data-testid="callback-editor"]')).toBeNull();
  expect(el.querySelector('[data-testid="callback-readonly"]').textContent).toMatch(/after 2 pm/);
  await act(async () => { root.unmount(); });
});
