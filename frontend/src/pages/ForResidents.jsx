import React from "react";
import { Link } from "react-router-dom";
import { RESIDENT_CAPABILITIES } from "../lib/capabilities/resident";
import { CAPABILITIES_BY_ID } from "../lib/capabilities";
import { ExperienceVideo } from "../components/landing/ExperienceVideoLibrary";
import { EXPERIENCE_VIDEOS } from "../lib/experienceVideos";
import CapabilityCard from "../components/capabilities/CapabilityCard";
import CapabilityPanel from "../components/capabilities/CapabilityPanel";
import StatusLegend from "../components/capabilities/StatusLegend";
import StaffDashboardShowcase from "../components/capabilities/StaffDashboardShowcase";
import useCapabilityPanel from "../components/capabilities/useCapabilityPanel";

// Cards in two groups: what exists today (any stage) and what is planned.
const AVAILABLE = RESIDENT_CAPABILITIES.filter((c) => c.status !== "planned");
const PLANNED = RESIDENT_CAPABILITIES.filter((c) => c.status === "planned");

export default function ForResidents() {
  const panel = useCapabilityPanel(CAPABILITIES_BY_ID);
  return (
    <div className="min-h-screen bg-caos-bone text-caos-ink" data-testid="for-residents">
      <nav className="px-6 md:px-12 py-6 border-b border-caos-line flex flex-wrap items-center justify-between gap-4">
        <Link to="/" className="text-2xl text-caos-forest"><span className="font-display font-bold tracking-tighter">CAOS</span><span className="font-display font-light">Care</span></Link>
        <div className="flex flex-wrap gap-5 text-caos-forest">
          <Link to="/for-communities">For communities</Link>
          <Link to="/experience">Explore a room</Link>
          <Link to="/login">Staff sign in</Link>
        </div>
      </nav>
      <main className="max-w-7xl mx-auto px-6 md:px-12 py-14 space-y-20">
        <header className="max-w-4xl">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">For residents & families</p>
          <h1 className="font-display text-4xl md:text-6xl font-light text-caos-forest mt-4">The room is Aria.</h1>
          <p className="text-lg leading-relaxed mt-6">Speak naturally from your chair or bed. The room has a small computer and audio device, while your TV remains your TV. A familiar handset is also part of the design for residents who prefer a phone.</p>
          <Link to="/experience" className="inline-block mt-7 rounded-full bg-caos-forest text-white px-6 py-3">Explore a sample room</Link>
        </header>
        {EXPERIENCE_VIDEOS[0] && (
          <section className="max-w-3xl" aria-label="Resident experience video">
            <ExperienceVideo video={EXPERIENCE_VIDEOS[0]} featured />
          </section>
        )}
        <section aria-labelledby="resident-heading">
          <h2 id="resident-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">What Aria can help with</h2>
          <p className="mb-6 max-w-3xl">Open any card to see what it looks like, what happens at each step, and exactly how far it has been built and tested.</p>
          <div className="mb-8"><StatusLegend items={RESIDENT_CAPABILITIES} /></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {AVAILABLE.map((c) => <CapabilityCard key={c.id} capability={c} onOpen={panel.open} />)}
          </div>
        </section>
        <section aria-labelledby="staff-respond-heading">
          <h2 id="staff-respond-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">How staff respond</h2>
          <p className="mb-6 max-w-3xl">A resident's request reaches the staff software with their own words. These are real CAOSCare screens with sample data.</p>
          <StaffDashboardShowcase onOpen={panel.open} compact />
        </section>
        <section aria-labelledby="design-heading">
          <h2 id="design-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">Planned</h2>
          <p className="mb-6 max-w-3xl">Designed but not available yet. Devices will come from a small list approved for each community; availability, setup and pricing will be shown once verified.</p>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {PLANNED.map((c) => <CapabilityCard key={c.id} capability={c} onOpen={panel.open} />)}
          </div>
        </section>
        <section className="rounded-3xl bg-caos-ambient p-8 md:p-12">
          <h2 className="font-display text-3xl text-caos-forest">A local introduction, together</h2>
          <p className="mt-4 max-w-3xl">A resident and family member can see a short video, hear Aria in a sample room, try a normal request, and learn which services and devices the community has actually enabled. Staff can explain who receives each request and how to call the front desk.</p>
          <Link to="/for-communities" className="inline-block mt-5 text-caos-forest underline underline-offset-4">How the community uses CAOSCare</Link>
        </section>
      </main>
      <CapabilityPanel capability={panel.capability} open={panel.isOpen} onClose={panel.close}
        onCloseAutoFocus={panel.onCloseAutoFocus} />
    </div>
  );
}
