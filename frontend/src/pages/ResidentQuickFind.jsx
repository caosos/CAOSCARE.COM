import React, { useMemo, useRef, useState } from "react";
import { Input } from "../components/ui/input";
import { Search } from "lucide-react";
import { matchResidents } from "../lib/residentSearch";

// Fast resident / room finder for a 100-300 resident community. Type a room
// number, a first or last name, a preferred name, or "First Last" - pick
// with the mouse or the keyboard (Up/Down/Enter, Esc to clear). onPick gets
// the full resident object; the parent decides what detail to open. Reuses
// the residents list the page already loaded - no new endpoint.
export default function ResidentQuickFind({ residents, onPick }) {
  const [q, setQ] = useState("");
  const [hi, setHi] = useState(0);
  const [focused, setFocused] = useState(false);
  const inputRef = useRef(null);

  const results = useMemo(() => matchResidents(residents, q, 8), [residents, q]);
  const open = focused && q.trim().length > 0;

  const choose = (r) => {
    if (!r) return;
    onPick?.(r);
    setQ("");
    setHi(0);
    inputRef.current?.blur();
  };

  const onKeyDown = (e) => {
    if (!open) return;
    if (e.key === "ArrowDown") { e.preventDefault(); setHi((i) => Math.min(i + 1, results.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setHi((i) => Math.max(i - 1, 0)); }
    else if (e.key === "Enter") { e.preventDefault(); choose(results[hi]); }
    else if (e.key === "Escape") { setQ(""); setHi(0); inputRef.current?.blur(); }
  };

  return (
    <div className="relative w-full max-w-md" data-testid="resident-quick-find">
      <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-caos-mute pointer-events-none" />
      <Input
        ref={inputRef}
        value={q}
        onChange={(e) => { setQ(e.target.value); setHi(0); }}
        onKeyDown={onKeyDown}
        onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 150)}
        placeholder="Find a resident or room — 214, Helen, Torres…"
        className="pl-9"
        data-testid="resident-quick-find-input"
        aria-autocomplete="list"
        aria-expanded={open}
      />
      {open && (
        <div
          className="absolute z-40 mt-1 w-full rounded-xl border border-caos-line bg-white shadow-lg overflow-hidden"
          data-testid="resident-quick-find-results"
          role="listbox"
        >
          {results.length === 0 && (
            <div className="px-3 py-3 text-sm text-caos-mute italic">No resident or room matches “{q}”.</div>
          )}
          {results.map((r, i) => (
            <button
              key={r.resident_id}
              type="button"
              role="option"
              aria-selected={i === hi}
              onMouseDown={(e) => { e.preventDefault(); choose(r); }}
              onMouseEnter={() => setHi(i)}
              data-testid={`resident-quick-find-opt-${r.resident_id}`}
              className={`w-full text-left px-3 py-2 flex items-center justify-between gap-3 ${i === hi ? "bg-caos-forest/10" : "hover:bg-caos-bone/60"}`}
            >
              <span className="min-w-0">
                <span className="font-medium text-caos-forest">{r.name}</span>
                {r.preferred_name && <span className="text-caos-mute text-xs ml-2">“{r.preferred_name}”</span>}
              </span>
              <span className="text-xs text-caos-mute shrink-0">Room {r.room}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
