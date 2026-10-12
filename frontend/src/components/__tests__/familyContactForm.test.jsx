// careops-family-edit-001: the contact form edits an existing contact (PATCH,
// resident fixed, no call-approval field) and adds a new one (POST, never
// sends allow_calls).
import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockPatch = jest.fn();
const mockPost = jest.fn();
jest.mock("../../lib/api", () => ({ api: { patch: (...a) => mockPatch(...a), post: (...a) => mockPost(...a) } }));
jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("sonner", () => ({ toast: { error: jest.fn(), success: jest.fn() } }));
jest.mock("../ui/dialog", () => {
  const R = require("react");
  const pass = ({ children, open }) => (open === false ? null : R.createElement("div", null, children));
  return { Dialog: pass, DialogContent: pass, DialogHeader: pass, DialogTitle: pass, DialogFooter: pass };
});
jest.mock("../ui/label", () => { const R = require("react"); return { Label: (p) => R.createElement("label", null, p.children) }; });
jest.mock("../ui/button", () => { const R = require("react"); return { Button: (p) => R.createElement("button", { type: p.type || "button", onClick: p.onClick, disabled: p.disabled, "data-testid": p["data-testid"] }, p.children) }; });
jest.mock("../ui/input", () => { const R = require("react"); return { Input: (p) => R.createElement("input", { type: p.type || "text", value: p.value, onChange: p.onChange, "data-testid": p["data-testid"] }) }; });
jest.mock("../ui/checkbox", () => { const R = require("react"); return { Checkbox: () => R.createElement("span") }; });
jest.mock("../ui/select", () => {
  const R = require("react");
  const Select = ({ value, onValueChange, children }) => R.createElement("select", { "data-testid": "fam-resident", value, onChange: (e) => onValueChange(e.target.value) },
    R.createElement("option", { value: "" }, ""), R.createElement("option", { value: "res_1" }, "Pearl"));
  const none = () => null;
  return { Select, SelectContent: none, SelectItem: none, SelectTrigger: none, SelectValue: none };
});

import FamilyContactForm from "../FamilyContactForm";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const residents = [{ resident_id: "res_1", name: "Pearl", room: "3W01" }];
const contact = { contact_id: "fam_1", resident_id: "res_1", name: "Kin", relationship: "son", email: "", phone: "+15550100",
  notify_on: ["emergency"], allow_calls: true };

function setValue(input, value) {
  const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, "value").set;
  setter.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

beforeEach(() => { mockPatch.mockReset(); mockPost.mockReset(); document.body.innerHTML = ""; });

test("edit sends a PATCH with the editable fields only and keeps the resident fixed", async () => {
  mockPatch.mockResolvedValue({ data: { changed: ["name"] } });
  const onSaved = jest.fn(); const onOpenChange = jest.fn();
  const el = document.createElement("div"); document.body.appendChild(el);
  const root = createRoot(el);
  await act(async () => { root.render(<FamilyContactForm open onOpenChange={onOpenChange} residents={residents} contact={contact} onSaved={onSaved} />); });
  expect(document.querySelector("[data-testid=fam-resident-fixed]").textContent).toContain("Pearl");
  expect(document.querySelector("[data-testid=fam-resident]")).toBeNull();
  expect(document.body.textContent).toContain("only an owner or admin can change the number");
  await act(async () => { setValue(document.querySelector("[data-testid=fam-name]"), "Kin Smith"); });
  await act(async () => { document.querySelector("[data-testid=fam-save]").click(); });
  expect(mockPatch).toHaveBeenCalledTimes(1);
  const [url, body] = mockPatch.mock.calls[0];
  expect(url).toBe("/family-contacts/fam_1");
  expect(body.name).toBe("Kin Smith");
  expect(body).not.toHaveProperty("resident_id");
  expect(body).not.toHaveProperty("allow_calls");
  expect(onSaved).toHaveBeenCalled(); expect(onOpenChange).toHaveBeenCalledWith(false);
  await act(async () => { root.unmount(); });
});

test("add sends a POST without allow_calls, and refuses with no resident", async () => {
  mockPost.mockResolvedValue({ data: {} });
  const el = document.createElement("div"); document.body.appendChild(el);
  const root = createRoot(el);
  await act(async () => { root.render(<FamilyContactForm open onOpenChange={() => {}} residents={residents} onSaved={() => {}} />); });
  await act(async () => { setValue(document.querySelector("[data-testid=fam-name]"), "New Kin"); });
  await act(async () => { document.querySelector("[data-testid=fam-save]").click(); });
  expect(mockPost).not.toHaveBeenCalled();                       // no resident chosen
  const sel = document.querySelector("[data-testid=fam-resident]");
  await act(async () => { sel.value = "res_1"; sel.dispatchEvent(new Event("change", { bubbles: true })); });
  await act(async () => { document.querySelector("[data-testid=fam-save]").click(); });
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, body] = mockPost.mock.calls[0];
  expect(url).toBe("/family-contacts");
  expect(body).toMatchObject({ resident_id: "res_1", name: "New Kin" });
  expect(body).not.toHaveProperty("allow_calls");
  await act(async () => { root.unmount(); });
});
