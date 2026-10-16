import React from "react";
import PublicVisual from "./PublicVisual";
import StatusPill from "../capabilities/StatusPill";
import { SCREENS } from "../../lib/capabilities/visuals";
import { statusOf } from "../../lib/capabilities/status";

// "Built for low vision", shown rather than claimed (#162): the real room
// screen in its everyday, high-contrast and enlarged views.
const VIEWS = [
  { visual: SCREENS.roomContrast, title: "High contrast", body: "One tap on HC, or ask Aria: the whole screen turns amber on black." },
  { visual: SCREENS.roomEnlarged, title: "Larger everything", body: "The + and − buttons, or \"Aria, make it bigger\": 50% to 200%, and it stays set." },
  { visual: SCREENS.roomScreen, title: "Everyday view", body: "Large type, one big help button and a talk button, with nothing to navigate." },
];

export default function LowVisionProof({ onOpen }) {
  return (
    <div data-testid="low-vision-proof">
      <div className="mb-6 flex flex-wrap items-center gap-3 text-[14px] text-[#4B5563]">
        <StatusPill status={statusOf("low_vision")} />
        <span>Real room screen, public demo room · not yet tested with residents who have low vision.</span>
        {onOpen && <button type="button" onClick={() => onOpen("low_vision")} className="font-semibold text-[#1D4ED8] hover:underline">Details and limits →</button>}
      </div>
      <ul className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {VIEWS.map((v) => (
          <li key={v.title} className="min-w-0">
            <PublicVisual visual={v.visual} />
            <h3 className="mt-3 text-[18px] font-semibold text-[#111827]">{v.title}</h3>
            <p className="mt-1 text-[15px] leading-relaxed text-[#4B5563]">{v.body}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}
