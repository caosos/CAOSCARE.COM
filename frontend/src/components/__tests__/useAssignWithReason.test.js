jest.mock("@/lib/utils", () => ({ cn: (...a) => a.filter(Boolean).join(" ") }), { virtual: true });
jest.mock("../ui/dialog", () => ({ Dialog: () => null, DialogContent: () => null, DialogFooter: () => null, DialogHeader: () => null, DialogTitle: () => null }));
import { assignmentKind } from "../useAssignWithReason";

test("moving a request: claim needs nothing; reassign, release and handoff need a reason (#168)", () => {
  expect(assignmentKind({ status: "pending", assigned_to: null }, "u1")).toBe("assign");
  expect(assignmentKind({ status: "pending", assigned_to: "u1" }, "u1")).toBeNull();
  expect(assignmentKind({ status: "pending", assigned_to: "u1" }, "u2")).toBe("reassign");
  expect(assignmentKind({ status: "pending", assigned_to: "u1" }, "")).toBe("release");
  expect(assignmentKind({ status: "in_progress", assigned_to: "u1" }, "u2")).toBe("handoff");
  expect(assignmentKind({ status: "in_progress", assigned_to: "u1" }, null)).toBe("handoff");
});
