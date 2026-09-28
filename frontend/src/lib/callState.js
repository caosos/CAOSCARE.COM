// Call states come only from the phone system (models_calls.py CallState).
// Labels never claim more than the state proves.
const STATES = {
  requested: { label: "Requested - not dialing yet", tone: "text-caos-mute" },
  dialing: { label: "Dialing", tone: "text-caos-forest" },
  ringing: { label: "Ringing - not answered", tone: "text-caos-forest" },
  connected: { label: "Connected", tone: "text-caos-moss" },
  unanswered: { label: "Not answered", tone: "text-caos-terracotta" },
  failed: { label: "Failed", tone: "text-caos-terracotta" },
  ended: { label: "Ended", tone: "text-caos-mute" },
};

export function callState(state) {
  return STATES[state] || { label: state || "Unknown", tone: "text-caos-mute" };
}

const KINDS = { aria: "Aria", front_desk: "Front desk", family: "Family", emergency: "911" };

export function callKind(kind) {
  return KINDS[kind] || kind;
}

// Whether the call ever reached a person/endpoint, from its history -
// "ended" alone does not say whether it was answered.
export function wasConnected(call) {
  return (call?.history || []).some((h) => h.state === "connected");
}
