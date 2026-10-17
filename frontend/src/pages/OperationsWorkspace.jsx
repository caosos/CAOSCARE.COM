import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import WorkspaceShell from "../components/workspace/WorkspaceShell";
import WorkspaceGrid from "../components/workspace/WorkspaceGrid";
import RecordsDialog from "../components/workspace/RecordsDialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { WIDGETS, WIDGET_BY_ID } from "../lib/workspaceCatalog";
import { useWorkspaceLayout } from "../lib/useWorkspaceLayout";
import { useBoxValues } from "../lib/useWorkspaceData";
import { useAuth } from "../lib/auth";
import { navFor } from "../lib/workspaceNav";

const SAVE_LABEL = { saving: "Saving…", saved: "Layout saved", error: "Layout not saved — check connection",
                     conflict: "Layout changed in another window — reloaded", loading: "" };

function PeriodBar({ view, setView, run }) {
  const sim = view.world === "simulated";
  const days = run?.executed_through_day || 0;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-3 text-[14px] text-[#4B5563]" data-testid="ws-period">
      <span className="inline-flex rounded-lg border border-[#E5E7EB] bg-white p-0.5">
        {[["live", "Live"], ["simulated", "Simulated"]].map(([w, label]) => (
          <button key={w} type="button" onClick={() => setView({ world: w, date: null, simDay: null })}
                  className={`rounded-md px-3 py-1 font-medium ${view.world === w ? "bg-[#111827] text-white" : "text-[#374151]"}`}>
            {label}
          </button>
        ))}
      </span>
      {sim ? (
        <label className="flex items-center gap-2">Simulated day
          <select value={view.simDay ?? ""} onChange={(e) => setView({ ...view, simDay: e.target.value === "" ? null : Number(e.target.value) })}
                  className="rounded-md border border-[#E5E7EB] bg-white px-2 py-1" aria-label="Simulated day">
            <option value="">Latest{days ? ` (day ${days})` : ""}</option>
            {Array.from({ length: days }, (_, i) => <option key={i} value={i}>Day {i + 1}</option>)}
          </select>
          {run?.clock && <span>· run clock day {run.clock.day}, {run.clock.hh_mm} · {run.state}</span>}
        </label>
      ) : (
        <label className="flex items-center gap-2">Date
          <input type="date" value={view.date || ""} onChange={(e) => setView({ ...view, date: e.target.value || null })}
                 className="rounded-md border border-[#E5E7EB] bg-white px-2 py-1" aria-label="Reporting date" />
          {!view.date && <span>today (facility time)</span>}
        </label>
      )}
    </div>
  );
}

