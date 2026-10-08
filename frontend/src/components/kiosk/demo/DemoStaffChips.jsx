import React, { useEffect, useState } from "react";
import { BellRing } from "lucide-react";
import { API } from "../../../lib/api";
import { DEMO_POLL_MS, staffNotifiedChips } from "../../../lib/demoRoom";

// Shows, under the demo room picture, that a staff request Aria filed is
// really open. Reads the resident's real requests; renders nothing (no
// placeholder, no fake chip) when there are none.
export default function DemoStaffChips({ room }) {
  const [items, setItems] = useState([]);
  useEffect(() => {
    if (!room) return undefined;
    let stop = false;
    const load = async () => {
      try {
        const r = await fetch(`${API}/tasks/resident-request/mine?room=${encodeURIComponent(room)}`);
        if (r.ok && !stop) setItems(await r.json());
      } catch { /* keep the last known list */ }
    };
    load();
    const t = setInterval(load, DEMO_POLL_MS * 3);
    return () => { stop = true; clearInterval(t); };
  }, [room]);
  const chips = staffNotifiedChips(items);
  if (!chips.length) return null;
  return (
    <div className="flex flex-wrap gap-2" data-testid="demo-staff-chips">
      {chips.map((c) => (
        <span key={c.id} data-testid={`demo-staff-chip-${c.id}`}
          className="inline-flex items-center gap-2 rounded-full bg-caos-forest text-white text-sm px-3 py-1">
          <BellRing className="w-4 h-4" aria-hidden="true" /> {c.label}
        </span>
      ))}
    </div>
  );
}
