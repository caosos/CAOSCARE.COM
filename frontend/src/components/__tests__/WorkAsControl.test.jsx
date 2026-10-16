import React, { act } from "react";
import { createRoot } from "react-dom/client";

const mockGet = jest.fn();
const mockPost = jest.fn();
jest.mock("../../lib/api", () => ({ api: { get: (...a) => mockGet(...a), post: (...a) => mockPost(...a) } }));
jest.mock("sonner", () => ({ toast: { success: jest.fn(), error: jest.fn() } }));
jest.mock("@/lib/utils", () => ({ cn: (...values) => values.filter(Boolean).join(" ") }), { virtual: true });

import WorkAsControl from "../WorkAsControl";
import { readWorkContext, workContextToken } from "../../lib/workContext";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const context = {
  work_context_id: "wctx_1", principal_id: "owner_1", principal_role: "owner",
  acting_role: "staff", acting_department: "maintenance", issued_at: 100, expires_at: 4102444800,
};

beforeEach(() => {
  sessionStorage.clear();
  mockGet.mockReset();
  mockPost.mockReset();
  mockGet.mockResolvedValue({ data: { departments: [{ slug: "maintenance", label: "Maintenance" }] } });
});

test("enters a session-local department context and exits without changing login", async () => {
  mockPost.mockResolvedValue({ data: { token: "signed-work-token", context } });
  const onEntered = jest.fn();
  const onExited = jest.fn();
  const element = document.createElement("div");
  const root = createRoot(element);

  await act(async () => { root.render(<WorkAsControl onEntered={onEntered} onExited={onExited} />); });
  await act(async () => {});
  expect(element.querySelector("[data-testid=work-as-picker]")).not.toBeNull();

  await act(async () => { element.querySelector("[data-testid=work-as-enter]").click(); });
  expect(mockPost).toHaveBeenCalledWith("/work-context", {
    acting_role: "staff", acting_department: "maintenance",
  });
  expect(workContextToken()).toBe("signed-work-token");
  expect(readWorkContext()).toEqual(context);
  expect(onEntered).toHaveBeenCalledWith(context);
  expect(element.textContent).toContain("Working as Maintenance");

  await act(async () => { element.querySelector("[data-testid=work-as-exit]").click(); });
  expect(workContextToken()).toBeNull();
  expect(readWorkContext()).toBeNull();
  expect(onExited).toHaveBeenCalledTimes(1);
  await act(async () => root.unmount());
});
