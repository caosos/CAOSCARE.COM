import React, { useEffect, useState } from "react";
import { api } from "../lib/api";
import { Card } from "./ui/card";
import { CheckCircle2, Circle } from "lucide-react";

const LABEL = {
  resend_key: "Email provider key", sending_domain: "Sending domain verified", webhook_secret: "Inbound/delivery webhook secret",
  department_inboxes: "Every department has an inbox address", inbound_menu_sender: "Kitchen sender approved (menu)",
  inbound_activities_sender: "Activities sender approved (activities)",
};

export default function EmailReadiness() {
  const [d, setD] = useState(null);
  useEffect(() => { api.get("/notifications/readiness").then((r) => setD(r.data)).catch(() => setD(null)); }, []);
  if (!d) return null;
  return (
    <Card className="border-caos-line p-5" data-testid="email-readiness">
      <h3 className="font-display text-lg font-medium text-caos-forest mb-1">Real email setup</h3>
      <p className="text-sm text-caos-mute mb-3">{d.ready ? "Everything needed is set. Send a test to prove delivery." : "Not ready yet. Nothing here sends mail; it lists what is still missing."}</p>
      <ul className="space-y-2">
        {d.checks.map((c) => (
          <li key={c.id} className="flex gap-2 text-sm" data-testid={`ready-${c.id}`}>
            {c.ok ? <CheckCircle2 className="w-4 h-4 text-green-700 mt-0.5 shrink-0" /> : <Circle className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />}
            <span><span className="font-medium">{LABEL[c.id] || c.id}</span>{!c.ok && <span className="text-caos-mute"> — {c.fix}</span>}</span>
          </li>
        ))}
      </ul>
      {d.departments_missing_inbox.length > 0 && (
        <p className="text-xs text-caos-mute mt-3">Missing an inbox: {d.departments_missing_inbox.map((x) => x.label).join(", ")}</p>
      )}
    </Card>
  );
}
