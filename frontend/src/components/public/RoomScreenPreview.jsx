import React from "react";
import { Link } from "react-router-dom";
import PublicPage, { PublicSection } from "./PublicPage";
import { VisualImage, VISUAL_TAG } from "../capabilities/CapabilityVisuals";
import { SCREENS } from "../../lib/capabilities/visuals";

// What /kiosk/demo shows when this site has no public demo room switched on
// (#162: the public "Try the room screen" link must never dead-end). Real
// room-screen captures from the demo room, said plainly.
const VIEWS = [
  { visual: SCREENS.roomScreen, title: "Everyday view", body: "A greeting, the time, one large help button and a talk button. Aria is reached by voice; the screen only supports her." },
  { visual: SCREENS.roomContrast, title: "High contrast", body: "One tap, or ask Aria, and the whole screen turns amber on black." },
  { visual: SCREENS.roomEnlarged, title: "Larger text", body: "The + and − buttons, or asking Aria, enlarge the whole screen from 50% to 200%." },
];

export default function RoomScreenPreview() {
  return (
    <PublicPage testid="room-screen-preview">
      <PublicSection id="preview" eyebrow="Room screen demo" title="The live demo room isn't switched on at this site right now."
        lead="Here is the real room screen from the CAOSCare demo room instead, with a sample resident. In a room, residents mostly talk to Aria; the screen is an ambient display with large controls when they want them.">
        <ul className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {VIEWS.map((v) => (
            <li key={v.title} className="min-w-0">
              <figure className="m-0 overflow-hidden rounded-xl border border-[#E5E7EB] bg-white">
                <VisualImage visual={v.visual} className="w-full" />
                <figcaption className="border-t border-[#E5E7EB] p-4">
                  <span className="block text-[12px] font-semibold uppercase tracking-[0.08em] text-[#6B7280]">{VISUAL_TAG[v.visual.kind]}</span>
                  <span className="mt-1 block text-[18px] font-semibold text-[#111827]">{v.title}</span>
                  <span className="mt-1 block text-[15px] text-[#4B5563]">{v.body}</span>
                </figcaption>
              </figure>
            </li>
          ))}
        </ul>
        <div className="mt-8 flex flex-wrap gap-3">
          <Link to="/for-residents" data-testid="preview-residents" className="rounded-lg bg-[#2F80ED] px-5 py-3 text-[16px] font-semibold text-white hover:bg-[#1F6FD9]">What living with Aria is like</Link>
          <Link to="/experience" data-testid="preview-experience" className="rounded-lg border border-[#D1D5DB] px-5 py-3 text-[16px] font-semibold text-[#111827] hover:border-[#111827]">Explore a room</Link>
        </div>
      </PublicSection>
    </PublicPage>
  );
}
