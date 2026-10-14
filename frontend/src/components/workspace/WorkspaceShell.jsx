import { createContext, useContext, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import * as Icons from "lucide-react";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "../ui/dropdown-menu";
import { useAuth } from "../../lib/auth";
import { navFor } from "../../lib/workspaceNav";
import AdminAria from "../admin/AdminAria";
import WorkAsControl from "../WorkAsControl";

// Ask Aria is the existing Admin Aria assistant (/admin-assistant/chat):
// the sidebar item and the optional workspace box both open this one panel.
const AskAria = createContext({ openAria: () => {} });
export const useAskAria = () => useContext(AskAria);

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

function SidebarSection({ section, active, open, onToggle, onAria }) {
  const Icon = Icons[section.icon] || Icons.Circle;
  const base = "flex w-full items-center gap-4 rounded-lg px-4 py-3 text-left text-[17px]";
  const look = active ? "bg-[#2F80ED] font-medium text-white shadow-sm" : "text-[#1F2937] hover:bg-white";
  const click = () => (section.action === "ask-aria" ? onAria() : onToggle());
  return (
    <div>
      {section.to && !section.action ? (
        <Link to={section.to} onClick={onToggle} className={`${base} ${look}`} data-testid={`nav-${section.id}`}>
          <Icon className="h-[22px] w-[22px]" strokeWidth={1.8} /> {section.label}
        </Link>
      ) : (
        <button type="button" onClick={click} aria-expanded={section.action ? undefined : open}
                className={`${base} ${look}`} data-testid={`nav-${section.id}`}>
          <Icon className="h-[22px] w-[22px]" strokeWidth={1.8} /> {section.label}
        </button>
      )}
      {open && section.items.length > 0 && (
        <ul className="mb-2 ml-[52px] mt-1 space-y-0.5 border-l border-[#E5E7EB] pl-3" data-testid={`nav-${section.id}-items`}>
          {section.items.map((item) => (
            <li key={item.to + item.label}>
              <Link to={item.to} className="block rounded-md px-2 py-1.5 text-[14px] text-[#374151] hover:bg-white hover:text-[#111827]"
                    data-testid={`nav-item-${item.tab || item.to}`}>
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default function WorkspaceShell({ children }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [expanded, setExpanded] = useState(null);
  const [ariaOpen, setAriaOpen] = useState(false);
  const [prompt, setPrompt] = useState(null);
  const sections = navFor(user?.role);
  const first = (user?.name || user?.email || "").split(/[\s@]/)[0];
  const openAria = (text) => {
    setAriaOpen(true);
    if (text) setPrompt({ text, id: Date.now() });
  };
  return (
    <AskAria.Provider value={{ openAria }}>
      <div className="ws-root flex min-h-screen bg-[#FBFCFD] text-[#111827]">
        <aside className="hidden w-[284px] shrink-0 border-r border-[#EEF0F3] bg-[#F7F8FA] px-4 py-5 lg:block">
          <Link to="/operations" className="mb-8 flex items-center gap-2 px-3">
            <CaosCareMark />
            <span>
              <span className="block text-[30px] font-bold leading-none tracking-tight text-[#111827]">CAOSCare</span>
              <span className="mt-1 block text-[12px] text-[#4B5563]">People · Care · Community</span>
            </span>
          </Link>
          <nav className="space-y-1.5" aria-label="Main">
            {sections.map((s) => (
              <SidebarSection key={s.id} section={s} active={s.id === "dashboard" && location.pathname === "/operations"}
                              open={expanded === s.id || (s.action === "ask-aria" && ariaOpen)}
                              onToggle={() => setExpanded((e) => (e === s.id ? null : s.id))}
                              onAria={() => openAria()} />
            ))}
          </nav>
        </aside>
        <div className="min-w-0 flex-1 px-5 pb-10 pt-5 sm:px-9">
          <header className="flex items-center justify-end gap-6">
            <WorkAsControl onEntered={() => navigate("/workspace")} />
            <span className="hidden sm:inline"><Clock /></span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button type="button" className="flex items-center gap-3" aria-label="Account menu">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[#1E4E8C] text-[15px] font-semibold text-white">
                    {initials(user?.name)}
                  </span>
                  <span className="text-[17px] font-medium">{first}</span>
                  <Icons.ChevronDown className="h-5 w-5" />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                {/* Small screens have no sidebar: every section stays reachable here. */}
                {sections.map((s) => (s.action
                  ? <DropdownMenuItem key={s.id} onSelect={() => openAria()}>{s.label}</DropdownMenuItem>
                  : <DropdownMenuItem key={s.id} onSelect={() => navigate(s.to || s.items[0].to)} className="lg:hidden">{s.label}</DropdownMenuItem>))}
                <DropdownMenuItem onSelect={() => navigate("/admin")}>Classic command centre</DropdownMenuItem>
                <DropdownMenuItem onSelect={async () => { await logout?.(); navigate("/login"); }}>Sign out</DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </header>
          {children}
        </div>
      </div>
      <AdminAria currentSection="operations" onNavigate={(t) => navigate(`/admin?tab=${t}`)}
                 open={ariaOpen} onOpenChange={setAriaOpen} hideLauncher prompt={prompt} />
    </AskAria.Provider>
  );
}
