import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Building2, CalendarDays, ChartColumn, ChevronDown, House, Settings, Smartphone, SquareCheck, Users, UsersRound,
} from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../ui/dropdown-menu";
import { useAuth } from "../../lib/auth";

// Sidebar entries open the existing Admin sections (the workspace is the
// new Dashboard; nothing else was rebuilt).
const NAV = [
  ["Dashboard", House, "/operations"], ["Residents", UsersRound, "/admin?tab=residents"],
  ["Staff", Users, "/admin?tab=staff"], ["Tasks", SquareCheck, "/admin?tab=tasks"],
  ["Schedules", CalendarDays, "/admin?tab=schedule"], ["Departments", Building2, "/admin?tab=departments"],
  ["Reports", ChartColumn, "/admin?tab=reports"], ["Devices", Smartphone, "/admin?tab=devices"],
  ["Settings", Settings, "/admin?tab=facilities"],
];

export function CaosCareMark() {
  return (
    <svg viewBox="0 0 64 64" className="h-[54px] w-[54px]" aria-hidden="true">
      <path d="M8 30 L32 9 L56 30" fill="none" stroke="#1E4E8C" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M15 27 V53 H49 V27" fill="none" stroke="#1E4E8C" strokeWidth="5" strokeLinejoin="round" />
      <path d="M32 50 C22 43 20 37 24 33 C27 30 31 31 32 34 C33 31 37 30 40 33 C44 37 42 43 32 50 Z" fill="#E4589A" />
      <path d="M20 44 C25 47 29 49 32 50" fill="none" stroke="#2F80ED" strokeWidth="3" strokeLinecap="round" />
    </svg>
  );
}

function Clock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 30000); return () => clearInterval(t); }, []);
  return (
    <span className="text-[16px] text-[#374151]">
      {now.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric", year: "numeric" })}
      <span className="ml-4">{now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</span>
    </span>
  );
}

const initials = (name) => (name || "?").split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");

export default function WorkspaceShell({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const first = (user?.name || user?.email || "").split(/[\s@]/)[0];
  return (
    <div className="ws-root flex min-h-screen bg-[#FBFCFD] text-[#111827]">
      <aside className="hidden w-[284px] shrink-0 border-r border-[#EEF0F3] bg-[#F7F8FA] px-4 py-5 lg:block">
        <Link to="/operations" className="mb-8 flex items-center gap-2 px-3">
          <CaosCareMark />
          <span>
            <span className="block text-[30px] font-bold leading-none tracking-tight text-[#111827]">CAOSCare</span>
            <span className="mt-1 block text-[12px] text-[#4B5563]">People · Care · Community</span>
          </span>
        </Link>
        <nav className="space-y-1.5">
          {NAV.map(([label, Icon, to]) => {
            const active = to === "/operations";
            return (
              <Link key={label} to={to}
                    className={`flex items-center gap-4 rounded-lg px-4 py-3 text-[17px] ${active
                      ? "bg-[#2F80ED] font-medium text-white shadow-sm" : "text-[#1F2937] hover:bg-white"}`}>
                <Icon className="h-[22px] w-[22px]" strokeWidth={1.8} /> {label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <div className="min-w-0 flex-1 px-5 pb-10 pt-5 sm:px-9">
        <header className="flex items-center justify-end gap-8">
          <span className="hidden sm:inline"><Clock /></span>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="flex items-center gap-3" aria-label="Account menu">
                <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#1E4E8C] text-[15px] font-semibold text-white">
                  {initials(user?.name)}
                </span>
                <span className="text-[17px] font-medium">{first}</span>
                <ChevronDown className="h-5 w-5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => navigate("/admin")}>Admin</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => logout?.()}>Sign out</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </header>
        {children}
      </div>
    </div>
  );
}
