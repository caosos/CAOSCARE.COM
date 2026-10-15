/**
 * Room 214 Aria's read-only self-code inspection tools (owner feature,
 * 2026-10-15). Same dispatch contract as the other tool modules: returns a
 * result object for the three names it handles, undefined otherwise.
 *
 * The browser only relays. The backend proves, on every call, that this
 * session is the live canonical Room 214 session (routes/self_code_identity.py)
 * and refuses everything else with 403 - the room/session values sent here
 * are the session's own context, never an argument the model can set.
 * There is no write tool: nothing here can modify, run or deploy code.
 */
import { API } from "./api";

export const SELF_CODE_TOOLS = {
  inspect_own_code: "inspect",
  search_own_code: "search",
  read_own_code: "read",
};

// Embedded by the Room page build (room-node/aria_wake/ctl.sh sets
// REACT_APP_BUILD_SHA) so the backend can say whether the page serving the
// room is the revision it inspected. Null when the build did not set it.
export const PAGE_BUILD_SHA = process.env.REACT_APP_BUILD_SHA || null;

const REFUSED = "I can't inspect my own code from this session - that's only available to the verified Room 214 session.";

export async function executeSelfCodeTool({ name, args, ctx }) {
  const endpoint = SELF_CODE_TOOLS[name];
  if (!endpoint) return undefined;
  const a = args || {};
  const body = {
    session_id: ctx?.session_id || "",
    resident_id: ctx?.resident_id || "",
    frontend_build_sha: PAGE_BUILD_SHA,
  };
  if (name === "search_own_code") body.query = String(a.query || "");
  if (name === "read_own_code") {
    body.path = String(a.path || "");
    body.start_line = Number.isInteger(a.start_line) && a.start_line > 0 ? a.start_line : 1;
    if (Number.isInteger(a.end_line) && a.end_line > 0) body.end_line = a.end_line;
  }
  const r = await fetch(`${API}/aria/self-code/${endpoint}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (r.status === 403) {
    let reason = "refused";
    try { reason = (await r.json())?.detail?.reason || reason; } catch { /* no body */ }
    const outside = reason.startsWith("path_") || reason === "query_length";
    return { ok: false, refused: true, reason, message: outside ? "That file or query is outside what I'm allowed to read." : REFUSED };
  }
  if (!r.ok) return { ok: false, message: `couldn't reach the code inspection service (${r.status}).` };
  return await r.json();
}
