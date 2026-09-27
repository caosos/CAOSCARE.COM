import React from "react";
import { Link } from "react-router-dom";
import PublicCatalog from "../components/landing/PublicCatalog";
import { RESIDENT_AREAS, WEARABLE_AREAS } from "../lib/publicOnboarding";
import { RESIDENT_BY_ID, RESIDENT_CAPABILITIES } from "../lib/capabilities/resident";
import { ExperienceVideo } from "../components/landing/ExperienceVideoLibrary";
import { EXPERIENCE_VIDEOS } from "../lib/experienceVideos";
import CapabilityCard from "../components/capabilities/CapabilityCard";
import CapabilityDemo from "../components/capabilities/CapabilityDemo";
import StatusLegend from "../components/capabilities/StatusLegend";
import StaffResponsePreview from "../components/capabilities/StaffResponsePreview";
import useCapabilityDemo from "../components/capabilities/useCapabilityDemo";

export default function ForResidents() {
  const demo = useCapabilityDemo(RESIDENT_BY_ID);
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
            <p className="text-sm text-caos-mute mt-3">Illustrative film. It includes planned features, such as family video calls, that are not available yet.</p>
          </section>
        )}
        <section aria-labelledby="resident-heading">
          <h2 id="resident-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">What Aria can help with</h2>
          <p className="mb-6 max-w-3xl">Select a card to see, step by step, what the resident says, what CAOSCare does, and what comes back.</p>
          <div className="mb-8"><StatusLegend /></div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {RESIDENT_CAPABILITIES.map((c) => <CapabilityCard key={c.id} capability={c} onOpen={demo.open} />)}
          </div>
        </section>
        <StaffResponsePreview />
        <section aria-labelledby="design-heading">
          <h2 id="design-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">Also in design</h2>
          <p className="mb-7 max-w-3xl">Phone, calling, messages and wearables. Devices come from a small catalog approved for each community; availability, setup and pricing will be shown with the room package once verified.</p>
          <PublicCatalog items={[...RESIDENT_AREAS, ...WEARABLE_AREAS]} label="Planned resident options" />
        </section>
        <section className="rounded-3xl bg-caos-ambient p-8 md:p-12">
          <h2 className="font-display text-3xl text-caos-forest">A local introduction, together</h2>
          <p className="mt-4 max-w-3xl">A resident and family member can see a short video, hear Aria in a sample room, try a normal request, and learn which services and devices the community has actually enabled. Staff can explain who receives each request and how to call the front desk.</p>
          <Link to="/for-communities" className="inline-block mt-5 text-caos-forest underline underline-offset-4">How the community uses CAOSCare</Link>
        </section>
      </main>
      <CapabilityDemo capability={demo.capability} open={demo.isOpen} onClose={demo.close}
        onCloseAutoFocus={demo.onCloseAutoFocus} />
    </div>
  );
}
