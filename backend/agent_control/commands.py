"""Command service: issue → deliver → collect reply, one receipt per step.

Receipts use the canonical create_receipt with SIM-0 provenance, chained like
the simulator's run receipts: parent_receipt_id = the previous step,
correlation_id = the command's origin receipt. status_log is append-only.
An agent's reply is a self-report, so it is never labelled verified.
"""
from typing import Optional

from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from deps import db
from models import now_utc, uid
from routes.actor_context import ActorContext, actor_from_user, actor_system
from routes.receipts import create_receipt
from agent_control import registry
from agent_control.adapters import ADAPTERS
from agent_control.models import CommandInput

AUTHORITY = "owner_only"


def _snap(cmd: dict) -> dict:
    return {"status": cmd.get("status"), "target_agent_id": cmd.get("target_agent_id")}


async def _receipt(cmd: Optional[dict], actor: ActorContext, action: str, *, source: str,
                   status: str, label: str, before: Optional[dict], after: Optional[dict],
                   result: Optional[str] = None, failure: Optional[str] = None,
                   object_id: Optional[str] = None) -> dict:
    rid = uid("rcpt")
    parent = cmd.get("last_receipt_id") if cmd else None
    origin = cmd.get("origin_receipt_id") if cmd else None
    return await create_receipt(
        action_type=action, related_object_type="agent_command",
        related_object_id=object_id or (cmd or {}).get("command_id") or "none",
        source=source, status=status, result=result, failure_reason=failure, receipt_id=rid,
        provenance={**actor.receipt_fields(), "authority": AUTHORITY,
                    "parent_receipt_id": parent, "correlation_id": origin or rid,
                    "before_state": before, "after_state": after, "result_label": label,
                    "next_state": (after or {}).get("status")})


async def _transition(cmd: dict, to: str, actor: ActorContext, action: str, *, source: str,
                      label: str, status: str = "completed", result: Optional[str] = None,
                      failure: Optional[str] = None, extra: Optional[dict] = None) -> dict:
    before = _snap(cmd)
    after = {**before, "status": to}
    rec = await _receipt(cmd, actor, action, source=source, status=status, label=label,
                         before=before, after=after, result=result, failure=failure)
    entry = {"at": now_utc().isoformat(), "from_status": cmd["status"], "to_status": to,
             "by": actor.actor_id, "receipt_id": rec["receipt_id"], "note": result or failure}
    sets = {"status": to, "last_receipt_id": rec["receipt_id"], **(extra or {})}
    await db.agent_commands.update_one({"command_id": cmd["command_id"]},
                                       {"$set": sets, "$push": {"status_log": entry}})
    cmd.update(sets)
    cmd.setdefault("status_log", []).append(entry)
    return rec


async def _refuse(owner: ActorContext, reason: str, code: int, target: str) -> None:
    await _receipt(None, owner, "agent_command_refused", source="staff", status="failed",
                   label="failed", before=None, after=None, failure=reason, object_id=target)
    raise HTTPException(status_code=code, detail=f"{reason}. The attempt was recorded.")