// Live Operations workspace: the approved minimalist design over the
// explainable ops metrics (issue #153). Boxes move, resize, hide and are
// restored; the arrangement is saved per user on the server.
export default function OperationsWorkspace() {
  const { boxes, status, update, reset } = useWorkspaceLayout();
  // The chosen world and period live in the address (?world=&date=&day=), so
  // Back, reload and returning from another page keep what you were looking at.
  const [sp, setSp] = useSearchParams();
  const [view, setView] = useState(() => ({
    world: sp.get("world") === "simulated" ? "simulated" : "live",
    date: sp.get("date") || null,
    simDay: sp.get("day") != null && sp.get("day") !== "" ? Number(sp.get("day")) - 1 : null,
  }));
  useEffect(() => {
    const n = new URLSearchParams();
    if (view.world === "simulated") n.set("world", "simulated");
    if (view.world === "live" && view.date) n.set("date", view.date);
    if (view.world === "simulated" && view.simDay != null) n.set("day", String(view.simDay + 1));
    if (n.toString() !== sp.toString()) setSp(n, { replace: true });
  }, [view]); // eslint-disable-line react-hooks/exhaustive-deps
  const [openWidget, setOpenWidget] = useState(null);
  // Layout is arranged on the page itself (owner 2026-10-15: no "Customize Layout" button): drag to
  // reorder, a box's eye to hide, ⋮ to resize, and "Add a widget" / "Restore hidden boxes" below the grid.
  const [adding, setAdding] = useState(false);
  const visibleIds = useMemo(() => (boxes || []).filter((b) => !b.hidden).map((b) => b.id), [boxes]);
  const { values } = useBoxValues(visibleIds, view);
  const run = Object.values(values).find((v) => v?.run)?.run;
  const placed = new Set((boxes || []).map((b) => b.id));
  // The sidebar's Dashboard entries (alerts, live board, overview...) shown under the boxes too, so they are found
  // without opening the menu (owner 2026-10-17). Same list as the sidebar (workspaceNav.js), never a second copy.
  const { user } = useAuth();
  const shortcuts = (navFor(user?.role).find((sec) => sec.id === "dashboard")?.items || []).filter((i) => i.to !== "/operations");

  const addBox = (id) => update((prev) => (prev.some((b) => b.id === id)
    ? prev.map((b) => (b.id === id ? { ...b, hidden: false } : b))
    : [...prev, { id, x: prev.length, y: 0, w: WIDGET_BY_ID[id].defaultW || 1, h: 1, hidden: false }]));

  return (
    <WorkspaceShell>
      <div className="mt-1 flex flex-col items-start justify-between gap-4 sm:flex-row">
        <div className="min-w-0 flex-1">
          <h1 className="text-[28px] font-bold leading-tight tracking-tight sm:text-[36px]">My CAOSCare Workspace</h1>
          <p className="mt-1 text-[17px] text-[#4B5563] sm:text-[20px]">Drag to arrange · Hide what you don't need</p>
          <PeriodBar view={view} setView={setView} run={run} />
        </div>
        <span className="shrink-0 text-xs text-[#6B7280]" data-testid="ws-save-status">{SAVE_LABEL[status]}</span>
      </div>
      <div className="mt-6">
        {boxes ? (
          <WorkspaceGrid boxes={boxes} values={values} update={update} view={view} onOpen={setOpenWidget}
                         onAdd={() => setAdding(true)}
                         onRestore={() => update((prev) => prev.map((b) => ({ ...b, hidden: false })))} />
        ) : <p className="text-[#6B7280]">Loading your workspace…</p>}
      </div>
      {shortcuts.length > 0 && (
        <nav aria-label="Dashboard" data-testid="ws-dashboard-links" className="mt-8 border-t border-[#EEF0F3] pt-5">
          <h2 className="text-[17px] font-semibold text-[#111827]">Dashboard</h2>
          <ul className="mt-3 flex flex-wrap gap-2">
            {shortcuts.map((i) => (
              <li key={i.to}>
                <Link to={i.to} className="inline-block rounded-lg border border-[#E5E7EB] bg-white px-4 py-2 text-[15px] font-medium text-[#111827] hover:bg-[#F9FAFB]">
                  {i.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}
      <RecordsDialog widget={openWidget} view={view} open={!!openWidget} onOpenChange={(o) => !o && setOpenWidget(null)} />
      <Dialog open={adding} onOpenChange={setAdding}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Add a widget</DialogTitle>
            <DialogDescription>Choose a box to add to your workspace.</DialogDescription>
          </DialogHeader>
          <ul className="max-h-[60vh] space-y-1 overflow-y-auto">
            {WIDGETS.filter((w) => !placed.has(w.id) || (boxes || []).find((b) => b.id === w.id)?.hidden)
              .map((w) => (
                <li key={w.id} className="flex items-center justify-between rounded-lg px-2 py-2 hover:bg-[#F9FAFB]">
                  <span><span className="font-medium">{w.title}</span> <span className="text-[#6B7280]">· {w.subtitle}</span></span>
                  <button type="button" onClick={() => { addBox(w.id); setAdding(false); }} className="rounded-md border px-3 py-1 text-sm">Add</button>
                </li>
              ))}
          </ul>
          <button type="button" onClick={() => { reset(); setAdding(false); }} data-testid="ws-reset"
                  className="mt-2 self-start text-sm text-[#B42318] underline">
            Reset to default layout
          </button>
        </DialogContent>
      </Dialog>
    </WorkspaceShell>
  );
}
