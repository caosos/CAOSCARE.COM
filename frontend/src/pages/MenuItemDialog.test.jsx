import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("../lib/api", () => ({ api: { patch: jest.fn(), post: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...args) => args.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));

import { api } from "../lib/api";
import { toast } from "sonner";
import MenuItemDialog from "./MenuItemDialog";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

test("correcting a published item explains versioning and that the published one stays live as a draft correction", async () => {
  api.patch.mockResolvedValue({ data: { menu_id: "m2", status: "draft", replaces: "m1" } });
  const item = { menu_id: "m1", status: "approved", date: "2031-03-04", meal_period: "dinner", item_name: "Baked cod", description: "", availability: "" };
  const host = document.createElement("div"); document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => { root.render(<MenuItemDialog open item={item} date="2031-03-04" onOpenChange={() => {}} />); });
  expect(document.body.textContent).toMatch(/correction becomes a new version/);
  expect(document.body.textContent).toMatch(/stays listed as Replaced/);
  await act(async () => { document.querySelector('[data-testid="menu-save-draft"]').click(); });
  expect(api.patch).toHaveBeenCalledWith("/menu/m1", expect.objectContaining({ publish: false }));
  expect(toast.success).toHaveBeenCalledWith("Correction saved as draft — residents still see the published version until you publish it");
  await act(async () => { root.unmount(); });
});
