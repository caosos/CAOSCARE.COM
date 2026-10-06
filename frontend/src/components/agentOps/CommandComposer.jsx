import React, { useState } from "react";
import { Button } from "../ui/button";
import { Textarea } from "../ui/textarea";
import { canCommand, MAX_INSTRUCTION, validateInstruction } from "../../lib/agentOps";

// Choose an agent and send it one instruction. Only agents bound to an
// adapter can receive anything; today that is the mock test agent only.
export default function CommandComposer({ agents, selectedId, onSelect, onSubmit, busy }) {
  const [text, setText] = useState("");
  const agent = agents.find((a) => a.agent_id === selectedId);
  const error = text ? validateInstruction(text) : null;
  const sendable = canCommand(agent) && !validateInstruction(text) && !busy;

  const submit = async (e) => {
    e.preventDefault();
    if (!sendable) return;
    const ok = await onSubmit(agent.agent_id, text);
    if (ok) setText("");
  };

  return (
    <form onSubmit={submit} className="space-y-2 rounded border border-caos-line p-3" data-testid="command-composer">
      <label className="block text-xs font-medium text-caos-mute" htmlFor="agent-select">Agent</label>
      <select id="agent-select" value={selectedId || ""} onChange={(e) => onSelect(e.target.value)}
              className="w-full rounded border border-caos-line px-2 py-1.5 text-sm" data-testid="agent-select">
        <option value="" disabled>Choose an agent</option>
        {agents.map((a) => (
          <option key={a.agent_id} value={a.agent_id}>
            {a.display_name} — {a.role}{canCommand(a) ? "" : " (not connected)"}
          </option>
        ))}
      </select>
      {agent && !canCommand(agent) && (
        <p className="text-xs text-caos-mute" data-testid="agent-not-connected">
          {agent.display_name} is not connected to CAOSCare yet, so it cannot receive commands.
        </p>
      )}
      <Textarea value={text} onChange={(e) => setText(e.target.value)} rows={4} maxLength={MAX_INSTRUCTION + 1}
                placeholder="Instruction" data-testid="command-text" />
      <div className="flex items-center justify-between gap-2">
        <span className={`text-xs ${error ? "text-red-700" : "text-caos-mute"}`}>
          {error || `${text.length}/${MAX_INSTRUCTION}`}
        </span>
        <Button type="submit" disabled={!sendable} data-testid="command-submit">
          {busy ? "Sending…" : "Send command"}
        </Button>
      </div>
    </form>
  );
}
