import React from "react";
import { STATUS } from "../../lib/publicOnboarding";

export function Status({ value }) {
  return <span className="text-xs font-bold uppercase tracking-widest text-caos-terracotta">{STATUS[value]}</span>;
}

export default function PublicCatalog({ items, label }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4" aria-label={label}>
      {items.map((item) => (
        <details key={item.name || item.id} className="group rounded-2xl border border-caos-line bg-white p-5">
          <summary className="cursor-pointer list-none flex items-start justify-between gap-4 min-h-[48px]">
            <span>
              <span className="block font-display text-xl text-caos-forest">{item.name}</span>
              <Status value={item.status} />
            </span>
            <span aria-hidden="true" className="text-2xl text-caos-forest group-open:rotate-45 transition-transform">+</span>
          </summary>
          <div className="border-t border-caos-line pt-4 mt-3 text-caos-ink leading-relaxed">
            <p>{item.detail || item.description}</p>
            {item.staff && <p className="mt-3"><b>Staff view:</b> {item.staff}</p>}
          </div>
        </details>
      ))}
    </div>
  );
}
