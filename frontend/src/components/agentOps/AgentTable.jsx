import React from "react";
import { agentState, known } from "../../lib/agentOps";
import { fmtTime } from "../../lib/simulator";
import StatusBadge from "./StatusBadge";

// Every registered agent. Values come straight from the registry; anything
// not known yet is shown as UNKNOWN. Clicking a row selects the agent.
export default function AgentTable({ agents, selectedId, onSelect }) {
  return (
    <div className="overflow-x-auto rounded border border-caos-line" data-testid="agent-table">
      <table className="w-full text-sm">
        <thead className="bg-stone-50 text-left text-xs text-caos-mute">
          <tr>
            {["Agent", "Role", "Status", "Current task", "Branch", "Last activity", "Last receipt"].map((h) => (
              <th key={h} className="px-3 py-2 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {agents.map((a) => {
            const st = agentState(a);
            return (
              <tr key={a.agent_id} onClick={() => onSelect(a.agent_id)}
                  className={`cursor-pointer border-t border-caos-line ${selectedId === a.agent_id ? "bg-amber-50" : "hover:bg-stone-50"}`}
                  data-testid={`agent-row-${a.agent_id}`}>
                <td className="px-3 py-2">
                  <div className="font-semibold text-caos-forest">{a.display_name}</div>
                  <div className="font-mono text-[11px] text-caos-mute">{a.agent_id}</div>
                </td>
                <td className="px-3 py-2">{a.role}</td>
                <td className="px-3 py-2 space-x-1 whitespace-nowrap">
                  <StatusBadge label={st.label} tone={st.tone} testId={`agent-status-${a.agent_id}`} />
                  {st.simulated && <StatusBadge label="SIMULATED" tone="sim" />}
                </td>
                <td className="px-3 py-2">{known(a.current_task)}</td>
                <td className="px-3 py-2 font-mono text-xs">{known(a.branch)}</td>
                <td className="px-3 py-2 whitespace-nowrap">{a.last_activity_at ? fmtTime(a.last_activity_at) : "UNKNOWN"}</td>
                <td className="px-3 py-2 font-mono text-[11px]">{known(a.last_receipt_id)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
