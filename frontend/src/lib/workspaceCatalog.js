// Every box the Live Operations workspace can show — the one list. A box's
// number comes from the same backend query as its drill-down records
// (GET /ops/metrics/records with page_size=1 returns that query's total), so
// what a box shows and what clicking it lists cannot disagree (issue #153).
//
// source.kind:
//   "metric"  -> /ops/metrics/records?metric=&department=&origin=
//   "widget"  -> /ops/metrics/widgets/{name}  (residents, staff on duty, events)
//   "panel"   -> a component box with no number (simulation controls, Ask Aria)
import {
  BedDouble, BriefcaseBusiness, Brush, CalendarDays, CarFront, CheckCircle2, ClipboardCheck,
  Headset, HeartPulse, PlayCircle, Sparkles, UserRoundPlus, Users, Utensils, Wrench,
} from "lucide-react";

export const TINTS = {
  rose: { card: "bg-[#FEF1F1] border-[#F7D4D4]", icon: "bg-[#FBDADA] text-[#D93B3B]", title: "text-[#B42318]" },
  sky: { card: "bg-[#EEF5FD] border-[#D3E3F6]", icon: "bg-[#D6E8FA] text-[#1D72D8]", title: "text-[#111827]" },
  green: { card: "bg-[#EFF8F1] border-[#CFE8D6]", icon: "bg-[#D6F0DD] text-[#2E9A4F]", title: "text-[#14532D]" },
  amber: { card: "bg-[#FFF8EC] border-[#F6E3BE]", icon: "bg-[#FCEBC6] text-[#D99A0B]", title: "text-[#111827]" },
  violet: { card: "bg-[#F4F2FD] border-[#DEDAF6]", icon: "bg-[#E3DEFB] text-[#5B49D6]", title: "text-[#111827]" },
  mint: { card: "bg-[#EEF8F1] border-[#CDE9D5]", icon: "bg-[#D3EFDB] text-[#2F8F4E]", title: "text-[#14532D]" },
  pink: { card: "bg-[#FBF0F8] border-[#F0D3E8]", icon: "bg-[#F6D9EE] text-[#A5308A]", title: "text-[#111827]" },
  cyan: { card: "bg-[#EEF7FA] border-[#D0E8EF]", icon: "bg-[#D5EEF5] text-[#1689A8]", title: "text-[#111827]" },
  slate: { card: "bg-[#F5F7FA] border-[#DFE4EB]", icon: "bg-[#E4E9F0] text-[#475569]", title: "text-[#111827]" },
};

const metric = (m, extra = {}) => ({ kind: "metric", metric: m, ...extra });

export const WIDGETS = [
  { id: "resident_calls", title: "Resident Calls", subtitle: "Waiting for response", tint: "rose",
    icon: UserRoundPlus, source: metric("waiting", { origin: "resident_request" }) },
  { id: "tasks_in_progress", title: "Tasks In Progress", subtitle: "Currently underway", tint: "sky",
    icon: ClipboardCheck, source: metric("in_progress") },
  { id: "staff_on_duty", title: "Staff On Duty", subtitle: "Scheduled now", tint: "green",
    icon: Users, source: { kind: "widget", name: "staff_on_duty" } },
  { id: "residents", title: "Residents", subtitle: "Registered residents", tint: "amber",
    icon: BedDouble, source: { kind: "widget", name: "residents" } },
  { id: "kitchen", title: "Kitchen", subtitle: "Meals in progress", tint: "violet",
    icon: Utensils, source: metric("in_progress", { department: "kitchen" }) },
  { id: "housekeeping", title: "Housekeeping", subtitle: "Rooms in progress", tint: "mint",
    icon: Brush, source: metric("in_progress", { department: "housekeeping" }) },
  { id: "maintenance", title: "Maintenance", subtitle: "Open requests", tint: "pink",
    icon: Wrench, source: metric("open", { department: "maintenance" }) },
  { id: "activities", title: "Activities", subtitle: "Today's events", tint: "cyan",
    icon: CalendarDays, source: { kind: "widget", name: "events_today" } },
  // Available from "Add a widget"
  { id: "completed_today", title: "Completed Today", subtitle: "All departments", tint: "green",
    icon: CheckCircle2, source: metric("done"), optional: true },
  { id: "nursing_waiting", title: "Nursing", subtitle: "Waiting for care staff", tint: "rose",
    icon: HeartPulse, source: metric("waiting", { department: "nursing" }), optional: true },
  { id: "nursing_open", title: "Nursing", subtitle: "Open requests", tint: "rose",
    icon: HeartPulse, source: metric("open", { department: "nursing" }), optional: true },
  { id: "nursing_done", title: "Nursing", subtitle: "Completed today", tint: "sky",
    icon: HeartPulse, source: metric("done", { department: "nursing" }), optional: true },
  { id: "kitchen_done", title: "Kitchen", subtitle: "Completed today", tint: "violet",
    icon: Utensils, source: metric("done", { department: "kitchen" }), optional: true },
  { id: "front_desk", title: "Front Desk", subtitle: "Open requests", tint: "amber",
    icon: Headset, source: metric("open", { department: "front_desk" }), optional: true },
  { id: "administration", title: "Administration", subtitle: "Open requests", tint: "slate",
    icon: BriefcaseBusiness, source: metric("open", { department: "administration" }), optional: true },
  { id: "transportation", title: "Transportation", subtitle: "Open requests", tint: "cyan",
    icon: CarFront, source: metric("open", { department: "transportation" }), optional: true },
  { id: "ask_aria", title: "Ask Aria", subtitle: "Your CAOSCare assistant", tint: "sky",
    icon: Sparkles, source: { kind: "panel", panel: "aria" }, optional: true, defaultW: 2 },
  { id: "simulation", title: "Simulation", subtitle: "Run controls", tint: "slate",
    icon: PlayCircle, source: { kind: "panel", panel: "simulation" }, optional: true, defaultW: 2 },
];

export const WIDGET_BY_ID = Object.fromEntries(WIDGETS.map((w) => [w.id, w]));

// Default arrangement: the eight boxes of the approved design, one column
// each, in design order. `x` is the order; `w` the column span (1-4).
export function defaultLayout() {
  return WIDGETS.filter((w) => !w.optional).map((w, i) => ({ id: w.id, x: i, y: 0, w: 1, h: 1, hidden: false }));
}

// Keep only known boxes, in saved order; boxes added to the catalog later
// do not appear until the user adds them.
export function normalizeLayout(boxes) {
  const seen = new Set();
  return (boxes || [])
    .filter((b) => WIDGET_BY_ID[b.id] && !seen.has(b.id) && seen.add(b.id))
    .sort((a, b) => a.x - b.x)
    .map((b, i) => ({ ...b, x: i, w: Math.min(4, Math.max(1, b.w || 1)), y: 0, h: 1 }));
}
