import React from "react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Trash2, Pencil, ChevronDown } from "lucide-react";
import { workspaceLabel } from "../lib/roleHome";
import { SetPasswordDialog } from "../components/PasswordDialogs";

// Compact (phone/tablet) presentation for Users & access - same data,
// same handlers, same data-testids as StaffTab.jsx's <Table>. Name + role
// + department are the identity/status a staff member needs at a glance;
// email/workspace/auth-provider and Delete sit behind a native <details>
// disclosure, matching ResidentsCards' pattern.
export default function StaffCards({ staff, deptLabel, onEdit, onDelete }) {
  return (
    <div className="space-y-3" data-testid="staff-cards">
      {staff.map((s) => (
        <div key={s.user_id} data-testid={`staff-row-${s.user_id}`} className="rounded-2xl border border-caos-line p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="font-medium text-caos-forest truncate">{s.name}</div>
              <div className="text-caos-mute text-xs uppercase font-bold tracking-wider mt-0.5">{s.role}</div>
            </div>
            <div className="shrink-0" data-testid={`staff-dept-${s.user_id}`}>
              {s.department
                ? <Badge variant="outline">{deptLabel(s.department)}</Badge>
                : <span className="text-caos-mute text-xs italic">No department</span>}
            </div>
          </div>

          <div className="flex flex-wrap gap-2 mt-3">
            <Button variant="outline" size="sm" onClick={() => onEdit(s)} data-testid={`edit-staff-${s.user_id}`} className="border-2 rounded-full">
              <Pencil className="w-4 h-4 mr-1" /> Edit
            </Button>
            <SetPasswordDialog userId={s.user_id} name={s.name} />
          </div>

          <details className="mt-3 group">
            <summary className="flex items-center gap-1 text-xs font-semibold uppercase tracking-wider text-caos-mute cursor-pointer select-none list-none">
              <ChevronDown className="w-3.5 h-3.5 transition-transform group-open:rotate-180" /> More
            </summary>
            <div className="mt-3 space-y-2 text-sm text-caos-mute">
              <div><span className="font-semibold text-caos-forest">Email: </span>{s.email}</div>
              <div><span className="font-semibold text-caos-forest">Workspace: </span>{workspaceLabel(s)}</div>
              <div><span className="font-semibold text-caos-forest">Auth: </span>{s.auth_provider}</div>
              <Button variant="ghost" size="sm" onClick={() => onDelete(s.user_id)} data-testid={`del-staff-${s.user_id}`} className="px-0">
                <Trash2 className="w-4 h-4 text-caos-terracotta mr-1" /> Delete
              </Button>
            </div>
          </details>
        </div>
      ))}
    </div>
  );
}
