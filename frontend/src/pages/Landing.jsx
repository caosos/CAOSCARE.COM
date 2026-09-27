import React from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Shield, Activity, Heart, MapPin, MessageSquare, Zap } from "lucide-react";
import { useAuth } from "../lib/auth";
import { roleHomePath, roleHomeLabel } from "../lib/roleHome";
import ExperienceVideoLibrary from "../components/landing/ExperienceVideoLibrary";

const HERO_IMG =
  "https://images.unsplash.com/photo-1765896387387-0538bc9f997e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w4NTYxODh8MHwxfHNlYXJjaHwxfHxzZW5pb3IlMjByZXNpZGVudCUyMGNhcmVnaXZlciUyMHNtaWxlfGVufDB8fHx8MTc3NjU2NTU1NXww&ixlib=rb-4.1.0&q=85";
const FEATURE_IMG =
  "https://images.pexels.com/photos/18459198/pexels-photo-18459198.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

const features = [
  {
    icon: Zap,
    title: "One-press call",
    body: "A familiar pendant or call button can page staff while Aria provides calm, voice-first support in the resident’s room.",
  },
  {
    icon: MessageSquare,
    title: "Voice companion",
    body: "CAOSCare assistive voice support helps comfort residents, gather context, and route staff-reviewed alerts while care teams respond.",
  },
  {
    icon: MapPin,
    title: "Building awareness · planned",
    body: "Future integrations may help staff understand location and building conditions where compatible systems are available.",
  },
  {
    icon: Activity,
    title: "Staff dashboard",
    body: "Review requests and alerts in the staff workspace on an authorized tablet, phone or computer.",
  },
  {
    icon: Heart,
    title: "Built for low-vision",
    body: "Voice-first interactions and large touch targets help residents who prefer not to use a screen.",
  },
  {
    icon: Shield,
    title: "Paired pendant integration",
    body: "The room node has decoded paired RF pendants in a test room. Other devices and frequencies need compatibility testing before installation.",
  },
];

