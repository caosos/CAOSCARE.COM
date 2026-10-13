import { findDeviceGuarded } from "./deviceAmbiguity";
import { numbersIn, VOLUME_PHRASES } from "./realtimeRoomControls";
import { conversationVolumeTarget, isStateReportingVolumeDevice, noteResidentVolumeChoice } from "./callAudioDuck";

export async function handleToggleTv(room, args, ctx, postRoomCommand) {
  if (!room) return { ok: false, message: "no room context — I can't reach the TV here." };
  const found = await findDeviceGuarded({ room, kind: "tv", noun: "TV", tool: "toggle_tv", args, ctx });
  if (found.fail) return found.fail;
  if (!found.device) return { ok: false, message: "there's no TV set up in this room yet." };

  const heard = (ctx?.last_user_text || "").trim();
  const requestedVolume = typeof args.volume === "number";
  const volumeGrounded = args.state === "on" && requestedVolume && VOLUME_PHRASES.test(heard) &&
    numbersIn(heard).has(Math.round(args.volume));
  if (args.state === "on" && requestedVolume && !volumeGrounded) {
    return { ok: false, message: "What volume would you like?" };
  }
  if (volumeGrounded && !isStateReportingVolumeDevice(found.device)) {
    return { ok: false, message: "this TV can't report its current volume. A state-reporting smart TV is required for voice volume adjustments." };
  }

  const power = await postRoomCommand(room, "power", args.state, "tv", ctx?.session_id, found.device.device_id);
  if (!power.ok) return { ok: false, message: `couldn't reach the TV (${power.status}).` };
  if (!volumeGrounded) return { ok: true, message: `turned the TV ${args.state}.` };

  const desired = Math.max(0, Math.min(100, Math.round(args.volume)));
  const duringConversation = conversationVolumeTarget(found.device.device_id, desired);
  const response = await postRoomCommand(room, "volume", duringConversation, "tv", ctx?.session_id, found.device.device_id);
  if (!response.ok) return { ok: false, message: `couldn't change the TV volume (${response.status}).` };
  const data = await response.json().catch(() => null);
  if (!data || data.verified !== true || typeof data.state?.volume !== "number") {
    return { ok: false, message: "the TV did not provide a verified volume reading, so I can't confirm that change." };
  }
  noteResidentVolumeChoice(found.device.device_id, desired);
  return { ok: true, message: `turned the TV on and kept it lower while we talk. Ask the resident, "Is that good?"` };
}
