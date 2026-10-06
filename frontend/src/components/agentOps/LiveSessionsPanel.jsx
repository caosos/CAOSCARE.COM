import React from "react";
import StatusBadge from "./StatusBadge";

// Read-only: the Claude Code sessions running on this host, as the backend
// discovered them. Not bound to agents and cannot receive commands - binding
// is a human decision.
export default function LiveSessionsPanel({ sessions }) {
  return (
    <section className="space-y-2" data-testid="live-sessions">
      <div>
        <h3 className="font-display text-lg text-caos-forest">Claude sessions on this host (read-only)</h3>
        <p className="text-xs text-caos-mute">
          Discovered from Claude Code's local session registry and the process table. These are not
          connected to the agents above and cannot be sent anything from here.
        </p>
      </div>
      {!sessions.length ? (
        <p className="text-sm text-caos-mute">No sessions found.</p>
      ) : (
        <div className="overflow-x-auto rounded border border-caos-line">
          <table className="w-full text-xs">
            <thead className="bg-stone-50 text-left text-caos-mute">
              <tr>{["Session", "PID", "Status", "Terminal", "Parent", "Started in", "Notes"].map((h) => (
                <th key={h} className="px-2 py-1.5 font-medium">{h}</th>))}</tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={`${s.pid}`} className="border-t border-caos-line" data-testid={`session-${s.pid}`}>
                  <td className="px-2 py-1.5 font-mono">{s.name || "—"}</td>
                  <td className="px-2 py-1.5 font-mono">{s.pid}</td>
                  <td className="px-2 py-1.5">
                    <StatusBadge label={s.alive ? String(s.status || "unknown").toUpperCase() : "GONE"}
                                 tone={!s.alive ? "bad" : s.status === "busy" ? "ok" : "mute"} />
                  </td>
                  <td className="px-2 py-1.5 font-mono">{s.tty || "—"}</td>
                  <td className="px-2 py-1.5">{s.parent_comm || "—"}</td>
                  <td className="px-2 py-1.5 font-mono break-all">{s.cwd || "—"}{s.cwd_branch ? ` (${s.cwd_branch})` : ""}</td>
                  <td className="px-2 py-1.5">
                    {s.session_id_shared && <div className="text-amber-800">Session id shared with another process</div>}
                    {s.alive && !s.pid_matches_registry && <div className="text-red-700">PID does not match registry</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
