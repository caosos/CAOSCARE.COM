"""RQ-001 demo data continuity: the demo community behaves as though time
passed while nobody was signed in.

Time is cut into fixed one-hour windows aligned to UTC. `last_simulated_at`
is the end of the last window that has been processed. On catch-up (backend
startup, staff sign-in, or the admin endpoint) every whole window between
`last_simulated_at` and now is processed exactly once:

  1. each open simulated demo request moves one lifecycle step
     (acknowledge -> start -> complete), oldest first, at most
     ADVANCE_PER_WINDOW per window;
  2. open simulated work above OPEN_CAP is closed as stale demo backlog
     (oldest first), so unresolved work stays bounded;
  3. during facility daytime, a fixed hash of the window start may raise
     one new request from a fixed catalogue (never twice in a category
     that is already open).

Scope (ENGINEERING_CONTRACT gate, Round 5 board): the demo room only. Work
is touched only if it is `simulated`, `simulation_scope == "demo_room"` and
in room DEMO, and only while the demo room holds the synthetic resident
alone (roster.resolve_cast). Real residents, rooms and facility records are
never read for writing.

Same world, no second lifecycle: requests come from
resident_requests.create_resident_request; every step is a task_actions
call by a simulated staff actor, so each change has its own chained
receipt. Each processed window adds one `demo_continuity_window` receipt
(chained per continuity state) that lists those receipts in provider_refs.

Exactly-once: the window range is claimed with one compare-and-set on
`last_simulated_at` before any work, so a second refresh or a concurrent
sign-in finds nothing left to process. Catch-up defers (and records why)
while a SIM-1 run is active, or a live email provider is configured.
"""
import asyncio
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from deps import db
from models import now_utc, uid
from routes import notifications, task_actions
from routes.actor_context import ActorContext
from routes.demo_kiosk import DEMO_ROOM
from routes.facility_local_time import facility_tz
from routes.receipts import create_receipt
from routes.task_lifecycle import LifecycleError
from routes.resident_requests import ResidentRequestInput, create_resident_request
from simulation import roster, scheduler

STATE_KEY = "demo_room"
WINDOW = timedelta(hours=1)
MAX_WINDOWS = 72            # a longer gap fast-forwards to the last 72 hours
ADVANCE_PER_WINDOW = 10
OPEN_CAP = 6
DAY_HOURS = range(7, 21)    # facility-local hours when new requests appear
OPEN = ("pending", "in_progress")

# Plausible things a resident asks for. Words carry no clock time, so the
# request bus's time-provenance guard has nothing to reject.
CATALOGUE = [
    ("maintenance", "The light over my bathroom mirror keeps flickering."),
    ("housekeeping", "Could someone bring me fresh towels, please?"),
    ("kitchen", "Could I get some extra coffee creamer with my tray?"),
    ("maintenance", "My closet door is sticking and hard to open."),
    ("housekeeping", "Would someone please empty my wastebasket?"),
    ("kitchen", "I'd like a cup of hot tea, please."),
]
DONE_NOTE = "Simulated: taken care of."
BACKLOG_NOTE = "Simulated: closed as stale demo backlog (demo continuity)."

_lock = asyncio.Lock()
# The continuity process itself: a simulated agent, never a real person or a
# real system authority over real work.
_ACTOR = ActorContext(actor_id="sim:system:demo_continuity", actor_type="simulated-agent",
                      identity_basis="synthetic", channel="simulator",
                      name="SIM - demo continuity", role="system", simulated=True)
_AUTHORITY = "simulator:demo_continuity"


