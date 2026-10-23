import React from "react";
import { CONCEPTS } from "../../lib/capabilities/visuals";
import PublicVisual from "../public/PublicVisual";
import { PublicSection } from "../public/PublicPage";

// Home One (#165, owner 2026-10-23: "add them in the system and showcase it").
// A design concept, shown as one and nothing more: no unit is built or tested, so
// it is not a capability and stays out of lib/capabilities/status.js.
// Source renders and parts plans: docs/hardware/home-one/.
const IDEAS = [
  ["One device in the room", "Aria's microphones, speaker and the room's radios would sit in a single appliance, instead of a speakerphone wired to a computer."],
  ["Designed for outages", "A backup battery, so the device could keep listening when the power drops."],
  ["Same Aria, same records", "It would connect to the same CAOSCare departments, requests and receipts as today."],
];

export default function HomeOneConcept() {
  return (
    <PublicSection id="home-one" tone="gray" eyebrow="What we're designing next" title="Home One"
      lead="Today Aria runs in our test apartment on a conference speakerphone connected to the community's central computer. Home One is our design for a single room device. It is a concept: none has been built or tested yet.">
      <div className="grid grid-cols-1 items-center gap-8 lg:grid-cols-12" data-testid="home-one-concept">
        <PublicVisual visual={CONCEPTS.homeOne} className="lg:col-span-7" />
        <ul className="grid grid-cols-1 gap-4 lg:col-span-5">
          {IDEAS.map(([t, b]) => (
            <li key={t} className="rounded-xl border border-[#E5E7EB] bg-white p-5">
              <h3 className="text-[18px] font-semibold text-[#111827]">{t}</h3>
              <p className="mt-2 text-[15px] leading-relaxed text-[#4B5563]">{b}</p>
            </li>
          ))}
        </ul>
      </div>
    </PublicSection>
  );
}
