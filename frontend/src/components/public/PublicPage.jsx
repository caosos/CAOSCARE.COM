import React from "react";
import { useAuth } from "../../lib/auth";
import { roleHomePath, roleHomeLabel } from "../../lib/roleHome";
import LandingNav from "../landing/LandingNav";

// The one shell for every public page (/, /for-residents, /for-communities,
// /experience): the same nav, type, colours and footer as the landing page,
// which follows the authenticated Care App (#162, owner 2026-10-15).
// A signed-in visitor gets a way back into the app instead of "Staff sign in".
export default function PublicPage({ children, testid }) {
  const { user } = useAuth();
  const authedDest = user ? roleHomePath(user) : "/login";
  const authedLabel = user ? roleHomeLabel(user) : "Staff sign in";
  return (
    <div className="ws-root min-h-screen overflow-x-hidden bg-white text-[#111827]" data-testid={testid}>
      <LandingNav authedDest={authedDest} authedLabel={authedLabel} signedIn={!!user} />
      {typeof children === "function" ? children({ authedDest, authedLabel }) : children}
      <footer className="border-t border-[#E5E7EB] px-4 py-8 text-[14px] text-[#6B7280] sm:px-6 lg:px-8">
        <div className="mx-auto flex max-w-7xl flex-col justify-between gap-2 sm:flex-row">
          <p>© 2026 CAOSCare. Assistive, human-supervised operations for senior living. Not a medical device or emergency service.</p>
          <p>Every action has a receipt. Every receipt has a source.</p>
        </div>
      </footer>
    </div>
  );
}

// A public section: eyebrow, heading and an optional lead paragraph, in the
// landing page's type scale.
export function PublicSection({ id, eyebrow, title, lead, children, className = "", tone = "white" }) {
  const bg = tone === "gray" ? "bg-[#F9FAFB] border-y border-[#E5E7EB]" : "bg-white";
  return (
    <section id={id} aria-labelledby={id ? `${id}-title` : undefined}
             className={`scroll-mt-20 px-4 py-14 sm:px-6 lg:px-8 ${bg} ${className}`}>
      <div className="mx-auto max-w-7xl">
        {eyebrow && <p className="text-[13px] font-semibold uppercase tracking-[0.14em] text-[#2F80ED]">{eyebrow}</p>}
        {title && (
          <h2 id={id ? `${id}-title` : undefined}
              className="mt-2 text-[28px] font-bold leading-tight tracking-tight text-[#111827] sm:text-[36px]">{title}</h2>
        )}
        {lead && <p className="mt-3 max-w-3xl text-[17px] leading-relaxed text-[#4B5563]">{lead}</p>}
        <div className={title || lead ? "mt-8" : ""}>{children}</div>
      </div>
    </section>
  );
}
