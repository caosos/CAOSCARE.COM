"""Deterministic in-memory harness for the visible community lifecycle."""

from copy import deepcopy
from datetime import datetime, timezone

from simulation import community_run_lifecycle as lifecycle
from simulation import community_runner
from simulation.community_blueprint import COMMUNITY_ID, SIMULATION_SCOPE
from simulation.community_control_service import CommunityControlService, runner_actor
from simulation.community_execution_adapter import CanonicalCommunityExecutionServices
from simulation.community_provisioning import provision_burn_in_residents
from simulation.community_runner_timeline import DatabaseRunnerTimeline
from simulation.community_timeline import build_90_day_timeline
from tests.community_runtime_fake import Collection, Cursor, RuntimeStore, _matches, _value


NOW = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)
AUTHORITY = "admin_override:owner"
HOLDER_ID = "acceptance:living-community-loop"


def _sort(rows, spec):
    ordered = list(rows)
    for field, direction in reversed(spec or []):
        ordered.sort(key=lambda row: (_value(row, field) is not None, _value(row, field)),
                     reverse=direction < 0)
    return ordered


class AcceptanceCursor(Cursor):
    def sort(self, field, direction):
        self.documents = _sort(self.documents, [(field, direction)])
        return self


class AcceptanceCollection(Collection):
    def find(self, query, projection=None, session=None):
        self.store.check_session(session)
        return AcceptanceCursor([row for row in self.documents if _matches(row, query)])

    async def find_one(self, query, projection=None, session=None, sort=None):
        self.store.check_session(session)
        rows = _sort([row for row in self.documents if _matches(row, query)], sort)
        return deepcopy(rows[0]) if rows else None

    async def count_documents(self, query):
        return sum(_matches(row, query) for row in self.documents)


class AcceptanceStore(RuntimeStore):
    def __init__(self):
        super().__init__()
        for name in self.collection_names:
            setattr(self, name, AcceptanceCollection(self, name))


class InertLoop:
    """Control reservation without a background task; the harness ticks explicitly."""

    def __init__(self):
        self.active = False

    def start(self, _run_id, _holder_id):
        if self.active:
            return False
        self.active = True
        return True

    def wake(self, _run_id):
        return None

    async def cancel(self, _run_id):
        self.active = False
        return {"phase": "cancelled"}


class CanonicalTaskBoundary:
    """In-memory canonical task writes injected into the production adapter."""

    def __init__(self, store):
        self.store = store
        self.receipt_sequence = 0

    def _stamp(self):
        self.receipt_sequence += 1
        return f"2026-10-13T18:00:{self.receipt_sequence:02d}+00:00"

    async def write_receipt(self, **fields):
        doc = {key: value for key, value in fields.items() if key != "provenance"}
        doc.update(fields.get("provenance") or {})
        doc.setdefault("receipt_id", f"rcpt:acceptance:{self.receipt_sequence + 1:04d}")
        doc.setdefault("created_at", self._stamp())
        await self.store.receipts.insert_one(doc)
        return deepcopy(doc)

    async def create_request(self, *, event, context, summary, priority):
        task_id = f"task:{event.workflow_event_id}"
        created_at = self._stamp()
        # Same rule as the real path: a worker-raised ticket has the worker as
        # its origin actor ("task_created"); a resident's ask has the resident.
        staff = event.opened_by == "staff"
        opener = event.actor_id if staff else event.target_id
        task = {
            "task_id": task_id, "resident_id": event.target_id,
            "category": event.department, "visibility_role": event.department,
            "description": summary, "priority": priority, "status": "pending",
            "source": "staff" if staff else "simulator", "simulated": True,
            "conversation_session_id": f"simulator:event:{event.workflow_event_id}",
            "simulation_run_id": context.run_id,
            "simulation_scope": SIMULATION_SCOPE,
            "simulation_community_id": COMMUNITY_ID,
            "created_at": created_at, "event_log": [],
        }
        await self.store.staff_tasks.insert_one(task)
        receipt_id = f"rcpt:task:{task_id}:origin"
        await self.write_receipt(
            receipt_id=receipt_id, action_type="task_created" if staff else "resident_request_created",
            related_object_type="task", related_object_id=task_id,
            source="staff" if staff else "simulator", status="created", resident_id=event.target_id,
            provenance={
                "actor_id": opener, "actor_type": "simulated-agent",
                "identity_basis": "synthetic", "channel": "simulator",
                "simulated": True, "authority": "simulation_run",
                "simulation_run_id": context.run_id,
                "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID,
                "correlation_id": receipt_id, "before_state": None,
                "after_state": {"status": "pending"}, "next_state": "awaiting_claim",
            },
        )
        return {"task_id": task_id, "receipt_id": receipt_id, "status": "pending"}

    async def load_task(self, task_id):
        return await self.store.staff_tasks.find_one({"task_id": task_id})

    async def _transition(self, *, task_id, actor, status, action_type, prior_status):
        stored = next(row for row in self.store.staff_tasks.docs if row["task_id"] == task_id)
        parent = next(
            row for row in reversed(self.store.receipts.docs)
            if row.get("related_object_type") == "task"
            and row.get("related_object_id") == task_id
        )
        stamp = self._stamp()
        stored["status"] = status
        if status == "in_progress":
            stored.update(assigned_to=actor.actor_id, assigned_name=actor.name, started_at=stamp)
        else:
            stored.update(completed_at=stamp, completed_by=actor.actor_id,
                          completed_by_name=actor.name)
        receipt = await self.write_receipt(
            receipt_id=f"rcpt:task:{task_id}:{status}", action_type=action_type,
            related_object_type="task", related_object_id=task_id,
            source="simulator", status=status,
            resident_id=stored["resident_id"], assigned_user=actor.actor_id,
            provenance={
                **actor.receipt_fields(), "authority": f"acts_for:{stored['category']}",
                "simulation_run_id": stored["simulation_run_id"],
                "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID,
                "parent_receipt_id": parent["receipt_id"],
                "correlation_id": parent.get("correlation_id") or parent["receipt_id"],
                "before_state": {"status": prior_status},
                "after_state": {"status": status},
                "next_state": "closed" if status == "completed" else "in_progress",
            },
        )
        return deepcopy(stored), receipt

    async def start_task(self, *, task_id, actor, user):
        return await self._transition(
            task_id=task_id, actor=actor, status="in_progress",
            action_type="task_in_progress", prior_status="pending",
        )

    async def complete_task(self, *, task_id, note, actor, user):
        task, receipt = await self._transition(
            task_id=task_id, actor=actor, status="completed",
            action_type="task_completed", prior_status="in_progress",
        )
        task["notes"] = note
        next(row for row in self.store.staff_tasks.docs if row["task_id"] == task_id)["notes"] = note
        return task, receipt


