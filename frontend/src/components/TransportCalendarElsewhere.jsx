import React from "react";
import { Button } from "./ui/button";

// What the shown day/week does not contain: the next dates with open rides
// (one tap to jump there) and open requests dated before today, which never
// appear on a future day. From the calendar response's `elsewhere` field.
export default function TransportCalendarElsewhere({ elsewhere, onJump, fmtDay }) {
  if (!elsewhere) return null;
  const { next_dates: next = [], earlier_open_unbooked: earlier = 0 } = elsewhere;
  if (!next.length && !earlier) return null;
  return (
    <div className="mt-4 rounded-lg border border-caos-line p-3 text-sm space-y-2" data-testid="calendar-elsewhere">
      {next.length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-caos-mute">Next rides:</span>
          {next.map((n) => (
            <Button key={n.date} size="sm" variant="outline" className="border-2 rounded-full" onClick={() => onJump(n.date)} data-testid={`calendar-jump-${n.date}`}>
              {fmtDay(n.date)} ({n.count})
            </Button>
          ))}
        </div>
      )}
      {earlier > 0 && (
        <div className="text-caos-terracotta" data-testid="calendar-earlier-open">
          {earlier} open ride request{earlier === 1 ? " is" : "s are"} dated before today and will not show on any day here. They are listed under Transportation → Unresolved.
        </div>
      )}
    </div>
  );
}
