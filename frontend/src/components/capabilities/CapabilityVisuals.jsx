import React, { useState } from "react";

// What every public picture is, said on the picture itself (#162: a capability
// card shows the real capability, or a clearly labelled illustration of it).
export const VISUAL_TAG = {
  screen: "CAOSCare screen · sample data",
  illustration: "Illustration · how it is used",
  concept: "Design concept · not built or tested",
};

export function VisualImage({ visual, className = "" }) {
  return (
    <img src={visual.src} alt={visual.alt} width={visual.width} height={visual.height} loading="lazy" decoding="async"
         className={`block h-auto max-w-full ${className}`} />
  );
}

// Main image plus selectable thumbnails.
export default function CapabilityVisuals({ visuals }) {
  const [index, setIndex] = useState(0);
  const main = visuals[index] || visuals[0];
  if (!main) return null;
  return (
    <div>
      <figure className="m-0 overflow-hidden rounded-xl border border-[#E5E7EB] bg-white">
        <div className="flex justify-center bg-[#F9FAFB]">
          <VisualImage visual={main} className="max-h-[60vh] w-full object-contain object-top" />
        </div>
        <figcaption className="border-t border-[#E5E7EB] px-4 py-3 text-[14px] text-[#374151]">
          <span className="block text-[12px] font-semibold uppercase tracking-[0.08em] text-[#6B7280]" data-visual-kind={main.kind}>{VISUAL_TAG[main.kind]}</span>
          {main.alt}
        </figcaption>
      </figure>
      {visuals.length > 1 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="More images">
          {visuals.map((v, i) => (
            <li key={v.src}>
              <button type="button" onClick={() => setIndex(i)} aria-pressed={i === index} aria-label={`Show image ${i + 1}: ${v.alt}`}
                      className={`h-16 w-24 overflow-hidden rounded-lg border-2 bg-[#F9FAFB] ${i === index ? "border-[#2F80ED]" : "border-[#E5E7EB]"}`}>
                <VisualImage visual={v} className={`h-full w-full object-cover ${v.kind === "screen" ? "object-left-top" : "object-center"}`} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
