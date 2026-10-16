import React from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { roleHomePath, roleHomeLabel } from "../lib/roleHome";
import { CAPABILITIES_BY_ID } from "../lib/capabilities";
import CapabilityPanel from "../components/capabilities/CapabilityPanel";
import useCapabilityPanel from "../components/capabilities/useCapabilityPanel";
import ExperienceVideoLibrary from "../components/landing/ExperienceVideoLibrary";
import LandingNav from "../components/landing/LandingNav";
import LandingFlow from "../components/landing/LandingFlow";
import LandingStatus from "../components/landing/LandingStatus";
import LandingPaths from "../components/landing/LandingPaths";
import ProductShot from "../components/landing/ProductShot";

// Public home (owner review 2026-10-15): product first. The hero shows the real
// Operations workspace; every picture says whose data it is; every capability
// status comes from lib/capabilities/status.js.
export default function Landing() {
  // A signed-in visitor sees a way back into the app, never "sign in again".
  // `user` is null until the one-time /auth/me check resolves; Protected
  // routes still gate on the real check, not this link.
  const { user } = useAuth();
  const panel = useCapabilityPanel(CAPABILITIES_BY_ID);
  const authedDest = user ? roleHomePath(user) : "/login";
  const authedLabel = user ? roleHomeLabel(user) : "Staff sign in";

  return (
    <div className="ws-root min-h-screen overflow-x-hidden bg-white text-[#111827]">
      <LandingNav authedDest={authedDest} authedLabel={authedLabel} signedIn={!!user} />

      <header className="px-4 pb-16 pt-12 sm:px-6 lg:px-8 lg:pt-16">
        <div className="mx-auto grid max-w-7xl grid-cols-1 items-center gap-10 lg:grid-cols-12">
          <div className="min-w-0 lg:col-span-5">
            <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">
              Create A Resident Experience
            </p>
            <h1 className="mt-3 text-[34px] font-bold leading-[1.1] tracking-tight sm:text-[46px]">
              The operating system for a senior-living community.
            </h1>
            <p className="mt-5 text-[18px] leading-relaxed text-[#374151]">
              Residents ask Aria by voice or press a help button. CAOSCare sends each request to the
              right department, shows staff who owns it and how long it has waited, and keeps a
              receipt for every step.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/experience" data-testid="hero-explore-room"
                    className="rounded-lg bg-[#2F80ED] px-5 py-3 text-[16px] font-semibold text-white hover:bg-[#1F6FD9]">
                Explore a room
              </Link>
              <Link to="/for-communities" data-testid="hero-communities"
                    className="rounded-lg border border-[#D1D5DB] bg-white px-5 py-3 text-[16px] font-semibold text-[#111827] hover:border-[#111827]">
                For communities
              </Link>
            </div>
            <p className="mt-5 text-[16px] text-[#374151]">
              Residents and families:{" "}
              <Link to="/for-residents" data-testid="hero-residents" className="font-semibold text-[#111827] underline underline-offset-4">
                what living with Aria is like
              </Link>
            </p>
            <p className="mt-4 text-[14px] text-[#6B7280]">
              In pilot · assistive and staff-supervised, not a medical device or emergency service.
            </p>
          </div>
          <ProductShot className="min-w-0 lg:col-span-7" eager
                       src="/media/product/workspace.jpg" label="My CAOSCare Workspace"
                       alt="The CAOSCare Operations workspace: resident calls, tasks in progress, staff on duty, residents and department boxes"
                       caption="Real CAOSCare Operations workspace · simulated 75-resident community, synthetic residents and staff." />
        </div>
      </header>

      <LandingFlow />
      <LandingStatus onOpen={panel.open} />
      <ExperienceVideoLibrary />
      <LandingPaths authedDest={authedDest} authedLabel={authedLabel} />

      <footer className="border-t border-[#E5E7EB] px-4 py-8 text-[14px] text-[#6B7280] sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 sm:flex-row">
          <p>© 2026 CAOSCare. Assistive, human-supervised operations for senior living.</p>
          <p>Every action has a receipt. Every receipt has a source.</p>
        </div>
      </footer>
      <CapabilityPanel capability={panel.capability} open={panel.isOpen} onClose={panel.close}
        onCloseAutoFocus={panel.onCloseAutoFocus} />
    </div>
  );
}
