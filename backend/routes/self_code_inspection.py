"""POST /api/aria/self-code/{inspect|search|read}: Room 214 Aria reads her own source.

Each call: prove the caller is the live, canonical Room 214 session
(routes/self_code_identity.py) -> do the bounded read-only work
(routes/self_code_source.py) -> write one receipt (allowed or refused,
never the file contents) -> answer. No write path exists in this module or
the two it uses: there is no endpoint, argument or branch that modifies a
file, runs a command, touches git state or the database beyond the receipt.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from routes.actor_context import actor_resident_claim
from routes.receipts import create_receipt
from routes.self_code_identity import verify_room214_session, SELF_INSPECT_ROOM
from routes import self_code_source as src

router = APIRouter(prefix="/aria/self-code", tags=["aria-self-code"])
ACTION = "self_code_inspection"


class InspectInput(BaseModel):
    session_id: str = Field(min_length=1, max_length=100)
    resident_id: str = Field(min_length=1, max_length=100)
    frontend_build_sha: Optional[str] = Field(default=None, max_length=64)   # reported by the page build


class SearchInput(InspectInput):
    query: str = Field(min_length=1, max_length=200)


class ReadInput(InspectInput):
    path: str = Field(min_length=1, max_length=300)
    start_line: int = Field(default=1, ge=1, le=1_000_000)
    end_line: Optional[int] = Field(default=None, ge=1, le=1_000_000)


def _revision_facts(body: InspectInput, rel: Optional[str] = None) -> dict:
    rev = src.revision(rel)
    reported = (body.frontend_build_sha or "").strip() or None
    rev["loaded_frontend_sha_reported_by_page"] = reported
    rev["frontend_match"] = src._same_commit(rev["inspected_sha"], reported)
    return rev


def _truth_line(rev: dict) -> str:
    sha = (rev.get("inspected_sha") or "unknown")[:12]
    if rev.get("backend_match") is True:
        return f"Inspected revision {sha} is the code currently serving Room 214's backend."
    if rev.get("backend_match") is False:
        return (f"Inspected revision {sha} is NOT the backend currently serving Room 214 "
                f"(loaded {rev.get('loaded_backend_sha')}). Say so.")
    return f"Inspected revision {sha}; whether it matches the running backend is unknown. Say so."


async def _receipt(tool: str, body: InspectInput, gate: dict, request_facts: dict,
                   rev: Optional[dict], allowed: bool, reason: Optional[str] = None) -> dict:
    """One receipt per attempt. Carries paths/queries/ranges and revisions,
    never source text. Refusals are receipted with the unverified claim."""
    verified = bool(gate.get("allowed"))            # session proven, even when the path/query is refused
    room = SELF_INSPECT_ROOM if verified else None
    actor = actor_resident_claim(body.resident_id, room, "aria_voice")
    after = {"tool": tool, "request": request_facts, "allowed": allowed, "reason": reason,
             "inspected_sha": (rev or {}).get("inspected_sha"),
             "loaded_backend_sha": (rev or {}).get("loaded_backend_sha") or src.loaded_sha(),
             "backend_match": (rev or {}).get("backend_match"),
             "frontend_match": (rev or {}).get("frontend_match"),
             "origin": gate.get("origin"), "trigger_source": gate.get("trigger_source")}
    return await create_receipt(
        action_type=ACTION, related_object_type=ACTION, related_object_id=f"sci_{uuid.uuid4().hex[:12]}",
        source="aria_voice", resident_id=body.resident_id if verified else None,
        room=room, conversation_session_id=body.session_id,
        status="completed" if allowed else "failed", result=tool if allowed else None,
        failure_reason=None if allowed else reason,
        provenance={**actor.receipt_fields(), "authority": gate.get("authority") if verified else None,
                    "after_state": after, "result_label": "verified" if allowed else "failed"},
    )


async def _gate(tool: str, body: InspectInput, request: Request, request_facts: dict) -> dict:
    gate = await verify_room214_session(body.session_id, body.resident_id, request)
    if not gate["allowed"]:
        rcpt = await _receipt(tool, body, gate, request_facts, None, False, gate["reason"])
        raise HTTPException(status_code=403, detail={
            "reason": gate["reason"], "receipt_id": rcpt["receipt_id"],
            "message": "Self-inspection is only available to the verified Room 214 session.",
        })
    return gate


async def _refuse_source(tool: str, body: InspectInput, gate: dict, facts: dict, reason: str):
    rcpt = await _receipt(tool, body, gate, facts, _revision_facts(body), False, reason)
    raise HTTPException(status_code=403, detail={"reason": reason, "receipt_id": rcpt["receipt_id"],
                                                 "message": "That file or query is outside what I'm allowed to read."})


@router.post("/inspect")
async def inspect_own_code(body: InspectInput, request: Request):
    gate = await _gate("inspect_own_code", body, request, {})
    rev = _revision_facts(body)
    files = src.approved_files()
    rcpt = await _receipt("inspect_own_code", body, gate, {"file_count": len(files)}, rev, True)
    return {"ok": True, "allowed": True, "room": gate["room"], "session_id": gate["session_id"],
            **rev, "approved_source_roots": list(src.APPROVED_GLOBS), "approved_files": files,
            "receipt_id": rcpt["receipt_id"], "read_only": True, "write_tools": [],
            "message": _truth_line(rev)}


@router.post("/search")
async def search_own_code(body: SearchInput, request: Request):
    facts = {"query": body.query[:src.MAX_QUERY]}
    gate = await _gate("search_own_code", body, request, facts)
    try:
        result = src.search(body.query)
    except src.SourceRefused as e:
        await _refuse_source("search_own_code", body, gate, facts, e.reason)
    rev = _revision_facts(body)
    rcpt = await _receipt("search_own_code", body, gate, {**facts, "match_count": len(result["matches"])}, rev, True)
    return {"ok": True, **result, **rev, "receipt_id": rcpt["receipt_id"], "message": _truth_line(rev)}


@router.post("/read")
async def read_own_code(body: ReadInput, request: Request):
    facts = {"path": body.path[:300], "start_line": body.start_line, "end_line": body.end_line}
    gate = await _gate("read_own_code", body, request, facts)
    try:
        result = src.read_lines(body.path, body.start_line, body.end_line)
    except src.SourceRefused as e:
        await _refuse_source("read_own_code", body, gate, facts, e.reason)
    rev = _revision_facts(body, result["path"])
    rcpt = await _receipt("read_own_code", body, gate, {**facts, "start": result["start"], "end": result["end"]}, rev, True)
    line = _truth_line(rev)
    if rev.get("local_modifications"):
        line += " This file also has uncommitted local changes on disk."
    return {"ok": True, **result, **rev, "receipt_id": rcpt["receipt_id"], "message": line}
