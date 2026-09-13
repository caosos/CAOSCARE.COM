import { workOrderBuckets, isOverdue, canClaim, canAssign, isMaintenanceWO } from "../maintenance";

const NOW = new Date("2026-09-07T12:00:00Z").getTime();
const HOUR = 3600_000;
const iso = (offsetMs) => new Date(NOW + offsetMs).toISOString();

// every fixture gets a distinct created_at so ordering is fully deterministic
function wo(over) {
  return {
    title: "WO", description: "", category: "maintenance", visibility_role: "maintenance",
    status: "pending", priority: "normal", assigned_to: null, assigned_name: null,
    room: null, due_at: null, completed_at: null,
    ...over,
  };
}

describe("isMaintenanceWO", () => {
  test("matches visibility_role, or category when role missing", () => {
    expect(isMaintenanceWO({ visibility_role: "maintenance" })).toBe(true);
    expect(isMaintenanceWO({ visibility_role: "housekeeping", category: "maintenance" })).toBe(false);
    expect(isMaintenanceWO({ category: "maintenance" })).toBe(true);
    expect(isMaintenanceWO({ visibility_role: "all_staff", category: "other" })).toBe(false);
    expect(isMaintenanceWO(null)).toBe(false);
  });
});

describe("isOverdue", () => {
  test("only when a real due_at is in the past and the WO is still open", () => {
    expect(isOverdue(wo({ due_at: null }), NOW)).toBe(false);
    expect(isOverdue(wo({ due_at: iso(-HOUR) }), NOW)).toBe(true);
    expect(isOverdue(wo({ due_at: iso(HOUR) }), NOW)).toBe(false);
    expect(isOverdue(wo({ due_at: iso(-HOUR), status: "completed" }), NOW)).toBe(false);
    expect(isOverdue(wo({ due_at: "not-a-date" }), NOW)).toBe(false);
  });
});

describe("canClaim / canAssign", () => {
  const maint = { role: "staff", department: "maintenance", user_id: "u1" };
  const hk = { role: "staff", department: "housekeeping", user_id: "u2" };
  const admin = { role: "admin", user_id: "a1" };

  test("claim: only an unassigned pending WO, by an admin or a maintenance staffer", () => {
    expect(canClaim(wo({}), maint)).toBe(true);
    expect(canClaim(wo({}), admin)).toBe(true);
    expect(canClaim(wo({}), hk)).toBe(false);
    expect(canClaim(wo({ assigned_to: "x" }), maint)).toBe(false);
    expect(canClaim(wo({ status: "in_progress" }), maint)).toBe(false);
  });

  test("assign controls: admin/owner or a maintenance staffer", () => {
    expect(canAssign(admin)).toBe(true);
    expect(canAssign({ role: "owner" })).toBe(true);
    expect(canAssign(maint)).toBe(true);
    expect(canAssign(hk)).toBe(false);
    expect(canAssign(null)).toBe(false);
  });
});

describe("workOrderBuckets", () => {
  const tasks = [
    wo({ task_id: "u_old", created_at: iso(-50 * HOUR) }),                                              // unassigned
    wo({ task_id: "u_new", created_at: iso(-2 * HOUR) }),                                               // unassigned
    wo({ task_id: "asg_other", assigned_to: "u9", assigned_name: "Kim", created_at: iso(-8 * HOUR) }),  // owned by someone else, pending
    wo({ task_id: "asg_mine", assigned_to: "u1", assigned_name: "Bob", created_at: iso(-7 * HOUR) }),   // owned by me, pending
    wo({ task_id: "prog_mine", status: "in_progress", assigned_to: "u1", assigned_name: "Bob", created_at: iso(-6 * HOUR) }),
    wo({ task_id: "prog_other", status: "in_progress", assigned_to: "u9", assigned_name: "Kim", created_at: iso(-5 * HOUR) }),
    wo({ task_id: "over_mine", assigned_to: "u1", assigned_name: "Bob", due_at: iso(-3 * HOUR), created_at: iso(-4 * HOUR) }),
    wo({ task_id: "done_a", status: "completed", completed_at: iso(-1 * HOUR), created_at: iso(-20 * HOUR) }),
    wo({ task_id: "done_b", status: "completed", completed_at: iso(-9 * HOUR), created_at: iso(-30 * HOUR) }),
    { task_id: "hk", visibility_role: "housekeeping", category: "housekeeping", status: "pending", created_at: iso(-99 * HOUR) },
    { task_id: "chore", visibility_role: "all_staff", category: "other", status: "pending", created_at: iso(-99 * HOUR) },
  ];
  const b = workOrderBuckets(tasks, { meId: "u1", now: NOW });

  test("excludes non-maintenance tasks entirely", () => {
    expect(b.all.map((t) => t.task_id).sort()).toEqual(
      ["asg_mine", "asg_other", "done_a", "done_b", "over_mine", "prog_mine", "prog_other", "u_new", "u_old"].sort()
    );
  });
  test("unassigned = pending + no owner, oldest first", () => {
    expect(b.unassigned.map((t) => t.task_id)).toEqual(["u_old", "u_new"]);
  });
  test("assigned = has owner, still pending (any tech), oldest first", () => {
    expect(b.assigned.map((t) => t.task_id)).toEqual(["asg_other", "asg_mine", "over_mine"]);
  });
  test("inProgress (any tech)", () => {
    expect(b.inProgress.map((t) => t.task_id)).toEqual(["prog_mine", "prog_other"]);
  });
  test("mine = every open WO owned by me (pending or in progress), oldest first", () => {
    expect(b.mine.map((t) => t.task_id)).toEqual(["asg_mine", "prog_mine", "over_mine"]);
  });
  test("overdue = real past due_at, still open", () => {
    expect(b.overdue.map((t) => t.task_id)).toEqual(["over_mine"]);
  });
  test("completed = newest closed first, capped", () => {
    expect(b.completed.map((t) => t.task_id)).toEqual(["done_a", "done_b"]);
    expect(workOrderBuckets(tasks, { meId: "u1", now: NOW, completedLimit: 1 }).completed.map((t) => t.task_id)).toEqual(["done_a"]);
  });
  test("counts summarise the open work", () => {
    // open = u_old,u_new,asg_other,asg_mine,prog_mine,prog_other,over_mine = 7
    expect(b.counts).toEqual({ open: 7, unassigned: 2, in_progress: 2, overdue: 1 });
  });
  test("empty / null input is safe and deterministic", () => {
    const e = workOrderBuckets([], {});
    expect(e.all).toEqual([]);
    expect(e.counts).toEqual({ open: 0, unassigned: 0, in_progress: 0, overdue: 0 });
    expect(workOrderBuckets(null, {}).all).toEqual([]);
  });
});
