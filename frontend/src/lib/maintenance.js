// Pure helpers for department request queues (Maintenance work orders,
// Nursing requests, ...). A department request is just a StaffTask whose
// visibility_role is that department - these functions slice that existing
// list into the operational buckets the queue shows. No new model, no
// server call here. `department` defaults to "maintenance".

const DONE = ["completed", "skipped"];

export function isDepartmentTask(t, department = "maintenance") {
  if (!t) return false;
  return t.visibility_role === department || (!t.visibility_role && t.category === department);
}

export const isMaintenanceWO = (t) => isDepartmentTask(t, "maintenance");

export function isOverdue(t, now = Date.now()) {
  if (!t || !t.due_at || DONE.includes(t.status)) return false;
  const d = new Date(t.due_at).getTime();
  return Number.isFinite(d) && d < now;
}

export function canClaim(t, user) {
  if (!t || t.assigned_to || t.status !== "pending") return false;
  if (["owner", "admin"].includes(user?.role)) return true;
  return user?.role === "staff" && user?.department === (t.visibility_role || t.category);
}

export function canAssign(user, department = "maintenance") {
  return ["owner", "admin"].includes(user?.role) ||
    (user?.role === "staff" && user?.department === department);
}

export function ageLabel(iso) {
  if (!iso) return "";
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000));
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

const byCreatedAsc = (a, b) => new Date(a.created_at || 0) - new Date(b.created_at || 0);

// Slice a task list into a department queue's sections. Deterministic:
// every bucket is oldest-first except `completed` (newest-closed first).
export function workOrderBuckets(tasks, { meId = null, now = Date.now(), completedLimit = 20, department = "maintenance" } = {}) {
  const wos = (tasks || []).filter((t) => isDepartmentTask(t, department));
  const open = wos.filter((t) => !DONE.includes(t.status));
  const unassigned = open.filter((t) => t.status === "pending" && !t.assigned_to).sort(byCreatedAsc);
  const inProgress = open.filter((t) => t.status === "in_progress").sort(byCreatedAsc);
  const overdue = open.filter((t) => isOverdue(t, now)).sort(byCreatedAsc);
  const assigned = open.filter((t) => t.assigned_to && t.status === "pending").sort(byCreatedAsc);
  return {
    all: wos,
    open,
    unassigned,
    inProgress,
    assigned,                                   // has an owner, not started yet
    overdue,
    mine: meId ? open.filter((t) => t.assigned_to === meId).sort(byCreatedAsc) : [],
    completed: wos
      .filter((t) => t.status === "completed")
      .sort((a, b) => new Date(b.completed_at || 0) - new Date(a.completed_at || 0))
      .slice(0, completedLimit),
    counts: {
      open: open.length,
      unassigned: unassigned.length,
      in_progress: inProgress.length,
      overdue: overdue.length,
    },
  };
}
