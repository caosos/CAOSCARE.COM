import { useCallback } from "react";
import { CirclePlus, Eye } from "lucide-react";
import WorkspaceCard from "./WorkspaceCard";
import SimulationBox from "./SimulationBox";
import AriaBox from "./AriaBox";

const PANELS = { simulation: SimulationBox, aria: AriaBox };
import { WIDGET_BY_ID } from "../../lib/workspaceCatalog";
import { stepBox } from "../../lib/useWorkspaceLayout";
import { useBoxDrag } from "../../lib/useBoxDrag";

// The arranged boxes, "Add a widget" and "Restore hidden boxes".
// Rearranging: drag a box (useBoxDrag), arrow keys on its handle, or
// Move earlier/later in its menu.
export default function WorkspaceGrid({ boxes, values, update, onOpen, onAdd, onRestore, view }) {
  const commit = useCallback((next) => update(() => next), [update]);
  const { drag, shown, onPointerDown } = useBoxDrag(boxes, commit);
  const visible = [...shown].sort((a, b) => a.x - b.x).filter((b) => !b.hidden);
  const hiddenCount = boxes.filter((b) => b.hidden).length;
  const set = (id, patch) => update((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)));
  const dragged = drag && WIDGET_BY_ID[drag.id];

  return (
    <>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4" data-testid="ws-grid">
        {visible.map((box) => {
          const widget = WIDGET_BY_ID[box.id];
          return (
            <WorkspaceCard key={box.id} widget={widget} box={box} state={values[box.id]}
                           onPointerDown={onPointerDown(box.id)} placeholder={drag?.id === box.id}
                           onOpen={() => onOpen(widget)} onHide={() => set(box.id, { hidden: true })}
                           onResize={(w) => set(box.id, { w })}
                           onStep={(d) => update((prev) => stepBox(prev, box.id, d))}>
              {widget.source.kind === "panel" ? (() => { const Panel = PANELS[widget.source.panel]; return <Panel view={view} />; })() : null}
            </WorkspaceCard>
          );
        })}
      </div>
      {dragged && (
        <div className="pointer-events-none fixed z-50 rotate-[1.5deg] rounded-2xl border border-[#2F80ED] bg-white/95 p-6 shadow-2xl"
             style={{ left: drag.x - drag.ox, top: drag.y - drag.oy, width: drag.w, height: drag.h }}
             data-testid="ws-drag-ghost">
          <div className="text-[18px] font-semibold">{dragged.title}</div>
          <div className="mt-1 text-[34px] font-bold">{values[drag.id]?.value ?? ""}</div>
          <div className="mt-2 text-[15px] text-[#4B5563]">{dragged.subtitle}</div>
        </div>
      )}
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center">
        <button type="button" onClick={onAdd} data-testid="ws-add"
                className="flex flex-1 items-center justify-center gap-2 rounded-xl border-2 border-dashed border-[#D1D5DB]
                  bg-transparent py-3.5 text-[15px] text-[#374151] hover:bg-white/70">
          <CirclePlus className="h-5 w-5" /> Add a widget
        </button>
        <button type="button" onClick={onRestore} disabled={!hiddenCount} data-testid="ws-restore"
                className="flex items-center justify-center gap-2 rounded-xl border border-[#E5E7EB] bg-white px-5 py-3.5
                  text-[15px] font-medium text-[#111827] shadow-[0_1px_2px_rgba(16,24,40,0.04)] disabled:opacity-50">
          <Eye className="h-5 w-5 text-[#1D4ED8]" /> Restore hidden boxes{hiddenCount ? ` (${hiddenCount})` : ""}
        </button>
      </div>
    </>
  );
}
