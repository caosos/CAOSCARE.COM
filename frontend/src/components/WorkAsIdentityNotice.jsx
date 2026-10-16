import React from "react";
import { Badge } from "./ui/badge";
import { Card } from "./ui/card";

// Work-as changes authorization scope, never identity. Keep that distinction
// visible while an owner/admin is doing frontline work so nobody can mistake
// the real human for one of the simulator's synthetic workers.
export default function WorkAsIdentityNotice({ principal, context, departmentLabel }) {
  if (!context) return null;
  const principalRole = context.principal_role || principal?.role || "admin";
  const actingRole = context.acting_role === "front_desk" ? "Front Desk" : "Staff";

  return (
    <Card className="mb-6 border-caos-amber bg-caos-amber/10 p-4" data-testid="work-as-identity-notice">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">REAL PERSON</Badge>
        <span className="font-semibold text-caos-forest" data-testid="work-as-principal">
          Signed in as {principal?.name || "authenticated administrator"} ({principalRole})
        </span>
      </div>
      <p className="mt-1 text-sm text-caos-ink" data-testid="work-as-authority">
        Working in {departmentLabel || context.acting_department} as {actingRole}. Actions are recorded as
        your real identity under this department authority—not as a simulated worker.
      </p>
    </Card>
  );
}
