import React from "react";
import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Card } from "../ui/card";

const label = (value) => String(value || "unknown").replaceAll("_", " ");

function Counts({ counts }) {
  return (
    <dl className="grid grid-cols-2 gap-2 md:grid-cols-4" aria-label="Observed canonical records">
      {[
        ["Residents", counts.residents],
        ["Tasks", counts.tasks],
        ["Notifications", counts.notifications],
        ["Runs", counts.runs],
      ].map(([name, value]) => (
        <div key={name} className="rounded-lg border border-caos-line bg-white p-3">
          <dt className="text-xs font-bold uppercase tracking-widest text-caos-mute">{name}</dt>
          <dd className="mt-1 font-display text-2xl text-caos-forest">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export default function SimCommunityObserved({ loadState, snapshot, refreshFailed = false, onRetry }) {
  if (loadState === "loading" && !snapshot) {
    return (
      <Card className="border-caos-line p-4" data-testid="sim-observed-loading">
        <h2 className="font-display text-xl text-caos-forest">Observed community state</h2>
        <p className="mt-1 text-sm text-caos-mute">Verifying canonical database records…</p>
      </Card>
    );
  }

  if (!snapshot) {
    return (
      <Card className="border-caos-line p-4" data-testid="sim-observed-error">
        <h2 className="font-display text-xl text-caos-forest">Observed state unknown</h2>
        <p className="mt-1 text-sm text-caos-mute">
          The observed-state read failed. This does not mean zero residents or that the community is not provisioned.
        </p>
        <Button type="button" variant="outline" className="mt-3" onClick={onRetry}>Retry observed read</Button>
      </Card>
    );
  }

  const provisioning = snapshot.provisioning;
  return (
    <Card className="border-caos-line p-4 space-y-3" data-testid="sim-observed-ready">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-xl text-caos-forest">Observed community state</h2>
          <p className="text-sm text-caos-mute">Verified canonical records, separate from the planning preview.</p>
        </div>
        <Badge variant="outline" className={provisioning.state === "inconsistent" ? "text-caos-terracotta" : "text-caos-forest"}>
          {label(provisioning.state)}
        </Badge>
      </div>
      {refreshFailed && (
        <div className="rounded-lg border border-caos-amber bg-[#FDF3E3] p-3 text-sm" data-testid="sim-observed-stale">
          Last verified {snapshot.observed_at}; refresh failed. These counts were preserved and were not replaced with zero.
        </div>
      )}
      <Counts counts={snapshot.counts} />
      <p className="text-xs text-caos-mute">
        {provisioning.exact_blueprint_residents} of {provisioning.expected_residents} exact burn-in residents verified
        {provisioning.collision_count ? ` · ${provisioning.collision_count} marker or identity conflicts` : ""}.
      </p>
      {snapshot.marker_anomalies?.length > 0 && (
        <p className="text-xs font-semibold text-caos-terracotta" data-testid="sim-observed-anomalies">
          {snapshot.marker_anomalies.length} attributable marker anomalies require review.
        </p>
      )}
      <Button type="button" variant="outline" onClick={onRetry}>Refresh observed state</Button>
    </Card>
  );
}