export default function Landing() {
  // Auth must feel continuous — a signed-in user landing here (clicking the
  // logo, refreshing, coming back later in the same session) sees a way
  // back into the app, never a "sign in again" prompt. `user` stays null
  // until the one-time /auth/me check on app boot resolves, so a first
  // paint briefly shows the guest CTA even for a signed-in user; harmless
  // since Protected routes still gate on the real check, not this button.
  const { user } = useAuth();
  const authedDest = user ? roleHomePath(user) : "/login";
  const authedLabel = user ? roleHomeLabel(user) : "Staff sign in";

  return (
    <div className="min-h-screen bg-caos-bone">
      {/* Top nav */}
      <nav className="flex items-center justify-between px-6 md:px-12 py-5 border-b border-caos-line bg-caos-bone/80 backdrop-blur relative md:sticky md:top-0 z-40">
        <Link to="/" data-testid="nav-home" className="text-2xl">
          <span className="font-display font-bold tracking-tighter text-caos-forest">CAOS</span>
          <span className="font-display font-light text-caos-forest">Care</span>
        </Link>
        <div className="hidden md:flex flex-wrap items-center justify-end gap-3">
          <Link to="/for-residents" className="text-caos-forest px-2">Residents & families</Link>
          <Link to="/for-communities" data-testid="nav-communities" className="text-caos-forest px-2">For communities</Link>
          <Link to="/experience" className="text-caos-forest px-2">Explore a room</Link>
          <Link to="/kiosk/demo" data-testid="nav-kiosk">
            <Button variant="ghost" className="text-caos-forest hover:bg-caos-ambient">
              Try kiosk
            </Button>
          </Link>
          <Link to={authedDest} data-testid={user ? "nav-continue" : "nav-login"}>
            <Button className="bg-caos-forest hover:bg-caos-forest-hover text-white rounded-full px-6">
              {authedLabel}
            </Button>
          </Link>
        </div>
        <details className="md:hidden relative text-caos-forest">
          <summary className="catalog-summary cursor-pointer rounded-full border border-caos-forest px-5 py-2 font-semibold">Explore</summary>
          <div className="absolute right-0 top-full mt-3 w-60 rounded-2xl border border-caos-line bg-white shadow-xl p-3 flex flex-col gap-1 z-50">
            <Link to="/for-residents" className="rounded-lg px-3 py-3">Residents & families</Link>
            <Link to="/for-communities" className="rounded-lg px-3 py-3">For communities</Link>
            <Link to="/experience" className="rounded-lg px-3 py-3">Explore a room</Link>
            <Link to="/kiosk/demo" className="rounded-lg px-3 py-3">Try kiosk</Link>
            <Link to={authedDest} className="rounded-lg px-3 py-3 font-semibold">{authedLabel}</Link>
          </div>
        </details>
      </nav>

      {/* Hero */}
      <section className="px-6 md:px-12 pt-16 md:pt-24 pb-20">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-12 items-center max-w-7xl mx-auto">
          <div className="md:col-span-7 caos-fade-in">
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-6">
              Senior living · Assistive care workflows
            </p>
            <h1 className="font-display text-5xl md:text-6xl lg:text-7xl font-light tracking-tighter leading-[0.95] text-caos-forest">
              Create
              <br />
              <span className="italic">A Resident Experience.</span>
            </h1>
            <div className="mt-8 space-y-2 text-caos-ink/80 max-w-xl">
              <p className="text-base md:text-lg">
                Through <b className="text-caos-forest">Compassionate Adaptive Resident Engagement</b>
              </p>
              <p className="text-base md:text-lg">
                Powered by a <b className="text-caos-forest">Cognitive Adaptive Operating System</b>
              </p>
            </div>
            <p className="mt-8 text-lg text-caos-ink/70 max-w-xl leading-relaxed">
              CAOSCare brings Aria into the room. A resident can speak naturally
              or press a familiar help button; requests reach staff with their
              actual status and history.
            </p>
            <div className="mt-10 flex flex-wrap gap-4">
              <Link to="/kiosk/demo" data-testid="hero-try-kiosk">
                <Button className="caos-emergency-btn caos-kiosk-btn !min-h-[60px] !text-lg !rounded-full px-8">
                  Launch kiosk demo
                </Button>
              </Link>
              <Link to="/for-communities#dashboard" data-testid="hero-staff-dashboard-preview">
                <Button
                  variant="outline"
                  className="rounded-full px-8 h-[60px] text-lg border-2 border-caos-forest text-caos-forest hover:bg-caos-forest hover:text-white"
                >
                  Staff dashboard demo
                </Button>
              </Link>
            </div>
          </div>
          <div className="md:col-span-5 relative caos-fade-in caos-delay-200">
            <div className="relative rounded-[32px] overflow-hidden aspect-[4/5] shadow-2xl shadow-caos-forest/20">
              <img src={HERO_IMG} alt="Caregiver with resident" className="w-full h-full object-cover" />
              <div className="absolute inset-0 bg-caos-forest/15" />
              <div className="absolute bottom-6 left-6 right-6 bg-white/90 backdrop-blur rounded-2xl p-5 border border-caos-line">
                <p className="text-xs font-bold uppercase tracking-widest text-caos-terracotta">Illustrative scene</p>
                <p className="text-lg font-display font-medium text-caos-forest mt-1">
                  "Help is coming, Margaret. Want to tell me about your grandkids while we wait?"
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <ExperienceVideoLibrary />

      {/* Feature grid */}
      <section className="px-6 md:px-12 py-20 bg-caos-ambient">
        <div className="max-w-7xl mx-auto">
          <div className="max-w-2xl mb-16">
            <p className="text-xs font-bold uppercase tracking-[0.22em] text-caos-mute mb-4">Why CAOS</p>
            <h2 className="font-display text-3xl md:text-5xl font-light tracking-tight text-caos-forest">
              Designed for the eighty-year-old<br />who just wants someone to answer.
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <div
                key={f.title}
                className={`bg-white rounded-2xl p-8 border border-caos-line hover:border-caos-forest transition-colors caos-fade-in caos-delay-${(i % 4) * 100}`}
              >
                <div className="w-12 h-12 rounded-xl bg-caos-forest/10 flex items-center justify-center mb-5">
                  <f.icon className="w-6 h-6 text-caos-forest" strokeWidth={2} />
                </div>
                <h3 className="font-display text-xl font-medium text-caos-forest">{f.title}</h3>
                <p className="text-caos-mute mt-3 leading-relaxed">{f.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Split image + text */}
      <section className="px-6 md:px-12 py-24">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-12 gap-12 items-center">
          <div className="md:col-span-5 rounded-[32px] overflow-hidden aspect-square">
            <img src={FEATURE_IMG} alt="Caregiver assisting elderly residents" className="w-full h-full object-cover" />
          </div>
          <div className="md:col-span-7">
            <h2 className="font-display text-4xl md:text-5xl font-light tracking-tight text-caos-forest leading-tight">
              Built on what you already have.
            </h2>
            <p className="text-lg text-caos-ink/75 mt-6 leading-relaxed max-w-xl">
              The hidden room node makes Aria available without a resident tablet.
              Compatible pendants can be paired and tested with the community's setup,
              while staff use their authorized workspaces.
            </p>
            <ul className="mt-8 space-y-3 text-caos-ink">
              <li className="flex gap-3"><span className="w-1 bg-caos-terracotta" />Hidden resident-room node + unobtrusive voice/audio hardware</li>
              <li className="flex gap-3"><span className="w-1 bg-caos-terracotta" />Familiar help pendant, where paired and verified</li>
              <li className="flex gap-3"><span className="w-1 bg-caos-terracotta" />Options for voice, phone and approved room devices</li>
            </ul>
          </div>
        </div>
      </section>

      <footer className="border-t border-caos-line px-6 md:px-12 py-10 text-caos-mute text-sm">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row justify-between gap-4">
          <p>© 2026 CAOSCare. Assistive care workflows for senior living.</p>
          <p>Built for dignity, designed for the people who already paid for one system.</p>
        </div>
      </footer>
    </div>
  );
}
