import React, { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { COMMUNITY_WORKFLOWS } from "../lib/capabilities/community";
import { CAPABILITIES_BY_ID } from "../lib/capabilities";
import { SCREENS } from "../lib/capabilities/visuals";
import CapabilityCard from "../components/capabilities/CapabilityCard";
import CapabilityPanel from "../components/capabilities/CapabilityPanel";
import StatusLegend from "../components/capabilities/StatusLegend";
import useCapabilityPanel from "../components/capabilities/useCapabilityPanel";
import PublicPage, { PublicSection } from "../components/public/PublicPage";
import PublicVisual from "../components/public/PublicVisual";
import RequestJourney from "../components/public/RequestJourney";
import StaffShowcase from "../components/public/StaffShowcase";

// Communities (#162): what staff and leaders actually use, shown with the
// current Operations product (simulated community, synthetic data). The staff
// workspace has its own section; the grid holds the departments.
const DEPARTMENTS = COMMUNITY_WORKFLOWS.filter((c) => c.id !== "staff_dashboard");

export default function ForCommunities() {
  const { hash } = useLocation();
  const panel = useCapabilityPanel(CAPABILITIES_BY_ID);
  useEffect(() => {
    // "#dashboard" is the old anchor for the staff section; keep links to it working.
    const id = hash === "#dashboard" ? "staff" : hash.slice(1);
    if (id) document.getElementById(id)?.scrollIntoView();
  }, [hash]);
  return (
    <PublicPage testid="for-communities">
      <header className="px-4 pb-14 pt-12 sm:px-6 lg:px-8 lg:pt-16">
        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 lg:grid-cols-12">
          <div className="min-w-0 lg:col-span-5">
            <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">For communities</p>
            <h1 className="mt-3 text-[34px] font-bold leading-[1.1] tracking-tight sm:text-[46px]">Every request reaches the right department, with an owner and a clock.</h1>
            <p className="mt-5 text-[18px] leading-relaxed text-[#374151]">
              A resident speaks to Aria. The request lands in the right department's workspace. The front desk and
              leaders see what was requested, claimed, started and finished, and every step is tied to the resident's record.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <a href="#staff" data-testid="communities-staff" className="rounded-lg bg-[#2F80ED] px-5 py-3 text-[16px] font-semibold text-white hover:bg-[#1F6FD9]">See what staff see</a>
              <a href="#departments" data-testid="communities-departments" className="rounded-lg border border-[#D1D5DB] px-5 py-3 text-[16px] font-semibold text-[#111827] hover:border-[#111827]">Every department</a>
            </div>
            <p className="mt-4 text-[14px] text-[#6B7280]">In pilot: proven with test staff accounts and a simulated 75-resident community. Not yet used by a community's staff in a real shift.</p>
          </div>
          <PublicVisual className="lg:col-span-7" eager visual={SCREENS.overview}
            caption="Operations overview · simulated 75-resident community, synthetic residents and staff" />
        </div>
      </header>

      <RequestJourney eyebrow="The workflow" title="From the resident's words to a finished, recorded job." />

      <PublicSection id="staff" eyebrow="What staff see" title="One workspace, the same records Aria uses"
        lead="Real CAOSCare screens, captured from a simulated community. Nothing here is a live record and it does not sign anyone in.">
        <StaffShowcase onOpen={panel.open} />
      </PublicSection>

      <PublicSection id="departments" tone="gray" eyebrow="Departments" title="Every department, and where it stands"
        lead="Open a department to see its current screen, what happens at each step, and what has not yet been accepted in real staff use.">
        <div className="mb-8"><StatusLegend items={DEPARTMENTS} /></div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {DEPARTMENTS.map((c) => <CapabilityCard key={c.id} capability={c} onOpen={panel.open} />)}
        </div>
      </PublicSection>

      <PublicSection id="start" eyebrow="Getting started" title="Bring CAOSCare into a community">
        <div className="max-w-3xl text-[17px] leading-relaxed text-[#374151]">
          <p>Introduce the room to residents and families locally. Set up staff roles, the front desk, departments, room profiles and approved devices before offering it to residents. Every installation's data and capabilities are verified on site.</p>
          <Link to="/for-residents" className="mt-5 inline-block font-semibold text-[#1D4ED8] hover:underline">See the resident and family experience →</Link>
        </div>
      </PublicSection>
      <CapabilityPanel capability={panel.capability} open={panel.isOpen} onClose={panel.close} onCloseAutoFocus={panel.onCloseAutoFocus} />
    </PublicPage>
  );
}
