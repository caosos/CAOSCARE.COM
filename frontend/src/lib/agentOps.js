// Agent Operations helpers (docs/CAOSCARE_AGENT_CONTROL_PLANE.md). Pure
// functions; the page holds no agent state of its own - everything comes
// from /agent-control/*. Receipt-chain ordering reuses the simulator's.
import { orderChain } from "./simulator";

export { orderChain };

export const MAX_INSTRUCTION = 4000; // mirrors backend agent_control/models.py
// eslint-disable-next-line no-control-regex
const BAD_CHARS = /[\x00-\x08\x0b-\x1f\x7f]/;

export const UNKNOWN = "UNKNOWN";

// Status shown for an agent. Unbound agents are OFFLINE, never guessed.
export function agentState(agent) {
  const s = agent?.status;
  if (!s?.state) return { label: UNKNOWN, tone: "mute", simulated: false };
  const label = s.state.toUpperCase();
  const tone = { ONLINE: "ok", WORKING: "ok", WAITING: "warn", BLOCKED: "bad", OFFLINE: "mute" }[label] || "mute";
  return { label, tone, simulated: !!s.simulated, adapter: s.adapter || null };
}

// A field the registry doesn't know yet reads as UNKNOWN, not blank.
export function known(v) {
  return v === null || v === undefined || v === "" ? UNKNOWN : v;
}

export function canCommand(agent) {
  return !!agent?.binding_id && agent?.status?.state && agent.status.state !== "offline";
}

export function validateInstruction(text) {
  if (!text || !text.trim()) return "Enter an instruction.";
  if (text.length > MAX_INSTRUCTION) return `Keep it under ${MAX_INSTRUCTION} characters.`;
  if (BAD_CHARS.test(text)) return "The instruction contains control characters.";
  return null;
}

export function newClientCommandId() {
  const c = typeof crypto !== "undefined" ? crypto : null;
  if (c?.randomUUID) return c.randomUUID().replace(/-/g, "");
  return `${Date.now().toString(16)}${Math.random().toString(16).slice(2, 18)}`;
}

// How much a receipt proves: an agent's own report is never shown as verified.
export function receiptTrust(r) {
  if (r?.result_label === "failed" || r?.status === "failed") return "failed";
  if (r?.result_label === "simulated" || r?.simulated) return "simulated";
  if (r?.result_label === "verified") return "verified";
  return "unverified";
}

// One line per command for the history list: what was asked, what came back.
export function commandSummary(cmd) {
  const log = cmd?.status_log || [];
  const last = log[log.length - 1];
  return {
    status: cmd?.status || UNKNOWN,
    asked: cmd?.instruction || "",
    reply: cmd?.last_message || (last?.to_status === "failed" ? last?.note : null),
    steps: log.length,
  };
}
