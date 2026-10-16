import { ArrowRight, Eye, EllipsisVertical, GripVertical } from "lucide-react";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from "../ui/dropdown-menu";
import { TINTS } from "../../lib/workspaceCatalog";

const SIZES = [[1, "Normal"], [2, "Wide"], [4, "Full width"]];

function Value({ state }) {
  if (state?.unverified) {
    return <div className="mt-1 text-[34px] font-bold leading-none text-[#9CA3AF]" title={state.unverified}>—</div>;
  }
  if (state?.value == null) {
    return <div className="mt-1 h-[34px] w-16 animate-pulse rounded bg-white/70" aria-label="Loading" />;
  }
  return <div className="mt-1 text-[34px] font-bold leading-none tracking-tight text-[#111827]">{state.value}</div>;
}

// One box. Only the handle drags it (or use the menu / arrow keys on the handle); the eye hides it;
// the menu also sets its width. Clicking the box opens its records.
export default function WorkspaceCard({ widget, box, state, children, onOpen, onHide, onResize, onStep,
                                        onPointerDown, placeholder }) {
  const tint = TINTS[widget.tint] || TINTS.slate;
  const Icon = widget.icon;
  const subtitle = state?.unverified ? "Not recorded yet" : widget.subtitle;
  return (
    <article
      data-box-id={widget.id}
      onPointerDown={onPointerDown}
      data-testid={`ws-box-${widget.id}`}
      className={`group relative flex flex-col rounded-2xl border p-6 pt-5 shadow-[0_1px_2px_rgba(16,24,40,0.04)]
        transition-shadow ${tint.card}
        ${placeholder ? "border-2 border-dashed !border-[#2F80ED] opacity-40" : ""}`}
      style={{ gridColumn: `span ${box.w} / span ${box.w}` }}
    >
      <div className="flex items-start justify-between">
        <button type="button" data-drag-handle data-testid={`ws-grip-${widget.id}`}
                aria-label={`Move ${widget.title}. Use arrow keys to move earlier or later.`} title="Drag to move"
                onKeyDown={(e) => {
                  const d = { ArrowLeft: -1, ArrowUp: -1, ArrowRight: 1, ArrowDown: 1 }[e.key];
                  if (d) { e.preventDefault(); onStep(d); }
                }}
                className="-ml-3 -mt-1 cursor-grab touch-none rounded p-1 text-[#B8BEC8] hover:text-[#6B7280]
                  focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2F80ED] active:cursor-grabbing">
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="-mr-2 flex items-center gap-1">
          <button type="button" onClick={onHide} aria-label={`Hide ${widget.title}`}
                  className="rounded-md p-1.5 text-[#1F2937] hover:bg-black/5">
            <Eye className="h-[18px] w-[18px]" />
          </button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" aria-label={`${widget.title} options`}
                      className="rounded-md p-1.5 text-[#1F2937] hover:bg-black/5">
                <EllipsisVertical className="h-[18px] w-[18px]" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Size</DropdownMenuLabel>
              {SIZES.map(([w, label]) => (
                <DropdownMenuItem key={w} onSelect={() => onResize(w)}>
                  {label}{box.w === w ? " ✓" : ""}
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => onStep(-1)}>Move earlier</DropdownMenuItem>
              <DropdownMenuItem onSelect={() => onStep(1)}>Move later</DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={onHide}>Hide box</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
      <div className={`-mt-1 flex h-[52px] w-[52px] items-center justify-center rounded-xl ${tint.icon}`}>
        <Icon className="h-7 w-7" strokeWidth={2} />
      </div>
      {children ? (
        <div className="mt-3">
          <h3 className={`text-[18px] font-semibold ${tint.title}`}>{widget.title}</h3>
          {children}
        </div>
      ) : (
        <>
          <h3 className={`mt-3 text-[18px] font-semibold leading-tight ${tint.title}`}>{widget.title}</h3>
          <Value state={state} />
          <p className="mt-2 text-[15px] text-[#4B5563]">{subtitle}</p>
          {state?.error && <p className="mt-1 text-xs text-[#B42318]">Last refresh failed — showing the last known value.</p>}
          <button type="button" onClick={onOpen}
                  className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg border border-[#E5E7EB]
                    bg-white py-2.5 text-[15px] font-medium text-[#111827] shadow-[0_1px_1px_rgba(16,24,40,0.03)]
                    hover:bg-[#F9FAFB]">
            View details <ArrowRight className="h-4 w-4" />
          </button>
        </>
      )}
    </article>
  );
}
