import React from "react";
import { Link } from "react-router-dom";
import { CAPABILITIES_BY_ID } from "../lib/capabilities";
import { SCREENS } from "../lib/capabilities/visuals";
import CapabilityPanel from "../components/capabilities/CapabilityPanel";
import useCapabilityPanel from "../components/capabilities/useCapabilityPanel";
import ExperienceVideoLibrary from "../components/landing/ExperienceVideoLibrary";
import LandingStatus from "../components/landing/LandingStatus";
import LandingPaths from "../components/landing/LandingPaths";
import PublicPage, { PublicSection } from "../components/public/PublicPage";
import PublicVisual from "../components/public/PublicVisual";
import RequestJourney from "../components/public/RequestJourney";
import StaffShowcase from "../components/public/StaffShowcase";

// Public home (#162). In order: what CAOSCare is, the request journey, what
// staff see, why receipts matter, what works today, where to go next. Every
// picture says whose data it is; every status comes from lib/capabilities/status.js.
const PROOF = [
  ["Who asked, in their words", "The request keeps the resident's own words, room and time."],
  ["Who owns it, and since when", "Each claim, start and finish is stamped with the person and the minute."],
  ["What really happened", "Aria and the room screen report the recorded status, so nobody is told \"someone is on the way\" unless it is true."],
];

export default function Landing() {
  const panel = useCapabilityPanel(CAPABILITIES_BY_ID);
  return (
    <PublicPage testid="landing">
      {({ authedDest, authedLabel }) => (
        <>
          <header className="px-4 pb-16 pt-12 sm:px-6 lg:px-8 lg:pt-16">
            <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 lg:grid-cols-12">
              <div className="min-w-0 lg:col-span-5">
                <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">Resident support and care coordination</p>
                <h1 className="mt-3 text-[34px] font-bold leading-[1.1] tracking-tight sm:text-[46px]">
                  Residents talk to Aria. Staff see the work. Every step is on record.
                </h1>
                <p className="mt-5 text-[18px] leading-relaxed text-[#374151]">
                  CAOSCare is the operating system for a senior-living community. A resident says "Hey Aria" from
                  their chair; the request reaches the right department with who owns it and how long it has waited,
                  and the resident hears its real status.
                </p>
                <div className="mt-8 flex flex-wrap gap-3">
                  <a href="#how" data-testid="hero-how"
                     className="rounded-lg bg-[#2F80ED] px-5 py-3 text-[16px] font-semibold text-white hover:bg-[#1F6FD9]">See how it works</a>
                  <Link to="/for-communities" data-testid="hero-communities"
                        className="rounded-lg border border-[#D1D5DB] bg-white px-5 py-3 text-[16px] font-semibold text-[#111827] hover:border-[#111827]">For communities</Link>
                </div>
                <p className="mt-5 text-[16px] text-[#374151]">
                  Residents and families:{" "}
                  <Link to="/for-residents" data-testid="hero-residents" className="font-semibold text-[#111827] underline underline-offset-4">what living with Aria is like</Link>
                </p>
                <p className="mt-4 text-[14px] text-[#6B7280]">In pilot · assistive and staff-supervised, not a medical device or emergency service.</p>
              </div>
              <PublicVisual className="lg:col-span-7" eager visual={SCREENS.workspace}
                caption="My CAOSCare Workspace · simulated 75-resident community, synthetic residents and staff" />
            </div>
          </header>

          <RequestJourney />

          <PublicSection id="staff" eyebrow="What staff see" title="The work, the owner and the clock, in one place."
            lead="Staff work in their department's view of the same records Aria uses. Leaders see what needs attention across the community.">
            <StaffShowcase onOpen={panel.open} />
          </PublicSection>

          <PublicSection id="proof" tone="gray" eyebrow="Why receipts" title="Proof, not promises."
            lead="Senior living runs on trust. CAOSCare records every step of every request, so families, staff and leaders can see what was asked and what was done.">
            <ul className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {PROOF.map(([t, b]) => (
                <li key={t} className="rounded-xl border border-[#E5E7EB] bg-white p-5">
                  <h3 className="text-[18px] font-semibold text-[#111827]">{t}</h3>
                  <p className="mt-2 text-[15px] leading-relaxed text-[#4B5563]">{b}</p>
                </li>
              ))}
            </ul>
          </PublicSection>

          <LandingStatus onOpen={panel.open} />
          <ExperienceVideoLibrary />
          <LandingPaths authedDest={authedDest} authedLabel={authedLabel} />
          <CapabilityPanel capability={panel.capability} open={panel.isOpen} onClose={panel.close}
            onCloseAutoFocus={panel.onCloseAutoFocus} />
        </>
      )}
    </PublicPage>
  );
}
