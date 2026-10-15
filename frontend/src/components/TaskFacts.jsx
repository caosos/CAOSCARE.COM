import React from "react";
import { nextStepText, simulationLines } from "../lib/taskFacts";

// The facts one task must reveal (#168) beyond its summary line: why it
// exists (origin), the simulated clock for a simulator ticket (next to the
// real receipt time), and (unless the caller shows it) the next permitted step. `detail` is the
// GET /tasks/{id}/detail response; until it loads only the next step shows.
export default function TaskFacts({ t, detail, clock, testid, showNext = true }) {
  const sim = detail?.simulation;
  const lines = simulationLines(sim, t, clock);
  const origin = sim?.origin?.label || detail?.origin?.label;
  return (
    <div className="space-y-0.5 text-[13px]" data-testid={testid}>
      {origin && !sim && <div><span className="text-caos-mute">Why: </span>{origin}</div>}
      {lines.length > 0 && (
        <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5" data-testid={testid && `${testid}-sim`}>
          {lines.map(([k, v]) => (
            <React.Fragment key={k}><dt className="text-caos-mute">{k}</dt><dd className="break-words">{v}</dd></React.Fragment>
          ))}
        </dl>
      )}
      {showNext && <div><span className="text-caos-mute">Next step: </span>{nextStepText(t)}</div>}
    </div>
  );
}