def _floor(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


def _parse(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def window_hash(start: datetime) -> int:
    """Deterministic per window: same window start, same number, every run."""
    return int(hashlib.sha256(start.isoformat().encode()).hexdigest()[:12], 16)


def staff_for(department: str) -> tuple:
    """The simulated staff member who acts for a department. Maintenance is
    SIM-1's maintenance tech; other departments get a stable `sim:` id.
    Never a User: cannot sign in, never in the roster."""
    if department == roster.STAFF["department"]:
        return roster.staff_actor(), roster.staff_profile()
    aid, name = f"sim:staff:{department}-1", f"SIM - {department.replace('_', ' ').title()} staff"
    actor = ActorContext(actor_id=aid, actor_type="simulated-agent", identity_basis="synthetic",
                         channel="simulator", name=name, role="staff", department=department, simulated=True)
    return actor, {"user_id": aid, "name": name, "role": "staff", "department": department, "simulated": True}


async def _staff(task: dict) -> Optional[tuple]:
    """The simulated staff member for a task's department, or None when a
    real account already holds that id (hands off; never act as a person)."""
    actor, profile = staff_for(task.get("visibility_role") or "all_staff")
    if await db.users.find_one({"user_id": actor.actor_id}, {"_id": 1}):
        return None
    return actor, profile


def _demo_scope() -> dict:
    return {"simulated": True, "simulation_scope": "demo_room", "room": DEMO_ROOM}


async def get_state() -> Optional[dict]:
    return await db.demo_continuity.find_one({"key": STATE_KEY}, {"_id": 0})


async def ensure_state(now: Optional[datetime] = None) -> Optional[dict]:
    """The continuity record, created on first sight of a valid demo room.
    Its creation is receipted and starts the chain. No demo room -> None."""
    st = await get_state()
    if st:
        return st
    try:
        await roster.resolve_cast()
    except roster.IdentityConflict:
        return None
    start = _floor(now or now_utc())
    origin = uid("rcpt")
    doc = {"key": STATE_KEY, "room": DEMO_ROOM, "last_simulated_at": start.isoformat(),
           "origin_receipt_id": origin, "last_receipt_id": origin, "windows_processed": 0,
           "created_at": now_utc().isoformat(), "simulated": True}
    res = await db.demo_continuity.update_one({"key": STATE_KEY}, {"$setOnInsert": doc}, upsert=True)
    if res.upserted_id is None:
        return await get_state()    # another caller created it first
    await create_receipt(
        action_type="demo_continuity_started", related_object_type="demo_continuity",
        related_object_id=STATE_KEY, room=DEMO_ROOM, status="created", receipt_id=origin,
        result=f"demo continuity clock starts at {start.isoformat()}",
        provenance={**_ACTOR.receipt_fields(), "authority": _AUTHORITY,
                    "correlation_id": origin, "after_state": {"last_simulated_at": start.isoformat()},
                    "result_label": "simulated", "next_state": "idle"})
    return await get_state()


async def _record(st: dict, action_type: str, *, before: dict, after: dict, result: str,
                  refs: Optional[list] = None, status: str = "completed",
                  failure_reason: Optional[str] = None, chain: bool = True) -> dict:
    """One continuity receipt. `chain=False` is evidence only (a deferral)."""
    receipt = await create_receipt(
        action_type=action_type, related_object_type="demo_continuity", related_object_id=STATE_KEY,
        room=DEMO_ROOM, status=status, result=result, failure_reason=failure_reason,
        provenance={**_ACTOR.receipt_fields(), "authority": _AUTHORITY,
                    "parent_receipt_id": st.get("last_receipt_id") if chain else None,
                    "correlation_id": st.get("origin_receipt_id") if chain else None,
                    "before_state": before, "after_state": after,
                    "result_label": "failed" if status == "failed" else "simulated",
                    "provider_refs": list(refs or []), "next_state": "idle"})
    if chain:
        st["last_receipt_id"] = receipt["receipt_id"]
        await db.demo_continuity.update_one({"key": STATE_KEY},
                                            {"$set": {"last_receipt_id": receipt["receipt_id"]}})
    return receipt


async def _open_tasks() -> list:
    q = {**_demo_scope(), "status": {"$in": list(OPEN)}}
    return await db.staff_tasks.find(q, {"_id": 0}).sort("created_at", 1).to_list(1000)


async def _advance(task: dict, refs: list) -> Optional[str]:
    """One lifecycle step for one simulated request. Returns what happened."""
    if not task.get("simulated") or task.get("room") != DEMO_ROOM:
        return None                                   # belt and braces: never real work
    who = await _staff(task)
    if not who:
        return None
    actor, profile = who
    tid = task["task_id"]
    try:   # a refusal (e.g. a legacy request) is recorded by the lifecycle itself
        if task["status"] == "pending" and not task.get("acknowledged_at"):
            step, (_, r) = "acknowledged", await task_actions.acknowledge(tid, actor, profile)
        elif task["status"] == "pending":
            step, (_, r) = "started", await task_actions.start(tid, actor, profile)
        else:
            step, (_, r) = "completed", await task_actions.complete(tid, DONE_NOTE, actor, profile)
    except LifecycleError:
        return None
    if r:
        refs.append(r["receipt_id"])
    return step


async def _process_window(start: datetime, cast: dict, tz: str, generated: dict) -> dict:
    end = start + WINDOW
    refs, out = [], {"window_start": start.isoformat(), "advanced": [], "closed_backlog": [], "generated": None}
    open_tasks = await _open_tasks()
    # 2. bound the backlog first: oldest beyond the cap close as stale demo work.
    for t in open_tasks[:max(0, len(open_tasks) - OPEN_CAP)]:
        who = await _staff(t)
        if not who:
            continue
        try:
            _, r = await task_actions.skip(t["task_id"], BACKLOG_NOTE, *who)
        except LifecycleError:
            continue
        if r:
            refs.append(r["receipt_id"])
            out["closed_backlog"].append(t["task_id"])
    # 1. advance what remains, if it existed before this window ended.
    for t in (await _open_tasks())[:ADVANCE_PER_WINDOW]:
        born = generated.get(t["task_id"])
        existed = born < start if born else _parse(t["created_at"]) < end
        if existed:
            step = await _advance(t, refs)
            if step:
                out["advanced"].append({"task_id": t["task_id"], "step": step})
    # 3. maybe one new request, by a fixed rule on the window start.
    h = window_hash(start)
    local_hour = start.astimezone(ZoneInfo(tz)).hour
    if local_hour in DAY_HOURS and h % 3 == 0 and len(await _open_tasks()) < OPEN_CAP:
        category, words = CATALOGUE[(h // 3) % len(CATALOGUE)]
        open_cats = {t.get("category") for t in await _open_tasks()}
        if category not in open_cats:
            r = cast["resident"]
            made = await create_resident_request(ResidentRequestInput(
                category=category, resident_id=r["actor_id"], room=r["room"],
                resident_words=words, summary=words, source=roster.RESIDENT_CHANNEL))
            refs.append(made["receipt_id"])
            generated[made["task_id"]] = start
            out["generated"] = {"task_id": made["task_id"], "category": category}
    out["receipt_refs"] = refs
    return out


async def _counts() -> dict:
    scope = _demo_scope()
    return {"open": await db.staff_tasks.count_documents({**scope, "status": {"$in": list(OPEN)}}),
            "closed": await db.staff_tasks.count_documents({**scope, "status": {"$in": ["completed", "skipped"]}})}


async def catch_up(now: Optional[datetime] = None, trigger: str = "manual") -> dict:
    """Process every whole window since `last_simulated_at`, exactly once."""
    now = now or now_utc()
    async with _lock:
        st = await ensure_state(now)
        if not st:
            return {"status": "no_demo_room", "windows": 0}
        last = _parse(st["last_simulated_at"])
        target = _floor(now)
        if target <= last:
            return {"status": "up_to_date", "windows": 0, "last_simulated_at": st["last_simulated_at"]}
        reason = None
        if await scheduler.active_run():
            reason = "a SIM-1 simulation run is active"
        elif notifications.RESEND_KEY:
            reason = "a live email provider is configured; simulated requests would send real mail"
        else:
            try:
                cast = await roster.resolve_cast()
            except roster.IdentityConflict as e:
                reason, cast = f"identity conflict: {e}", None
        if reason:
            await _record(st, "demo_continuity_deferred", before={"last_simulated_at": last.isoformat()},
                          after={"last_simulated_at": last.isoformat()}, status="failed",
                          result=f"catch-up ({trigger}) deferred", failure_reason=reason, chain=False)
            return {"status": "deferred", "reason": reason, "windows": 0}
        # Claim the whole range before doing any work: exactly-once.
        claimed = await db.demo_continuity.find_one_and_update(
            {"key": STATE_KEY, "last_simulated_at": st["last_simulated_at"]},
            {"$set": {"last_simulated_at": target.isoformat(), "last_catch_up_at": now.isoformat()}})
        if not claimed:
            return {"status": "already_processed", "windows": 0}
        windows, skipped = [], 0
        first = last
        if (target - last) > WINDOW * MAX_WINDOWS:
            first = target - WINDOW * MAX_WINDOWS
            skipped = int((first - last) / WINDOW)
            before = await _counts()
            await _record(st, "demo_continuity_fast_forward", before={**before, "last_simulated_at": last.isoformat()},
                          after={**before, "last_simulated_at": first.isoformat()},
                          result=f"{skipped} hours skipped; only the last {MAX_WINDOWS} hours are simulated")
        tz = await facility_tz()
        generated: dict = {}
        w = first
        while w < target:
            before = await _counts()
            out = await _process_window(w, cast, tz, generated)
            after = await _counts()
            await _record(st, "demo_continuity_window",
                          before={**before, "window_start": w.isoformat()},
                          after={**after, "window_end": (w + WINDOW).isoformat()},
                          result=(f"{trigger}: {len(out['advanced'])} advanced, "
                                  f"{len(out['closed_backlog'])} backlog closed, "
                                  f"{'1 new request' if out['generated'] else 'no new request'}"),
                          refs=out["receipt_refs"])
            windows.append(out)
            w += WINDOW
        await db.demo_continuity.update_one({"key": STATE_KEY}, {"$inc": {"windows_processed": len(windows)}})
        return {"status": "caught_up", "windows": len(windows), "skipped_hours": skipped,
                "last_simulated_at": target.isoformat(), "detail": windows, **await _counts()}


def catch_up_in_background(trigger: str) -> None:
    """Fire-and-forget for sign-in/startup. Never blocks or fails the caller."""
    async def _run():
        try:
            await catch_up(trigger=trigger)
        except Exception as e:   # noqa: BLE001 - continuity must never break sign-in
            import logging
            logging.warning(f"demo continuity catch-up ({trigger}) failed: {e}")
    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        pass