class RealtimeAcceptanceHarness:
    def __init__(self, operator):
        self.operator = operator
        self.store = AcceptanceStore()
        self.plan = build_90_day_timeline()
        self.timeline = DatabaseRunnerTimeline(store=self.store, plan=self.plan)
        self.boundary = CanonicalTaskBoundary(self.store)
        self.services = CanonicalCommunityExecutionServices(
            store=self.store, request_creator=self.boundary.create_request,
            task_loader=self.boundary.load_task, task_starter=self.boundary.start_task,
            task_completer=self.boundary.complete_task,
            receipt_writer=self.boundary.write_receipt,
        )
        self.loop = InertLoop()

        async def ready(*, store, run):
            residents = [row for row in store.residents.docs if row.get("synthetic") is True]
            return {
                "run_id": run["run_id"], "simulation_scope": SIMULATION_SCOPE,
                "simulation_community_id": COMMUNITY_ID,
                "plan_revision": self.plan.plan_revision,
                "plan_digest_sha256": self.plan.digest_sha256,
                "cursor": run["cursor"], "sim_minute": run["sim_minute"],
                "resident_count": len(residents), "department_digest": "acceptance-exact",
            }

        self.controls = CommunityControlService(
            store=self.store, plan=self.plan, timeline=self.timeline,
            services=self.services, loop_manager=self.loop, start_guard=ready,
            clock=lambda: NOW,
        )
        self.run_id = None

    async def create_and_provision(self):
        created = await self.controls.create_paused(
            self.operator, AUTHORITY, "acceptance-create", now=NOW,
        )
        self.run_id = created["run"]["run_id"]
        await provision_burn_in_residents(
            self.operator, AUTHORITY, store=self.store,
            receipt_writer=self.boundary.write_receipt,
            simulation_run_id=self.run_id,
        )
        return created

    async def run_row(self):
        return await self.timeline.load_run(run_id=self.run_id)

    async def resume(self, key):
        row = await self.run_row()
        return await self.controls.resume_and_start(
            self.operator, AUTHORITY, self.run_id, row["cursor"], row["sim_minute"],
            key, HOLDER_ID, now=NOW,
        )

    async def pause(self, key):
        row = await self.run_row()
        return await self.controls.pause(
            self.operator, AUTHORITY, self.run_id, row["cursor"], row["sim_minute"],
            key, now=NOW,
        )

    async def tick_next(self):
        row = await self.run_row()
        event = self.plan.events[row["cursor"]]
        target = event.day_index * 1440 + event.minute
        if target > row["sim_minute"]:
            advanced = await lifecycle.advance_simulated_clock(
                runner_actor(), f"simulation_run:{self.run_id}:clock", self.run_id,
                row["cursor"], row["sim_minute"], target,
                f"acceptance-clock:{row['cursor']}:{target}", self.plan,
                store=self.store, now=NOW,
            )
            row = advanced["run"]
        return await community_runner.tick(
            self.run_id, HOLDER_ID, store=self.store, timeline=self.timeline,
            services=self.services, now=NOW, clock=lambda: NOW,
        )

    async def stop(self, key):
        row = await self.run_row()
        return await self.controls.stop(
            self.operator, AUTHORITY, self.run_id, row["state"], row["cursor"],
            row["sim_minute"], key, now=NOW,
        )
