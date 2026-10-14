import { useMemo, useState } from "react";
import { Settings } from "lucide-react";
import WorkspaceShell from "../components/workspace/WorkspaceShell";
import WorkspaceGrid from "../components/workspace/WorkspaceGrid";
import RecordsDialog from "../components/workspace/RecordsDialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "../components/ui/dialog";
import { WIDGETS, WIDGET_BY_ID } from "../lib/workspaceCatalog";
import { useWorkspaceLayout } from "../lib/useWorkspaceLayout";
import { useBoxValues } from "../lib/useWorkspaceData";

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
  const [view, setView] = useState({ world: "live", date: null, simDay: null });
  const [openWidget, setOpenWidget] = useState(null);
  const [panel, setPanel] = useState(null);       // "customize" | "add" | null
  const visibleIds = useMemo(() => (boxes || []).filter((b) => !b.hidden).map((b) => b.id), [boxes]);
  const { values } = useBoxValues(visibleIds, view);
  const run = Object.values(values).find((v) => v?.run)?.run;
  const placed = new Set((boxes || []).map((b) => b.id));

  const addBox = (id) => update((prev) => (prev.some((b) => b.id === id)
    ? prev.map((b) => (b.id === id ? { ...b, hidden: false } : b))
    : [...prev, { id, x: prev.length, y: 0, w: WIDGET_BY_ID[id].defaultW || 1, h: 1, hidden: false }]));

  return (
    <WorkspaceShell>
      <div className="mt-1 flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <h1 className="text-[36px] font-bold leading-tight tracking-tight">My CAOSCare Workspace</h1>
          <p className="mt-1 text-[20px] text-[#4B5563]">Drag to arrange · Hide what you don't need</p>
          <PeriodBar view={view} setView={setView} run={run} />
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button type="button" onClick={() => setPanel("customize")} data-testid="ws-customize"
                  className="flex items-center gap-2.5 rounded-lg border border-[#E5E7EB] bg-white px-5 py-3 text-[17px]
                    font-medium shadow-[0_1px_2px_rgba(16,24,40,0.05)] hover:bg-[#F9FAFB]">
            <Settings className="h-5 w-5" /> Customize Layout
          </button>
          <span className="text-xs text-[#6B7280]" data-testid="ws-save-status">{SAVE_LABEL[status]}</span>
        </div>
      </div>
      <div className="mt-6">
        {boxes ? (
          <WorkspaceGrid boxes={boxes} values={values} update={update} view={view} onOpen={setOpenWidget}
                         onAdd={() => setPanel("add")}
                         onRestore={() => update((prev) => prev.map((b) => ({ ...b, hidden: false })))} />
        ) : <p className="text-[#6B7280]">Loading your workspace…</p>}
      </div>
      <RecordsDialog widget={openWidget} view={view} open={!!openWidget} onOpenChange={(o) => !o && setOpenWidget(null)} />
      <Dialog open={!!panel} onOpenChange={(o) => !o && setPanel(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>{panel === "add" ? "Add a widget" : "Customize layout"}</DialogTitle>
            <DialogDescription>
              {panel === "add" ? "Choose a box to add to your workspace." : "Show or hide boxes. Drag boxes on the page to reorder; use a box's ⋮ menu to resize."}
            </DialogDescription>
          </DialogHeader>
          <ul className="max-h-[60vh] space-y-1 overflow-y-auto">
            {WIDGETS.filter((w) => panel !== "add" || !placed.has(w.id) || (boxes || []).find((b) => b.id === w.id)?.hidden)
              .map((w) => {
                const box = (boxes || []).find((b) => b.id === w.id);
                const shown = box && !box.hidden;
                return (
                  <li key={w.id} className="flex items-center justify-between rounded-lg px-2 py-2 hover:bg-[#F9FAFB]">
                    <span><span className="font-medium">{w.title}</span> <span className="text-[#6B7280]">· {w.subtitle}</span></span>
                    {panel === "add" ? (
                      <button type="button" onClick={() => { addBox(w.id); setPanel(null); }} className="rounded-md border px-3 py-1 text-sm">Add</button>
                    ) : (
                      <input type="checkbox" checked={!!shown} aria-label={`Show ${w.title} ${w.subtitle}`}
                             onChange={() => (shown ? update((prev) => prev.map((b) => (b.id === w.id ? { ...b, hidden: true } : b))) : addBox(w.id))} />
                    )}
                  </li>
                );
              })}
          </ul>
          {panel === "customize" && (
            <button type="button" onClick={() => { reset(); setPanel(null); }} className="mt-2 text-sm text-[#B42318] underline">
              Reset to default layout
            </button>
          )}
        </DialogContent>
      </Dialog>
    </WorkspaceShell>
  );
}
