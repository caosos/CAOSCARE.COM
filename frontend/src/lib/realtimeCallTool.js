// call_contact (resident Aria core step 4): asks the backend to call the front
// desk or an approved family contact and speaks only the backend's answer.
// Until an outbound phone path exists the backend always says calling isn't
// set up; this file never invents "calling" / "ringing" / "connected".
import { API } from "./api";

export async function executeCallTool({ name, args, ctx }) {
  if (name !== "call_contact") return null;
  let token = null;
  try { token = localStorage.getItem("caos_token"); } catch { /* no storage */ }
  try {
    const r = await fetch(`${API}/telephony/room-call-request`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: JSON.stringify({ target: args?.target || "", resident_id: ctx?.residentId || ctx?.resident_id || null, session_id: ctx?.sessionId || ctx?.session_id || null }),
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) return { ok: false, message: "I can't place calls from here right now." };
    return { ok: !!data.ok, message: data.message || "I can't place calls from here right now.", outcome: data.outcome };
  } catch {
    return { ok: false, message: "I can't place calls from here right now." };
  }
}
