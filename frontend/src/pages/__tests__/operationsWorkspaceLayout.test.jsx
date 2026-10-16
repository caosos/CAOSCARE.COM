import React, { act } from "react";
import { createRoot } from "react-dom/client";

jest.mock("react-router-dom", () => ({ useSearchParams: () => [new URLSearchParams(), () => {}] }), { virtual: true });
jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../../components/workspace/WorkspaceShell", () => ({ children }) => <div>{children}</div>);
jest.mock("../../components/workspace/RecordsDialog", () => () => null);
jest.mock("../../components/workspace/WorkspaceGrid", () => ({ onAdd }) => (
  <button type="button" data-testid="ws-add" onClick={onAdd}>Add a widget</button>));
const mockReset = jest.fn();
jest.mock("../../lib/useWorkspaceLayout", () => ({
  useWorkspaceLayout: () => ({ boxes: [], status: "saved", update: jest.fn(), reset: mockReset }),
}));
jest.mock("../../lib/useWorkspaceData", () => ({ useBoxValues: () => ({ values: {} }) }));

import OperationsWorkspace from "../OperationsWorkspace";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// Owner 2026-10-15: the workspace has no "Customize Layout" button; arranging happens on the page,
// and "Reset to default layout" stays reachable from the existing Add-a-widget dialog.
test("no Customize Layout control; reset stays reachable from Add a widget", async () => {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  await act(async () => root.render(<OperationsWorkspace />));
  expect(document.body.textContent).not.toMatch(/customi[sz]e/i);
  expect(document.querySelector("[data-testid=ws-customize]")).toBeNull();
  expect(document.querySelector("[data-testid=ws-save-status]").textContent).toBe("Layout saved");

  await act(async () => document.querySelector("[data-testid=ws-add]").click());
  const resetButton = document.querySelector("[data-testid=ws-reset]");
  expect(resetButton.textContent).toMatch("Reset to default layout");
  await act(async () => resetButton.click());
  expect(mockReset).toHaveBeenCalledTimes(1);
  await act(async () => root.unmount());
  host.remove();
});
