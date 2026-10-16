import React from "react";
import { Link } from "react-router-dom";
import { RESIDENT_CAPABILITIES } from "../lib/capabilities/resident";
import { CAPABILITIES_BY_ID } from "../lib/capabilities";
import { ILLUSTRATIONS } from "../lib/capabilities/visuals";
import { ExperienceVideo } from "../components/landing/ExperienceVideoLibrary";
import { EXPERIENCE_VIDEOS } from "../lib/experienceVideos";
import CapabilityCard from "../components/capabilities/CapabilityCard";
import CapabilityPanel from "../components/capabilities/CapabilityPanel";
import StatusLegend from "../components/capabilities/StatusLegend";
import useCapabilityPanel from "../components/capabilities/useCapabilityPanel";
import PublicPage, { PublicSection } from "../components/public/PublicPage";
import PublicVisual from "../components/public/PublicVisual";
import RequestJourney from "../components/public/RequestJourney";
import StaffShowcase from "../components/public/StaffShowcase";
import LowVisionProof from "../components/public/LowVisionProof";

// Residents and families (#162): voice first. Aria is the way in; the room
// screen supports her. Cards come from lib/capabilities (one status registry).

export default function ForResidents() {
  const panel = useCapabilityPanel(CAPABILITIES_BY_ID);
  return (
    <PublicPage testid="for-residents">
      <header className="px-4 pb-14 pt-12 sm:px-6 lg:px-8 lg:pt-16">
        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 lg:grid-cols-12">
          <div className="min-w-0 lg:col-span-5">
            <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">For residents & families</p>
            <h1 className="mt-3 text-[34px] font-bold leading-[1.1] tracking-tight sm:text-[46px]">Just say "Hey Aria."</h1>
            <p className="mt-5 text-[18px] leading-relaxed text-[#374151]">
              Aria lives in the room. Talk from your chair or bed and she answers out loud, sends what you ask for to
              the right staff, and tells you its real status. The room screen only shows supporting information,
              and your TV stays your TV.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#how" data-testid="residents-how" className="rounded-lg bg-[#2F80ED] px-5 py-3 text-[16px] font-semibold text-white hover:bg-[#1F6FD9]">See a request travel</a>
              <Link to="/kiosk/demo" data-testid="residents-demo" className="rounded-lg border border-[#D1D5DB] px-5 py-3 text-[16px] font-semibold text-[#111827] hover:border-[#111827]">Try the room screen</Link>
            </div>
            <p className="mt-4 text-[14px] text-[#6B7280]">In pilot in the CAOSCare test room. Not a medical device or emergency service.</p>
          </div>
          <PublicVisual className="lg:col-span-7" eager visual={ILLUSTRATIONS.talk} />
        </div>
      </header>

      <RequestJourney eyebrow="A request, start to finish" title="You ask once. Aria and the staff take it from there." />

      {EXPERIENCE_VIDEOS[0] && (
        <PublicSection id="video" eyebrow="The room is Aria" title="A day with Aria"
          lead="Illustrative scenes of a resident's day, spoken naturally to the room.">
          <div className="max-w-4xl"><ExperienceVideo video={EXPERIENCE_VIDEOS[0]} featured /></div>
        </PublicSection>
      )}

      <PublicSection id="low-vision" tone="gray" eyebrow="Built for low vision" title="Easy to see, and easy to skip."
        lead="Aria is reached by voice, so nobody has to read the screen. When the screen is used, this is what it looks like.">
        <LowVisionProof onOpen={panel.open} />
      </PublicSection>

      <PublicSection id="capabilities" eyebrow="What Aria can help with" title="What exists today, and how far each has been tested"
        lead="Open any card for what it looks like, what happens at each step, and its stated limits.">
        <div className="mb-8"><StatusLegend items={RESIDENT_CAPABILITIES} /></div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {RESIDENT_CAPABILITIES.map((c) => <CapabilityCard key={c.id} capability={c} onOpen={panel.open} />)}
        </div>
      </PublicSection>

      <PublicSection id="staff" tone="gray" eyebrow="How staff respond" title="Your request, on the staff side"
        lead="A request reaches the staff software in your own words. These are real CAOSCare screens with simulated data.">
        <StaffShowcase compact onOpen={panel.open} />
      </PublicSection>


      <PublicSection id="introduction" tone="gray" eyebrow="Getting started" title="A local introduction, together">
        <div className="max-w-3xl text-[17px] leading-relaxed text-[#374151]">
          <p>A resident and a family member can watch a short video, hear Aria in a sample room, try a normal request, and learn which services and devices the community has actually switched on. Staff can explain who receives each request.</p>
          <Link to="/for-communities" className="mt-5 inline-block font-semibold text-[#1D4ED8] hover:underline">How the community uses CAOSCare →</Link>
        </div>
      </PublicSection>
      <CapabilityPanel capability={panel.capability} open={panel.isOpen} onClose={panel.close} onCloseAutoFocus={panel.onCloseAutoFocus} />
    </PublicPage>
  );
}
