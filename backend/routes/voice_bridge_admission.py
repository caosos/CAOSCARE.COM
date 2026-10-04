"""Voice bridge capacity: priority classes and admission.

Every turn is classified from the resident's words before any model call:

  1 emergency      fall, can't breathe, chest pain, bleeding, "help me"
  2 staff help     nurse, aide, bathroom, help getting up, any "help"
  3 operational    maintenance, broken/leaking, ride/transport, front desk
  4 room action    light, lamp, TV, temperature, thermostat, heat, cool
  5 information    menu/dinner/lunch, activities/schedule, time, weather
  6 conversation   everything else

Priority 1 never waits for capacity: the bridge escalates it directly
(voice_bridge.py) without the language model. The rest share
CAOSCARE_VOICE_BRIDGE_MAX_ACTIVE model slots; the last
CAOSCARE_VOICE_BRIDGE_RESERVED of them are usable only by priority 2, so
conversation can never fill the slots staff-help needs. A turn that cannot
get a slot within its class's wait limit is answered at once, honestly,
with a receipt - never dropped silently.

Admission state is per backend process (per uvicorn worker); the
conversation, requests and receipts it governs live in Mongo.
"""
import asyncio
import heapq
import itertools
import os
import re
import time

EMERGENCY = re.compile(
    r"\b(i (just )?fell|i'?ve fallen|i have fallen|fallen down|can'?t breathe|cannot breathe|"
    r"chest pains?|i'?m bleeding|bleeding (a lot|badly)|emergency|call 911|call an ambulance)\b")
EMERGENCY_WHOLE = re.compile(r"(please )?help( me)?( please)?( now)?")
STAFF = re.compile(r"\b(nurse|aide|caregiver|bathroom|toilet|help getting|get up|help)\b")
OPERATIONAL = re.compile(r"\b(maintenance|broken|leak(ing|s)?|clogged|repair|fix|ride|transport(ation)?|"
                         r"appointment|front desk|housekeeping|towels?)\b")
ROOM = re.compile(r"\b(light|lights|lamp|tv|television|temperature|thermostat|heat|cool|cooler|warmer|degrees)\b")
INFO = re.compile(r"\b(menu|dinner|lunch|breakfast|eat|activit(y|ies)|schedule|today|time|weather)\b")
CLASS_NAMES = {1: "emergency", 2: "staff_help", 3: "operational", 4: "room_action",
               5: "information", 6: "conversation"}
MAX_WAIT_S = {2: 6.0, 3: 5.0, 4: 4.0, 5: 2.0, 6: 2.0}


def _norm(text: str) -> str:
    t = (text or "").lower().replace("’", "'")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", t)).strip()


def classify(text: str) -> int:
    t = _norm(text)
    if EMERGENCY.search(t) or EMERGENCY_WHOLE.fullmatch(t):
        return 1
    for prio, pat in ((2, STAFF), (3, OPERATIONAL), (4, ROOM), (5, INFO)):
        if pat.search(t):
            return prio
    return 6


class Admission:
    def __init__(self, max_active: int, reserved: int):
        self.max_active = max(1, max_active)
        self.reserved = min(max(0, reserved), self.max_active - 1)
        self.active = 0
        self._waiters = []  # (priority, seq, future)
        self._seq = itertools.count()
        self.stats = {"admitted": 0, "deferred": 0, "max_queue": 0, "max_active": 0,
                      "by_class": {n: {"admitted": 0, "deferred": 0, "wait_s_total": 0.0} for n in CLASS_NAMES.values()}}

    def _limit(self, priority: int) -> int:
        return self.max_active if priority <= 2 else self.max_active - self.reserved

    def _can_run(self, priority: int) -> bool:
        return self.active < self._limit(priority)

    def snapshot(self) -> dict:
        import copy
        return {"active": self.active, "queued": len(self._waiters), "slots": self.max_active,
                "reserved_for_staff_help": self.reserved, **copy.deepcopy(self.stats)}

    async def acquire(self, priority: int, timeout: float) -> tuple:
        """(admitted, waited_seconds)."""
        t0 = time.monotonic()
        better_waiting = any(p <= priority for p, _, _ in self._waiters)
        if not better_waiting and self._can_run(priority):
            return self._admit(priority, t0)
        fut = asyncio.get_running_loop().create_future()
        entry = (priority, next(self._seq), fut)
        heapq.heappush(self._waiters, entry)
        self.stats["max_queue"] = max(self.stats["max_queue"], len(self._waiters))
        try:
            await asyncio.wait_for(asyncio.shield(fut), timeout)
            return self._admit(priority, t0, granted=True)
        except asyncio.TimeoutError:
            if fut.done() and not fut.cancelled():  # granted at the last moment
                return self._admit(priority, t0, granted=True)
            fut.cancel()
            self._waiters = [w for w in self._waiters if w[2] is not fut]
            heapq.heapify(self._waiters)
            self.stats["deferred"] += 1
            self.stats["by_class"][CLASS_NAMES[priority]]["deferred"] += 1
            return False, time.monotonic() - t0

    def _admit(self, priority, t0, granted=False):
        if not granted:
            self.active += 1
        self.stats["admitted"] += 1
        self.stats["max_active"] = max(self.stats["max_active"], self.active)
        c = self.stats["by_class"][CLASS_NAMES[priority]]
        c["admitted"] += 1
        waited = time.monotonic() - t0
        c["wait_s_total"] += waited
        return True, waited

    def release(self):
        self.active -= 1
        self._wake()

    def _wake(self):
        while self._waiters:
            prio, _, fut = self._waiters[0]
            if fut.done():
                heapq.heappop(self._waiters)
                continue
            if not self._can_run(prio):
                return
            heapq.heappop(self._waiters)
            self.active += 1  # slot handed to the waiter
            fut.set_result(True)


def from_env(env=None) -> Admission:
    env = os.environ if env is None else env
    max_active = int(env.get("CAOSCARE_VOICE_BRIDGE_MAX_ACTIVE") or 16)
    reserved = int(env.get("CAOSCARE_VOICE_BRIDGE_RESERVED") or 4)
    return Admission(max_active, reserved)


ADMISSION = from_env()
