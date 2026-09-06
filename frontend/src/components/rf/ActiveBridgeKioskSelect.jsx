import React, { useEffect, useState } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "../ui/select";
import { api } from "../../lib/api";

/**
 * Real incident, 2026-09-06: RFPairingTab's "add pendant" dialog used to
 * list EVERY kiosk as an equally valid pairing target and told admins to
 * "pick the kiosk nearest the pendant" - the natural, wrong assumption
 * when only ONE kiosk anywhere actually has an SDR bridge attached. Every
 * listen window against any other kiosk timed out no matter what was
 * pressed, for reasons that had nothing to do with the pendant. Split out
 * of RFPairingTab.jsx (already well over the 300-line cap) so fixing this
 * didn't grow that file further.
 */
export default function ActiveBridgeKioskSelect({ kiosks, value, onChange, resetKey }) {
  const [activeBridgeIds, setActiveBridgeIds] = useState(null); // null = loading

  useEffect(() => {
    setActiveBridgeIds(null);
    onChange("");
    (async () => {
      try {
        const { data } = await api.get("/rf/bridges/active");
        setActiveBridgeIds(data.kiosk_ids || []);
        if ((data.kiosk_ids || []).length === 1) onChange(data.kiosk_ids[0]);
      } catch {
        setActiveBridgeIds([]);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey]);

  return (
    <div className="space-y-4">
      {activeBridgeIds === null ? (
        <p className="text-caos-mute text-sm">Checking for an active RF bridge…</p>
      ) : activeBridgeIds.length === 0 ? (
        <p className="text-red-600 text-sm">
          No RF bridge is currently online. The physical SDR bridge daemon needs to be
          running and polling before a new pendant can be captured — check it's started,
          then reopen this dialog.
        </p>
      ) : (
        <p className="text-caos-mute text-sm">
          Pick the RF bridge that's currently online (not the resident's own room kiosk —
          only a kiosk with a physical SDR attached can actually hear the pendant), then
          we'll listen for the button press.
        </p>
      )}
      <Select value={value} onValueChange={onChange} disabled={!activeBridgeIds?.length}>
        <SelectTrigger data-testid="rf-add-kiosk-select"><SelectValue placeholder="Choose an active RF bridge" /></SelectTrigger>
        <SelectContent>
          {kiosks.filter((k) => activeBridgeIds?.includes(k.kiosk_id)).map((k) => (
            <SelectItem key={k.kiosk_id} value={k.kiosk_id}>{k.name} · Rm {k.room}</SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
