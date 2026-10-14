import { useState } from "react";
import { CirclePlus, Eye } from "lucide-react";
import WorkspaceCard from "./WorkspaceCard";
import SimulationBox from "./SimulationBox";
import { WIDGET_BY_ID } from "../../lib/workspaceCatalog";
import { moveBox, stepBox } from "../../lib/useWorkspaceLayout";

// The arranged boxes, "Add a widget" and "Restore hidden boxes".
// Rearranging: drag a box by its handle, or Move earlier/later in its menu
// (keyboard).
export default function WorkspaceGrid({ boxes, values, update, onOpen, onAdd, onRestore, view }) {
  const [dragId, setDragId] = useState(null);
  const [overId, setOverId] = useState(null);
  const visible = [...boxes].sort((a, b) => a.x - b.x).filter((b) => !b.hidden);
  const hiddenCount = boxes.filter((b) => b.hidden).length;
  const set = (id, patch) => update((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)));

  // Drag from a box's handle: pointer events (mouse, pen and touch alike);
  // the box under the pointer is highlighted and receives the drop.
  const startDrag = (id) => (e) => {
    e.preventDefault();
    setDragId(id);
    let target = null;
    const move = (ev) => {
      const el = document.elementFromPoint(ev.clientX, ev.clientY)?.closest("[data-box-id]");
      target = el && el.dataset.boxId !== id ? el.dataset.boxId : null;
      setOverId(target);
    };
    const end = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      if (target) update((prev) => moveBox(prev, id, target));
      setDragId(null);
      setOverId(null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
  };

  return (
    <>
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 xl:grid-cols-4" data-testid="ws-grid">
        {visible.map((box) => {
          const widget = WIDGET_BY_ID[box.id];
          return (
            <WorkspaceCard key={box.id} widget={widget} box={box} state={values[box.id]}
                           onGripDown={startDrag(box.id)} dragging={dragId === box.id} dropActive={overId === box.id}
                           onOpen={() => onOpen(widget)} onHide={() => set(box.id, { hidden: true })}
                           onResize={(w) => set(box.id, { w })}
                           onStep={(d) => update((prev) => stepBox(prev, box.id, d))}>
              {widget.source.kind === "panel" ? <SimulationBox view={view} /> : null}
            </WorkspaceCard>
          );
        })}
      </div>
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
