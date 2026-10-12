// careops-dept-dispatch-001: an admin queue says how work arrives and who can take it,
// and says plainly when nobody works in the department (empty Assign list).
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import DepartmentDispatchNote from "../DepartmentDispatchNote";
globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function render(props) {
  const el = document.createElement("div"); const root = createRoot(el);
  await act(async () => { root.render(<DepartmentDispatchNote label="Housekeeping" {...props} />); });
  return { el, root };
}

test("lists who works in the department", async () => {
  const { el, root } = await render({ roster: [{ user_id: "u1", name: "Rosa" }], rosterState: "ok" });
  expect(el.querySelector("[data-testid=dept-roster]").textContent).toBe("Works in Housekeeping: Rosa.");
  expect(el.querySelector("[data-testid=dept-roster-empty]")).toBeNull();
  await act(async () => { root.unmount(); });
});

test("an empty department says nobody can claim the work, with the fix", async () => {
  const { el, root } = await render({ roster: [], rosterState: "ok" });
  expect(el.querySelector("[data-testid=dept-roster-empty]").textContent).toMatch(/No one works in Housekeeping yet.*Users & access/);
  await act(async () => { root.unmount(); });
});

test("a failed roster load is not shown as an empty department", async () => {
  const { el, root } = await render({ roster: [], rosterState: "error" });
  expect(el.querySelector("[data-testid=dept-roster-error]")).not.toBeNull();
  expect(el.querySelector("[data-testid=dept-roster-empty]")).toBeNull();
  await act(async () => { root.unmount(); });
});
