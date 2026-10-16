import { Link } from "react-router-dom";
import { ArrowRight, Building2, DoorOpen, HeartHandshake, MonitorSmartphone } from "lucide-react";

const PATHS = [
  { to: "/for-residents", icon: HeartHandshake, title: "Residents & families",
    body: "What living with Aria is like: talking, asking for help, today's menu and activities.", testid: "path-residents" },
  { to: "/for-communities", icon: Building2, title: "Communities",
    body: "Every department's workspace, the staff dashboard and how requests are tracked.", testid: "path-communities" },
  { to: "/experience", icon: DoorOpen, title: "Explore a room",
    body: "Pick an apartment and see which room features are in pilot today.", testid: "path-experience" },
  { to: "/kiosk/demo", icon: MonitorSmartphone, title: "Room screen demo",
    body: "The real room screen in a demo room: a sample resident and simulated light, TV and thermostat.", testid: "path-kiosk" },
];

export default function LandingPaths({ authedDest, authedLabel }) {
  return (
    <section className="border-t border-[#E5E7EB] bg-[#F9FAFB] px-4 py-16 sm:px-6 lg:px-8" aria-labelledby="paths-title">
      <div className="mx-auto max-w-7xl">
        <h2 id="paths-title" className="text-[28px] font-bold tracking-tight text-[#111827] sm:text-[36px]">Where to next</h2>
        <ul className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {PATHS.map(({ to, icon: Icon, title, body, testid }) => (
            <li key={to}>
              <Link to={to} data-testid={testid}
                    className="group flex h-full flex-col rounded-xl border border-[#E5E7EB] bg-white p-5 hover:border-[#111827] hover:shadow-md">
                <Icon className="h-6 w-6 text-[#2F80ED]" aria-hidden="true" />
                <span className="mt-3 flex items-center gap-1 text-[18px] font-semibold text-[#111827]">
                  {title} <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" aria-hidden="true" />
                </span>
                <span className="mt-1 text-[15px] leading-relaxed text-[#4B5563]">{body}</span>
              </Link>
            </li>
          ))}
        </ul>
        <p className="mt-6 text-[15px] text-[#4B5563]">
          Community staff: <Link to={authedDest} className="font-semibold text-[#111827] underline">{authedLabel}</Link>
        </p>
      </div>
    </section>
  );
}
