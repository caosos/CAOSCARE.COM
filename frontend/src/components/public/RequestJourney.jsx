import React from "react";
import PublicVisual from "./PublicVisual";
import { ILLUSTRATIONS, SCREENS } from "../../lib/capabilities/visuals";

// The one story every public page tells (#162): the resident speaks, Aria
// answers and routes, staff own the work, and every step leaves a receipt.
// Voice first: the room screen only supports what Aria says.
export const JOURNEY = [
  { n: "1", who: "The resident", title: "Says \"Hey Aria\" and asks",
    body: "From a chair or bed, in their own words. No tablet to learn and no menu to find. A help pendant or the help button works too.",
    visual: ILLUSTRATIONS.talk },
  { n: "2", who: "Aria", title: "Answers and sends it to the right department",
    body: "Aria replies out loud, turns the request into one ticket for the right department, and the room screen shows its status at a glance.",
    visual: SCREENS.roomScreen, caption: "public demo room, sample resident" },
  { n: "3", who: "Staff", title: "See it, own it, finish it",
    body: "The request lands in that department's workspace with who is on duty, who owns it and how long it has waited. Overdue work rises to the top.",
    visual: SCREENS.nursing, caption: "simulated 75-resident community, synthetic staff" },
  { n: "4", who: "The record", title: "Every step leaves a receipt",
    body: "Requested, claimed, started, finished: each step records who acted and when. Aria tells the resident the true status, never a guess.",
    visual: SCREENS.activityLog, caption: "simulated community, synthetic data" },
];

export default function RequestJourney({ id = "how", eyebrow = "How it works", title = "One request, from the room to the right person, with proof." }) {
  return (
    <section id={id} className="scroll-mt-20 border-y border-[#E5E7EB] bg-[#F9FAFB] px-4 py-16 sm:px-6 lg:px-8" aria-labelledby={`${id}-title`} data-testid="request-journey">
      <div className="mx-auto max-w-7xl">
        <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">{eyebrow}</p>
        <h2 id={`${id}-title`} className="mt-2 max-w-3xl text-[28px] font-bold leading-tight tracking-tight text-[#111827] sm:text-[36px]">{title}</h2>
        <ol className="mt-10 grid grid-cols-1 gap-10 md:grid-cols-2 xl:grid-cols-4 xl:gap-6">
          {JOURNEY.map((s) => (
            <li key={s.n} className="flex min-w-0 flex-col">
              <div className="flex items-baseline gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[#111827] text-[15px] font-bold text-white">{s.n}</span>
                <span className="text-[13px] font-semibold uppercase tracking-[0.12em] text-[#6B7280]">{s.who}</span>
              </div>
              <h3 className="mt-3 text-[20px] font-semibold text-[#111827]">{s.title}</h3>
              <p className="mt-2 flex-1 text-[16px] leading-relaxed text-[#4B5563]">{s.body}</p>
              <PublicVisual className="mt-5" visual={s.visual} caption={s.caption} />
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
