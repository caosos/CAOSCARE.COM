// Pure display helpers for Live Operations (SIM-2). No state of its own:
// everything shown comes from the SIM-1 API (/simulator/state,
// /simulator/runs/{id}/history) and canonical receipts/tasks. These helpers
// only order, label and link what the server returned.

export const SIM_STATES = { RUNNING: "RUNNING", PAUSED: "PAUSED", STOPPED: "STOPPED" };

// Which controls the server will accept in each state (simulation/scheduler.py).
// The server stays the authority; this only enables/disables buttons.
export function allowedControls(state) {
  return {
    start: !state || state === SIM_STATES.STOPPED,
    pause: state === SIM_STATES.RUNNING,
    step: state === SIM_STATES.PAUSED,
    resume: state === SIM_STATES.PAUSED,
    stop: state === SIM_STATES.RUNNING || state === SIM_STATES.PAUSED,
  };
}

export function simClock(minute) {
  const m = Number(minute) || 0;
  const h = Math.floor(m / 60);
  return h ? `T+${h} h ${m % 60} min` : `T+${m} min`;
}

export function describeStep(step) {
  if (!step) return "—";
  const action = String(step.action || "").replace(/_/g, " ");
  return `${String(step.actor || "").replace(/_/g, " ")}: ${action} at ${simClock(step.at)}`;
}

// Real vs simulated vs system, from the receipt's / cast entry's own fields.
// A record marked simulated anywhere is never shown as real.
export function actorKind(x) {
  if (!x) return "unknown";
  if (x.simulated === true || x.actor_type === "simulated-agent" || x.identity_basis === "synthetic") return "simulated";
  if (x.actor_type === "system") return "system";
  if (x.actor_type === "real-human") return "real";
  return "unknown";
}

export const ACTOR_BADGE = {
  simulated: { label: "SIMULATED", className: "bg-caos-amber/20 text-[#8B5A20] border border-caos-amber" },
  real: { label: "REAL", className: "bg-caos-forest text-white" },
  system: { label: "SYSTEM", className: "bg-caos-mute/15 text-caos-mute border border-caos-line" },
  unassigned: { label: "UNASSIGNED", className: "bg-white text-caos-mute border border-dashed border-caos-mute" },
  unknown: { label: "UNKNOWN", className: "bg-caos-terracotta/15 text-caos-terracotta border border-caos-terracotta" },
};

// SIM-3: who holds a staff role in this run (cast entry's filled_by, set by
// the server). A role with no holder record is held by its simulated actor.
export function roleFill(entry) {
  const f = entry?.filled_by || { mode: "simulated" };
  if (f.mode === "real") return { kind: "real", name: f.name || f.user_id, userId: f.user_id };
  if (f.mode === "unassigned") return { kind: "unassigned", name: null };
  return { kind: "simulated", name: entry?.name };
}

// The "waiting for" line when the next step's role is not simulated.
export function waitingText(waitingOn) {
  if (!waitingOn) return null;
  if (waitingOn.mode === "real") return `waiting for REAL ${waitingOn.name || waitingOn.user_id} to work it in the normal staff UI`;
  return "waiting: nobody holds this role";
}

// Order one receipt chain by its parent links (exact), falling back to
// created_at for anything outside the links. Same-millisecond receipts
// stay in their true order this way.
export function orderChain(chain) {
  const rows = Array.isArray(chain) ? chain : [];
  const byParent = new Map();
  const ids = new Set(rows.map((r) => r.receipt_id));
  rows.forEach((r) => {
    const p = ids.has(r.parent_receipt_id) ? r.parent_receipt_id : null;
    if (!byParent.has(p)) byParent.set(p, []);
    byParent.get(p).push(r);
  });
  const byTime = (a, b) => String(a.created_at || "").localeCompare(String(b.created_at || ""));
  const out = [];
  const visit = (parent) => (byParent.get(parent) || []).sort(byTime).forEach((r) => { out.push(r); visit(r.receipt_id); });
  visit(null);
  return out.length === rows.length ? out : [...rows].sort(byTime);
}

// One stream, newest first: the run chain and the request chain, each in
// chain order, merged by time. Each row says which chain it came from.
export function mergeStream(runChain, requestChain) {
  const a = orderChain(runChain).map((r) => ({ ...r, chain: "run" }));
  const b = orderChain(requestChain).map((r) => ({ ...r, chain: "request" }));
  const out = [];
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (j >= b.length || (i < a.length && String(a[i].created_at) <= String(b[j].created_at))) out.push(a[i++]);
    else out.push(b[j++]);
  }
  return out.reverse();
}

const STEP_TYPES = ["sim_step_executed", "sim_step_observed", "sim_step_failed", "sim_step_refused"];

// The latest scheduled step the run recorded (executed, observed, failed or refused).
export function currentAction(runChain) {
  const steps = orderChain(runChain).filter((r) => STEP_TYPES.includes(r.action_type));
  return steps.length ? steps[steps.length - 1] : null;
}

export function failures(runChain, refusedStarts = []) {
  return [...orderChain(runChain).filter((r) => r.status === "failed"), ...(refusedStarts || [])];
}

// A step receipt names the canonical receipt that recorded the work.
export function canonicalRefOf(receipt) {
  return (receipt?.provider_refs || [])[0] || null;
}

// Open requests from the canonical task list, simulated work only.
// Open requests raised by this run. A run's requests carry its
// simulation_run_id; other simulated work in the demo room (e.g. demo
// continuity) belongs to a different run and is not shown here.
export function activeSimRequests(tasks, runId) {
  return (tasks || []).filter((t) => t.simulated && !["completed", "skipped"].includes(t.status)
    && (!runId || t.simulation_run_id === runId));
}

// The cast entry (from the run) that matches a receipt's actor, if any.
export function castEntryFor(cast, actorId) {
  return Object.values(cast || {}).find((c) => c.actor_id === actorId) || null;
}

export function fmtTime(iso) {
  if (!iso) return "—";
  try { return new Date(iso).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", second: "2-digit" }); }
  catch { return iso; }
}
