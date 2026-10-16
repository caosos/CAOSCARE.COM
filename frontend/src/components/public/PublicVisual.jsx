import React from "react";
import { VisualImage, VISUAL_TAG } from "../capabilities/CapabilityVisuals";

// One framed public picture from lib/capabilities/visuals.js, always saying
// what it is (real screen with sample data, or illustration) and,
// optionally, where the data came from.
export default function PublicVisual({ visual, caption, className = "", eager = false, framed = false }) {
  return (
    <figure className={`m-0 min-w-0 ${className}`}>
      <div className={`overflow-hidden rounded-xl border border-[#E5E7EB] bg-white shadow-[0_12px_40px_-12px_rgba(17,24,39,0.22)] ${framed ? "aspect-[4/3]" : ""}`}>
        <img src={visual.src} alt={visual.alt} width={visual.width} height={visual.height}
             loading={eager ? "eager" : "lazy"} decoding="async"
             className={framed ? "block h-full w-full object-cover object-left-top" : "block h-auto w-full"} />
      </div>
      <figcaption className="mt-2 text-[13px] leading-snug text-[#6B7280]">
        <span className="font-semibold text-[#4B5563]" data-visual-kind={visual.kind}>{VISUAL_TAG[visual.kind]}</span>
        {caption ? ` · ${caption}` : ""}
      </figcaption>
    </figure>
  );
}

export { VisualImage };
