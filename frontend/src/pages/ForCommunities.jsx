import React, { useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { COMMUNITY_AREAS, STATUS } from "../lib/publicOnboarding";
import PublicCatalog, { Status } from "../components/landing/PublicCatalog";

export default function ForCommunities() {
  const { hash } = useLocation();
  const [activeId, setActiveId] = useState(COMMUNITY_AREAS[0].id);
  const active = COMMUNITY_AREAS.find((item) => item.id === activeId);
  const detailRef = useRef(null);
  const selectService = (id) => {
    setActiveId(id);
    if (window.innerWidth < 1024) {
      requestAnimationFrame(() => detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }));
    }
  };
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
          <a href="#dashboard" className="inline-block mt-7 rounded-full bg-caos-forest text-white px-6 py-3">Explore the staff dashboard preview</a>
        </header>

        <section id="dashboard" aria-labelledby="dashboard-heading" className="scroll-mt-28">
          <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Public demonstration</p>
          <h2 id="dashboard-heading" className="font-display text-3xl md:text-5xl text-caos-forest mt-3">Staff dashboard preview</h2>
          <p className="mt-4 max-w-3xl">These are illustrative records showing the intended staff experience. This preview has no resident data and does not sign anyone into a community.</p>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5 mt-8">
            <div className="lg:col-span-1 flex flex-col gap-2" role="group" aria-label="Choose a service">
              {COMMUNITY_AREAS.map((item) => (
                <button key={item.id} type="button" onClick={() => selectService(item.id)}
                  aria-pressed={activeId === item.id}
                  className={`text-left rounded-xl px-4 py-3 border min-h-[48px] ${activeId === item.id ? "border-caos-forest bg-caos-ambient" : "border-caos-line bg-white"}`}>
                  {item.name}
                </button>
              ))}
            </div>
            <article ref={detailRef} className="lg:col-span-2 rounded-3xl bg-white border border-caos-line p-7 md:p-10 scroll-mt-5" aria-live="polite">
              <p className="text-xs uppercase tracking-widest text-caos-mute">Sample Community · illustrative preview</p>
              <h3 className="font-display text-3xl text-caos-forest mt-5">{active.name}</h3>
              <Status value={active.status} />
              <p className="mt-6 text-lg">{active.description}</p>
              <div className="mt-6 rounded-xl bg-caos-ambient p-5">
                <p className="text-xs font-bold uppercase tracking-widest text-caos-mute">Example row · sample data</p>
                <p className="mt-2 font-medium">{active.example}</p>
              </div>
              <p className="mt-6"><b>What staff would do:</b> {active.staff}</p>
              <p className="text-sm text-caos-mute mt-6">{STATUS[active.status].label} describes this service's development stage, not the sample row.</p>
            </article>
          </div>
        </section>

        <section aria-labelledby="areas-heading">
          <h2 id="areas-heading" className="font-display text-3xl md:text-4xl text-caos-forest mb-5">Explore every service area</h2>
          <p className="mb-7">Open a service to see what a resident experiences and how staff use it.</p>
          <PublicCatalog items={COMMUNITY_AREAS} label="Community service areas" />
        </section>
        <section className="rounded-3xl bg-caos-forest text-white p-8 md:p-12">
          <h2 className="font-display text-3xl">Bring the experience into a community</h2>
          <p className="mt-4 max-w-3xl">Introduce the room to residents and families locally. Set up authorized staff roles, the front desk, departments, room profiles and approved devices before offering a resident package. Community data and capabilities must be verified for each installation.</p>
          <Link to="/for-residents" className="inline-block mt-6 underline underline-offset-4">See the resident and family experience</Link>
        </section>
      </main>
    </div>
  );
}
