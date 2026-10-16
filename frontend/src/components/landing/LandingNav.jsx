import { Link } from "react-router-dom";
import CaosCareMark from "../brand/CaosCareMark";

export const PUBLIC_LINKS = [
  { to: "/for-residents", label: "Residents & families", testid: "nav-residents" },
  { to: "/for-communities", label: "Communities", testid: "nav-communities" },
  { to: "/experience", label: "Explore a room", testid: "nav-experience" },
  { to: "/kiosk/demo", label: "Room screen demo", testid: "nav-kiosk" },
];

// Public top bar. A signed-in visitor gets a way back into the app instead of "Staff sign in".
export default function LandingNav({ authedDest, authedLabel, signedIn }) {
  return (
    <nav className="sticky top-0 z-40 border-b border-[#E5E7EB] bg-white/90 px-4 backdrop-blur sm:px-6 lg:px-8">
      <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 py-3">
        <Link to="/" data-testid="nav-home" className="flex items-center gap-2">
          <CaosCareMark className="h-9 w-9" />
          <span className="text-[22px] font-bold tracking-tight text-[#111827]">CAOSCare</span>
        </Link>
        <div className="hidden items-center gap-1 lg:flex">
          {PUBLIC_LINKS.map((l) => (
            <Link key={l.to} to={l.to} data-testid={l.testid}
                  className="rounded-md px-3 py-2 text-[15px] font-medium text-[#374151] hover:bg-[#F3F4F6] hover:text-[#111827]">
              {l.label}
            </Link>
          ))}
          <Link to={authedDest} data-testid={signedIn ? "nav-continue" : "nav-login"}
                className="ml-2 rounded-lg bg-[#111827] px-4 py-2 text-[15px] font-semibold text-white hover:bg-[#1F2937]">
            {authedLabel}
          </Link>
        </div>
        <details className="relative lg:hidden">
          <summary className="catalog-summary cursor-pointer list-none [&::-webkit-details-marker]:hidden rounded-lg border border-[#D1D5DB] px-4 py-2 text-[15px] font-semibold text-[#111827]">
            Menu
          </summary>
          <div className="absolute right-0 top-full z-50 mt-2 flex w-64 flex-col gap-1 rounded-xl border border-[#E5E7EB] bg-white p-2 shadow-xl">
            {PUBLIC_LINKS.map((l) => (
              <Link key={l.to} to={l.to} className="rounded-md px-3 py-3 text-[16px] text-[#111827] hover:bg-[#F3F4F6]">{l.label}</Link>
            ))}
            <Link to={authedDest} className="rounded-md px-3 py-3 text-[16px] font-semibold text-[#111827] hover:bg-[#F3F4F6]">{authedLabel}</Link>
          </div>
        </details>
      </div>
    </nav>
  );
}
