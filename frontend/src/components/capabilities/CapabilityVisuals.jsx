import React, { useState } from "react";

const TAG = { screen: "CAOSCare screen · sample data", photo: "Illustrative photo" };

export function VisualImage({ visual, className = "" }) {
  return (
    <img src={visual.src} alt={visual.alt} width={visual.width} height={visual.height} loading="lazy" decoding="async"
         className={`block h-auto max-w-full ${className}`} />
  );
}

// Main image plus selectable thumbnails. Screens are real CAOSCare software
// with sample data; photos are labelled illustrative.
export default function CapabilityVisuals({ visuals }) {
  const [index, setIndex] = useState(0);
  const main = visuals[index] || visuals[0];
  if (!main) return null;
  return (
    <div>
      <figure className="rounded-2xl border border-caos-line bg-white overflow-hidden">
        <div className="bg-caos-ambient flex justify-center">
          <VisualImage visual={main} className="w-full max-h-[60vh] object-contain object-top" />
        </div>
        <figcaption className="px-4 py-3 text-sm text-caos-ink">
          <span className="block text-[11px] font-bold uppercase tracking-widest text-caos-mute" data-visual-kind={main.kind}>{TAG[main.kind]}</span>
          {main.alt}
        </figcaption>
      </figure>
      {visuals.length > 1 && (
        <ul className="mt-3 flex flex-wrap gap-2" aria-label="More images">
          {visuals.map((v, i) => (
            <li key={v.src}>
              <button type="button" onClick={() => setIndex(i)} aria-pressed={i === index} aria-label={`Show image ${i + 1}: ${v.alt}`}
                      className={`w-24 h-16 rounded-lg overflow-hidden border-2 bg-caos-ambient ${i === index ? "border-caos-forest" : "border-caos-line"}`}>
                <VisualImage visual={v} className="w-full h-full object-cover object-top" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