async def issue(data: CommandInput, user: dict) -> dict:
    owner = actor_from_user(user)
    await registry.ensure_seeded()
    agent = await registry.get_agent(data.target_agent_id)
    if not agent:
        await _refuse(owner, "unknown agent", 404, data.target_agent_id)
    binding = registry.binding_for(agent)
    if not binding:
        await _refuse(owner, f"agent {agent['agent_id']} is not bound to a session", 409,
                      agent["agent_id"])
    if data.parent_command_id and not await db.agent_commands.find_one(
            {"command_id": data.parent_command_id}, {"_id": 1}):
        await _refuse(owner, "parent command not found", 404, data.target_agent_id)

    cmd = {
        "command_id": uid("acmd"), "client_command_id": data.client_command_id,
        "issued_by": {"user_id": user["user_id"], "name": user.get("name"), "role": user.get("role")},
        "target_agent_id": agent["agent_id"], "instruction": data.instruction,
        "parent_command_id": data.parent_command_id,
        "based_on_integration_sha": data.based_on_integration_sha,
        "status": "queued", "status_log": [], "created_at": now_utc().isoformat(),
        "origin_receipt_id": None, "delivery_receipt_id": None, "response_receipt_id": None,
        "last_receipt_id": None, "adapter": binding["adapter"],
    }
    try:
        await db.agent_commands.insert_one(dict(cmd))
    except DuplicateKeyError:
        await _refuse(owner, "duplicate client_command_id (replay)", 409, agent["agent_id"])

    origin = await _receipt(cmd, owner, "agent_command_issued", source="staff", status="created",
                            label="verified", before=None, after=_snap(cmd))
    entry = {"at": now_utc().isoformat(), "from_status": None, "to_status": "queued",
             "by": owner.actor_id, "receipt_id": origin["receipt_id"], "note": None}
    await db.agent_commands.update_one({"command_id": cmd["command_id"]}, {
        "$set": {"origin_receipt_id": origin["receipt_id"], "last_receipt_id": origin["receipt_id"]},
        "$push": {"status_log": entry}})
    cmd.update(origin_receipt_id=origin["receipt_id"], last_receipt_id=origin["receipt_id"],
               status_log=[entry])

    await _deliver(cmd, binding)
    return await get_command(cmd["command_id"])


async def _deliver(cmd: dict, binding: dict) -> None:
    adapter = ADAPTERS[binding["adapter"]]
    system = actor_system(f"agent_control:{adapter.kind}")
    delivery = await adapter.send_command(binding, cmd)
    label = "simulated" if delivery.simulated else "verified"
    if not delivery.ok:
        await _transition(cmd, "failed", system, "agent_command_delivery_failed", source="system",
                          status="failed", label="failed", failure=delivery.evidence)
        return
    rec = await _transition(cmd, "delivered", system, "agent_command_delivered", source="system",
                            label=label, result=delivery.evidence)
    cmd["delivery_receipt_id"] = rec["receipt_id"]
    await db.agent_commands.update_one({"command_id": cmd["command_id"]},
                                       {"$set": {"delivery_receipt_id": rec["receipt_id"]}})

    reply = await adapter.collect_reply(binding, cmd)
    if reply is None:
        return
    agent_actor = ActorContext(
        actor_id=f"agent:{cmd['target_agent_id']}",
        actor_type="simulated-agent" if reply.simulated else "system",
        identity_basis="synthetic" if reply.simulated else "system",
        channel=f"agent_control:{adapter.kind}", name=cmd["target_agent_id"], role="agent",
        simulated=reply.simulated)
    # Self-report: never "verified" (receipt law).
    rlabel = "simulated" if reply.simulated else "unverified"
    rec = await _transition(cmd, reply.status, agent_actor, f"agent_command_{reply.status}",
                            source="system", label=rlabel, result=reply.message)
    await db.agent_commands.update_one({"command_id": cmd["command_id"]},
                                       {"$set": {"response_receipt_id": rec["receipt_id"],
                                                 "last_message": reply.message}})
    await db.agent_registry.update_one({"agent_id": cmd["target_agent_id"]}, {"$set": {
        "last_activity_at": now_utc().isoformat(), "last_message": reply.message,
        "last_receipt_id": rec["receipt_id"]}})


async def get_command(command_id: str) -> Optional[dict]:
    return await db.agent_commands.find_one({"command_id": command_id}, {"_id": 0})


async def list_commands(agent_id: Optional[str] = None, limit: int = 50) -> list:
    q = {"target_agent_id": agent_id} if agent_id else {}
    return await db.agent_commands.find(q, {"_id": 0}).sort("created_at", -1).to_list(limit)


async def receipt_chain(command: dict) -> list:
    """Every receipt for this command, in chain order (origin first)."""
    recs = await db.receipts.find({"related_object_type": "agent_command",
                                   "related_object_id": command["command_id"]},
                                  {"_id": 0}).to_list(100)
    by_parent = {r.get("parent_receipt_id"): r for r in recs}
    out, cur = [], by_parent.get(None)
    while cur and len(out) < len(recs):
        out.append(cur)
        cur = by_parent.get(cur["receipt_id"])
    return out
