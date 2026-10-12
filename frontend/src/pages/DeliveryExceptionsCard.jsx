import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";

/*
 * Alert messages that did not go out (GET /ops/delivery-exceptions): escalation
 * texts/calls and family alert updates that were not sent or failed in the last
 * 3 days. Read-only and resident-safe: no message text, recipients masked. Open
 * the alert to follow up in person or by phone; nothing is re-sent from here.
 */
function ago(iso) {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  return s < 3600 ? `${Math.floor(s / 60)}m ago` : s < 86400 ? `${Math.floor(s / 3600)}h ago` : `${Math.floor(s / 86400)}d ago`;
}

export default function DeliveryExceptionsCard() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const load = useCallback(() => {
    api.get("/ops/delivery-exceptions").then(({ data: d }) => { setData(d); setError(false); }).catch(() => setError(true));
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  return (
    <div className="space-y-3" data-testid="delivery-exceptions">
      <div>
        <h2 className="font-display text-2xl font-medium text-caos-forest">Alert messages that did not go out</h2>
        <p className="text-caos-mute text-sm mt-1">
          Texts, calls and family updates about an alert that were not sent or failed in the last 3 days. Nothing is
          re-sent from here: open the alert and follow up in person or by phone.
        </p>
      </div>
      {error && <Card className="p-4 text-sm text-red-700" data-testid="dx-error">Could not load undelivered alert messages.</Card>}
      {data && data.items.length === 0 && <Card className="p-6 text-center text-caos-mute italic" data-testid="dx-empty">Every alert message in the last 3 days went out.</Card>}
      {data?.items.map((d) => (
        <Card key={d.notification_id} className="p-4 border-2 border-caos-line" data-testid={`dx-row-${d.notification_id}`}>
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <div className="flex flex-wrap gap-1.5 items-center">
                <Badge className={d.state === "failed" ? "bg-[#FDECE9] text-[#98392F] border border-[#B6463A]" : "bg-[#FDF3E3] text-[#8B5A20] border border-[#D28D38]"}>{d.label}</Badge>
                <span className="text-xs text-caos-mute uppercase">{d.channel === "sms" ? "text" : d.channel}</span>
              </div>
              <div className="font-semibold text-caos-forest mt-1 break-words">{d.recipient}</div>
              <div className="text-xs text-caos-mute mt-0.5">
                {[d.resident_name, d.room ? `Room ${d.room}` : null, d.alert_severity ? `${d.alert_severity} alert, ${d.alert_status}` : null, ago(d.created_at)].filter(Boolean).join(" · ")}
              </div>
            </div>
            <Link to={`/staff?alert=${d.alert_id}`} className="text-sm font-semibold text-caos-forest underline shrink-0" data-testid={`dx-open-${d.notification_id}`}>Open alert</Link>
          </div>
        </Card>
      ))}
    </div>
  );
}
