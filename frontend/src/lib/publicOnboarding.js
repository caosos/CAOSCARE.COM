// Public sales/onboarding catalog. Room capabilities read their status from
// the room builder's evidence-backed catalog, never a duplicate status list.
import { FEATURE_STATUS, FEATURES_BY_ID } from "./roomExperience/features";

export const STATUS = FEATURE_STATUS;
const roomStage = (id) => FEATURES_BY_ID[id].status;

export const COMMUNITY_AREAS = [
  {
    id: "care", name: "Resident & care requests", status: "pilot",
    description: "A resident asks for help; Aria gathers the request and staff see its actual status and history.",
    staff: "Review resident, room, original words, priority, assignment, acknowledgement and receipts.",
    example: "Room 214 · Assistance requested · Awaiting staff acknowledgement",
  },
  {
    id: "maintenance", name: "Maintenance & housekeeping", status: "in_development",
    description: "Requests reach the responsible department rather than disappearing into conversation.",
    staff: "See work orders and requests, assign work, track progress and completion.",
    example: "Room 116 · Faucet repair · Assigned to Maintenance",
  },
  {
    id: "transport", name: "Transportation & appointments", status: "in_development",
    description: "The resident can request a ride; a request remains pending until staff confirm the schedule.",
    staff: "Review dates, pickup times, driver and vehicle capacity, conflicts and confirmations in a calendar.",
    example: "Tuesday, 10:00 AM · Ride requested · Pending schedule confirmation",
  },
  {
    id: "menus", name: "Kitchen & menus", status: "in_development",
    description: "Aria answers from the published menu when one exists and says when it is unavailable.",
    staff: "Publish and correct meal information so residents hear the same current information.",
    example: "Dinner menu · Awaiting kitchen publication",
  },
  {
    id: "programs", name: "Resident programs & activities", status: "in_development",
    description: "Aria and the resident Today panel can read published activities from the community schedule.",
    staff: "The schedule and intake path exist; community-specific publishing and operations still need setup.",
    example: "Afternoon program · Sample calendar item",
  },
  {
    id: "therapy", name: "Therapy coordination", status: "planned",
    description: "Therapy visits and messages fit into the resident's authorized schedule and mailbox.",
    staff: "Coordinate visit information and leave a message with clear attribution.",
    example: "Therapy visit · Sample reminder",
  },
  {
    id: "salon", name: "Beauty shop & salon", status: "planned",
    description: "A resident can ask about an appointment or request one through Aria.",
    staff: "Manage availability and confirmation before a booking is promised.",
    example: "Salon appointment · Sample request",
  },
  {
    id: "frontdesk", name: "Front desk workspace", status: "in_development",
    description: "Authorized front desk staff have a workspace for residents, requests and transportation.",
    staff: "Review the resident directory, request board and transportation calendar.",
    example: "Front desk · Sample request awaiting review",
  },
  {
    id: "calls", name: "Front desk calls & callbacks", status: "planned",
    description: "The desk would be a single staffed destination for calls, requests and callbacks.",
    staff: "Distinguish a recorded request from a voice call that was actually accepted.",
    example: "Front desk call · Sample callback request",
  },
  {
    id: "leadership", name: "Community leadership", status: "in_development",
    description: "Authorized leaders see requests, rooms, devices and operational history together.",
    staff: "Inspect real records, ownership, escalation and receipts across departments.",
    example: "Requests needing attention · Sample overview",
  },
];

export const RESIDENT_AREAS = [
  { name: "Talk to the room", status: roomStage("voice"), detail: "A hidden room node, eMeet audio and the resident's TV support Aria. The TV is a visual surface when useful; it is not a menu the resident must navigate." },
  { name: "Ask for staff help", status: roomStage("help"), detail: "Aria routes a spoken request; a paired pendant or call button remains a separate way to summon help." },
  { name: "Lighting", status: roomStage("lighting"), detail: "Real lights have been controlled by voice in a test room, with the result checked." },
  { name: "Television", status: roomStage("tv"), detail: "TV power and input control by voice are in development." },
  { name: "Thermostat & comfort", status: roomStage("climate"), detail: "Comfort requests can reach staff; verified voice temperature changes need compatible hardware." },
  { name: "Motorized blinds", status: roomStage("blinds"), detail: "Opening and closing blinds by voice is a planned room option." },
  { name: "A familiar Aria phone", status: "planned", detail: "Pick up the handset to speak with Aria; hang up to end. Designed for people who already know how to use a telephone, with a simple handset and cradle rather than an office phone screen." },
  { name: "Calls within the community", status: "planned", detail: "Ask Aria to call a neighbor, another room, nursing or the front desk, subject to each person's preferences and staff routing. Ordinary outside calls are also a design goal." },
  { name: "An answering machine", status: "planned", detail: "A mailbox for the resident's room would hold real attributed messages from authorized people. Aria would say how many messages actually exist and read them on request." },
  { name: "Family connection", status: roomStage("family_call"), detail: "Call family by name, share appropriate messages and photos, and offer video calls where the resident chooses and the setup supports them." },
];

export const WEARABLE_AREAS = [
  { name: "Familiar HELP pendant", status: roomStage("help"), detail: "Paired RF pendants have been tested with the room node. The physical button is for urgent assistance; routine requests go through Aria or staff." },
  { name: "Approved wearable options", status: "planned", detail: "A small, supported device catalog will show compatible options by community. Heart rate, steps, activity, battery, location/proximity and family contact depend on the approved device and consent." },
];
