import React, { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { api } from "../lib/api";
import { Button } from "../components/ui/button";
import { newClientCommandId } from "../lib/agentOps";
import AgentTable from "../components/agentOps/AgentTable";
import CommandComposer from "../components/agentOps/CommandComposer";
import CommandHistory from "../components/agentOps/CommandHistory";
import ReceiptChainDialog from "../components/agentOps/ReceiptChainDialog";
import LiveSessionsPanel from "../components/agentOps/LiveSessionsPanel";

// Agent Operations (owner only; docs/CAOSCARE_AGENT_CONTROL_PLANE.md). Holds
// no agent state of its own: everything is read from /agent-control/*.
// Commands can only reach agents bound to an adapter - today the mock test
// agent. Real Claude sessions are listed read-only below.
export default function AgentOperations() {
  const [agents, setAgents] = useState([]);
  const [commands, setCommands] = useState([]);
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [busy, setBusy] = useState(false);
  const [inspect, setInspect] = useState(null);
  const [unavailable, setUnavailable] = useState(null);

  const load = useCallback(async () => {
    try {
      const [a, s] = await Promise.all([api.get("/agent-control/agents"), api.get("/agent-control/sessions")]);
      setAgents(a.data.agents);
      setSessions(s.data.sessions);
      setUnavailable(null);
      setSelectedId((cur) => cur || a.data.agents.find((x) => x.binding_id)?.agent_id || "");
    } catch (err) {
      const code = err?.response?.status;
      setUnavailable(code === 404 ? "Agent control is not enabled on this server."
        : code === 403 ? "Agent operations are for the owner only." : "Could not load agents.");
    }
  }, []);

  const loadCommands = useCallback(async () => {
    if (!selectedId) { setCommands([]); return; }
    try {
      const { data } = await api.get("/agent-control/commands", { params: { agent_id: selectedId } });
      setCommands(data.commands);
    } catch { setCommands([]); }
  }, [selectedId]);

  useEffect(() => { load(); const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);
  useEffect(() => { loadCommands(); }, [loadCommands]);

  const submit = async (agentId, instruction) => {
    setBusy(true);
    try {
      const { data } = await api.post("/agent-control/commands", {
        client_command_id: newClientCommandId(), target_agent_id: agentId, instruction,
      });
      toast.success(`Command ${data.status}`);
      return true;
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Command not sent");
      return false;
    } finally {
      setBusy(false);
      load();
      loadCommands();
    }
  };

  if (unavailable) {
    return <p className="text-sm text-caos-mute" data-testid="agent-ops-unavailable">{unavailable}</p>;
  }

  return (
    <div className="space-y-4" data-testid="agent-operations">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="font-display text-2xl text-caos-forest">Agent operations</h2>
          <p className="text-sm text-caos-mute">
            The Claude agents working on CAOSCare. Every command and every reply has a receipt. Agents not
            yet connected show OFFLINE and UNKNOWN; nothing about them is guessed.
          </p>
        </div>
        <Button variant="outline" onClick={() => { load(); loadCommands(); }} data-testid="agent-ops-refresh">
          Refresh
        </Button>
      </div>
      <AgentTable agents={agents} selectedId={selectedId} onSelect={setSelectedId} />
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="min-w-0">
          <CommandComposer agents={agents} selectedId={selectedId} onSelect={setSelectedId}
                           onSubmit={submit} busy={busy} />
        </div>
        <div className="min-w-0 lg:col-span-2">
          <h3 className="mb-2 font-display text-lg text-caos-forest">Recent commands</h3>
          <CommandHistory commands={commands} onInspect={setInspect} />
        </div>
      </div>
      <LiveSessionsPanel sessions={sessions} />
      <ReceiptChainDialog commandId={inspect} onClose={() => setInspect(null)} />
    </div>
  );
}
