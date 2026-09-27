import React, { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { COMMUNITY_WORKFLOWS } from "../lib/capabilities/community";
import { CAPABILITIES_BY_ID } from "../lib/capabilities";
import CapabilityCard from "../components/capabilities/CapabilityCard";
import CapabilityPanel from "../components/capabilities/CapabilityPanel";
import StaffDashboardShowcase from "../components/capabilities/StaffDashboardShowcase";
import StatusLegend from "../components/capabilities/StatusLegend";
import useCapabilityPanel from "../components/capabilities/useCapabilityPanel";

// The staff dashboard has its own section; the grid holds the departments.
const DEPARTMENTS = COMMUNITY_WORKFLOWS.filter((c) => c.id !== "staff_dashboard");

export default function ForCommunities() {
  const { hash } = useLocation();
  const panel = useCapabilityPanel(CAPABILITIES_BY_ID);
  useEffect(() => {
    if (hash === "#dashboard") document.getElementById("dashboard")?.scrollIntoView();
  }, [hash]);
  return (
    <div className="min-h-screen bg-caos-bone text-caos-ink" data-testid="for-communities">
      <nav className="px-6 md:px-12 py-6 border-b border-caos-line flex flex-wrap items-center justify-between gap-4">
        <Link to="/" className="text-2xl text-caos-forest"><span className="font-display font-bold tracking-tighter">CAOS</span><span className="font-display font-light">Care</span></Link>
        <div className="flex flex-wrap gap-5 text-caos-forest">
          <Link to="/for-residents">Residents & families</Link>
          <Link to="/experience">Explore a room</Link>
          <Link to="/login">Staff sign in</Link>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 md:px-12 py-14 space-y-20">
        <header className="max-w-4xl">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">For communities</p>
          <h1 className="font-display text-4xl md:text-6xl font-light text-caos-forest mt-4">See how the community works together.</h1>
          <p className="text-lg leading-relaxed mt-6">
            A resident speaks to Aria. A request reaches the right staff workspace.
            The front desk and community leaders see what has been requested,
            acknowledged, assigned and completed. Each step stays tied to the resident's real record.
          </p>
          <a href="#dashboard" className="inline-block mt-7 rounded-full bg-caos-forest text-white px-6 py-3">Open the staff dashboard demo</a>
        </header>

        <section id="dashboard" aria-labelledby="dashboard-heading" className="scroll-mt-28">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Public demonstration</p>
          <h2 id="dashboard-heading" className="font-display text-3xl md:text-5xl text-caos-forest mt-3">Staff dashboard demo</h2>
          <p className="mt-4 mb-8 max-w-3xl">Screens from the actual CAOSCare staff software, captured with sample data. Nothing here is a live record and it does not sign anyone in. Staff at a community use <Link to="/login" className="underline underline-offset-4">Staff sign in</Link>.</p>
          <StaffDashboardShowcase onOpen={panel.open} />
        </section>

        <section aria-labelledby="workflows-heading">
          <h2 id="workflows-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">Every department, and where it stands</h2>
          <p className="mb-6 max-w-3xl">Open a department to see its real screens, what happens at each step, and what has not yet been accepted in real staff use.</p>
          <div className="mb-8"><StatusLegend items={DEPARTMENTS} /></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {DEPARTMENTS.map((c) => <CapabilityCard key={c.id} capability={c} onOpen={panel.open} />)}
          </div>
        </section>

        <section className="rounded-3xl bg-caos-forest text-white p-8 md:p-12">
          <h2 className="font-display text-3xl">Bring the experience into a community</h2>
          <p className="mt-4 max-w-3xl">Introduce the room to residents and families locally. Set up authorized staff roles, the front desk, departments, room profiles and approved devices before offering a resident package. Community data and capabilities must be verified for each installation.</p>
          <Link to="/for-residents" className="inline-block mt-6 underline underline-offset-4">See the resident and family experience</Link>
        </section>
      </main>
      <CapabilityPanel capability={panel.capability} open={panel.isOpen} onClose={panel.close}
        onCloseAutoFocus={panel.onCloseAutoFocus} />
    </div>
  );
}
