// Planned resident options without their own capability card.
// Status comes from the shared registry (lib/capabilities/status.js).
import { statusOf } from "./capabilities/status";

const withStatus = (items) => items.map((i) => ({ ...i, status: statusOf(i.id) }));

export const RESIDENT_AREAS = withStatus([
  { id: "handset", name: "A familiar Aria phone", detail: "Pick up the handset to speak with Aria; hang up to end. Designed for people who already know how to use a telephone, with a simple handset and cradle rather than an office phone screen." },
  { id: "community_calls", name: "Calls within the community", detail: "Ask Aria to call a neighbor, another room, nursing or the front desk, subject to each person's preferences and staff routing." },
  { id: "family_call", name: "Calling family", detail: "Ask Aria to call an approved family contact by name. Aria would only call contacts on the resident's approved list and would say whether the call actually connected." },
  { id: "answering_machine", name: "An answering machine", detail: "A mailbox for the resident's room would hold real messages from authorized people, with the sender's name. Aria would say how many messages actually exist and read them on request." },
  { id: "blinds", name: "Motorized blinds", detail: "Opening and closing blinds by voice." },
]);

export const WEARABLE_AREAS = withStatus([
  { id: "wearables", name: "Approved wearable options", detail: "A small, supported device catalog will show compatible options by community. Heart rate, steps, activity, battery, location and family contact depend on the approved device and consent." },
]);
