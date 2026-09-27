import React from "react";
import { Link } from "react-router-dom";
import PublicCatalog from "../components/landing/PublicCatalog";
import { RESIDENT_AREAS, WEARABLE_AREAS } from "../lib/publicOnboarding";
import { ExperienceVideo } from "../components/landing/ExperienceVideoLibrary";
import { EXPERIENCE_VIDEOS } from "../lib/experienceVideos";

export default function ForResidents() {
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
        {EXPERIENCE_VIDEOS[0] && <section className="max-w-3xl" aria-label="Resident experience video"><ExperienceVideo video={EXPERIENCE_VIDEOS[0]} featured /></section>}
        <section aria-labelledby="resident-heading">
          <h2 id="resident-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">What Aria can help with</h2>
          <p className="mb-7">Open each area to see the experience and its current development stage.</p>
          <PublicCatalog items={RESIDENT_AREAS} label="Resident experience areas" />
        </section>
        <section aria-labelledby="wearables-heading">
          <h2 id="wearables-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-4">Wearables & room options</h2>
          <p className="mb-7 max-w-3xl">Residents choose from a small catalog of devices approved for their community. Availability, setup and pricing will be shown with the room package once verified.</p>
          <PublicCatalog items={WEARABLE_AREAS} label="Wearables and room options" />
        </section>
        <section className="rounded-3xl bg-caos-ambient p-8 md:p-12">
          <h2 className="font-display text-3xl text-caos-forest">A local introduction, together</h2>
          <p className="mt-4 max-w-3xl">A resident and family member can see a short video, hear Aria in a sample room, try a normal request, and learn which services and devices the community has actually enabled. Staff can explain who receives each request and how to call the front desk.</p>
          <Link to="/for-communities" className="inline-block mt-5 text-caos-forest underline underline-offset-4">How the community uses CAOSCare</Link>
        </section>
      </main>
    </div>
  );
}
