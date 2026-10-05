import React from "react";
import { Button } from "../ui/button";
import { Card } from "../ui/card";
import { Play, Pause, StepForward, Square, RotateCw } from "lucide-react";
import { allowedControls, describeStep, simClock, waitingText } from "../../lib/simulator";

const STATE_CLASS = {
  RUNNING: "bg-caos-moss/20 text-caos-forest border border-caos-moss",
  PAUSED: "bg-caos-amber/20 text-[#8B5A20] border border-caos-amber",
  STOPPED: "bg-caos-mute/10 text-caos-mute border border-caos-line",
};

// Run state, simulated time, next scheduled action and the five controls.
// Buttons follow what the scheduler accepts; the server stays the authority.
export default function SimControls({ state, busy, onControl }) {
  const s = state?.state || "STOPPED";
  const can = allowedControls(s);
  const btn = (key, label, Icon, extra = {}) => (
    <Button key={key} size="sm" variant={key === "start" ? "default" : "outline"} disabled={busy || !can[key]}
            onClick={() => onControl(key)} data-testid={`sim-${key}`} {...extra}>
      <Icon className="w-4 h-4 mr-1" />{label}
    </Button>
  );
  return (
    <Card className="border-caos-line p-4" data-testid="sim-controls">
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <span className={`rounded-full px-3 py-1 text-xs font-bold tracking-widest ${STATE_CLASS[s]}`} data-testid="sim-state">{s}</span>
        <span className="text-sm text-caos-mute">Simulated time <b className="text-caos-ink" data-testid="sim-clock">{simClock(state?.sim_minute)}</b></span>
        {state?.run_id && (
          <span className="text-xs text-caos-mute">
            Step {state.cursor} of {state.steps_total} · run <span className="font-mono">{state.run_id}</span>
            {s === "RUNNING" && state.loop_alive === false && <b className="text-caos-terracotta"> · scheduler loop not running</b>}
          </span>
        )}
      </div>
      <div className="flex flex-wrap gap-2 mb-3">
        {btn("start", "Start", Play, { className: "bg-caos-forest" })}
        {btn("pause", "Pause", Pause)}
        {btn("step", "Step", StepForward)}
        {btn("resume", "Resume", RotateCw)}
        {btn("stop", "Stop", Square)}
      </div>
      <div className="text-sm" data-testid="sim-next-step">
        <span className="text-caos-mute">Next scheduled action: </span>
        {state?.next_step ? describeStep(state.next_step) : <span className="italic text-caos-mute">none ({s === "STOPPED" ? "stopped" : "scenario finished"})</span>}
        {waitingText(state?.waiting_on) && (
          <span className="ml-2 font-semibold text-caos-forest" data-testid="sim-waiting">— {waitingText(state.waiting_on)}</span>
        )}
      </div>
    </Card>
  );
}
