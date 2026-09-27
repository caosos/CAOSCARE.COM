// Public catalog entries that don't have a step-by-step demonstration yet.
// Status comes from the shared registry (lib/capabilities/status.js).
// The demonstrated capabilities live in lib/capabilities/*.js.
import { statusOf } from "./capabilities/status";

const withStatus = (items) => items.map((i) => ({ ...i, status: statusOf(i.id) }));

export const RESIDENT_AREAS = withStatus([
  { id: "handset", name: "A familiar Aria phone", detail: "Pick up the handset to speak with Aria; hang up to end. Designed for people who already know how to use a telephone, with a simple handset and cradle rather than an office phone screen." },
  { id: "community_calls", name: "Calls within the community", detail: "Ask Aria to call a neighbor, another room, nursing or the front desk, subject to each person's preferences and staff routing. Ordinary outside calls are also a design goal." },
  { id: "answering_machine", name: "An answering machine", detail: "A mailbox for the resident's room would hold real messages from authorized people, with the sender's name. Aria would say how many messages actually exist and read them on request." },
  { id: "family_call", name: "Family connection", detail: "Call family by name, share appropriate messages and photos, and offer video calls where the resident chooses and the setup supports them." },
]);

export const WEARABLE_AREAS = withStatus([
  { id: "wearables", name: "Approved wearable options", detail: "A small, supported device catalog will show compatible options by community. Heart rate, steps, activity, battery, location and family contact depend on the approved device and consent." },
]);
