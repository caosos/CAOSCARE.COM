import React from "react";
import DemoRoomVisual from "./DemoRoomVisual";
import DemoStaffChips from "./DemoStaffChips";
import { DemoTypedInput, DemoResetButton } from "./DemoControls";

// Idle-screen block of the public demo kiosk: the live room picture, a way
// to type to Aria (starts the same conversation "I just want to talk"
// would, then sends the text into it) and DEMO RESET.
export default function DemoKioskPanel({ room, onStartTyped }) {
  return (
    <section className="w-full text-left mt-10 space-y-3" data-testid="demo-kiosk-panel">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <h2 className="font-display text-2xl text-caos-forest">Try it: this demo room</h2>
        <DemoResetButton />
      </div>
      <p className="text-caos-mute">
        Say or type a request to Aria, for example “Turn the light on.” The room below shows the device state
        after Aria's command. These are simulated devices; nothing here controls a real room.
      </p>
      <DemoRoomVisual room={room} />
      <DemoStaffChips room={room} />
      <DemoTypedInput onSend={onStartTyped} />
    </section>
  );
}
