import React from "react";
import StatusPill from "../capabilities/StatusPill";
import { CAPABILITIES_BY_ID } from "../../lib/capabilities";

// A compact, status-honest list of capabilities by id (status from the one
// registry). Each tile opens the capability's panel with its limits.
export default function CapabilityTiles({ ids, onOpen, testid }) {
  return (
    <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid={testid}>
      {ids.map((id) => {
        const c = CAPABILITIES_BY_ID[id];
        return (
          <li key={id} className="min-w-0">
            <button type="button" onClick={() => onOpen(id)} aria-haspopup="dialog" data-testid={`tile-${id}`}
                    className="flex h-full w-full flex-col rounded-xl border border-[#E5E7EB] bg-white p-4 text-left hover:border-[#111827] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#2F80ED]">
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-[17px] font-semibold text-[#111827]">{c.name}</span>
                <StatusPill status={c.status} />
              </span>
              <span className="mt-1 text-[15px] leading-relaxed text-[#4B5563]">{c.summary}</span>
            </button>
          </li>
        );
      })}
    </ul>
  );
}
