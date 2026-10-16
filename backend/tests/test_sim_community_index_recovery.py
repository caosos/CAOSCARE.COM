"""Crash, ambiguity, and replay proof for simulator index preparation."""

import pytest

from simulation.community_index_contract import REQUIRED_INDEXES
from simulation.community_index_evidence import FAILED, RECONCILED, REQUESTED
from simulation.community_index_preparation import (
    IndexPreparationError, prepare_required_indexes,
)
from tests.test_sim_community_index_preparation import (
    AUTHORITY, NOW, OWNER, Store, _actions, _install_all, _run,
)


def test_ambiguous_create_error_reconciles_only_after_exact_reinspection():
    store = Store()
    missing = REQUIRED_INDEXES[-1]
    _install_all(store, except_name=missing["name"])
    getattr(store, missing["collection"]).fail_create[missing["name"]] = "committed"
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "ambiguous-create", store=store, now=NOW,
    ))
    assert result["status"] == "ready"
    assert result["action_type"] == RECONCILED
    assert _actions(store) == [REQUESTED, RECONCILED]


def test_crash_after_index_commit_requires_explicit_recovery_then_reconciles():
    store = Store()
    missing = REQUIRED_INDEXES[-1]
    _install_all(store, except_name=missing["name"])
    getattr(store, missing["collection"]).crash_create.add(missing["name"])
    with pytest.raises(KeyboardInterrupt, match="injected crash"):
        _run(prepare_required_indexes(
            OWNER, AUTHORITY, "crash-recovery", store=store, now=NOW,
        ))
    assert _actions(store) == [REQUESTED]
    with pytest.raises(IndexPreparationError, match="explicit recovery"):
        _run(prepare_required_indexes(
            OWNER, AUTHORITY, "crash-recovery", store=store, now=NOW,
        ))
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "crash-recovery", store=store, now=NOW,
        recover_interrupted=True,
    ))
    assert result["action_type"] == RECONCILED
    assert _actions(store) == [REQUESTED, RECONCILED]


def test_recovery_can_finish_partial_build_and_marks_reconciled():
    store = Store()
    first_missing = REQUIRED_INDEXES[0]
    second_missing = REQUIRED_INDEXES[1]
    _install_all(store)
    getattr(store, first_missing["collection"]).indexes.pop(first_missing["name"])
    getattr(store, second_missing["collection"]).indexes.pop(second_missing["name"])
    getattr(store, first_missing["collection"]).crash_create.add(first_missing["name"])
    with pytest.raises(KeyboardInterrupt):
        _run(prepare_required_indexes(
            OWNER, AUTHORITY, "partial-recovery", store=store, now=NOW,
        ))
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "partial-recovery", store=store, now=NOW,
        recover_interrupted=True,
    ))
    assert result["action_type"] == RECONCILED
    assert second_missing["name"] in result["created_indexes"]


def test_outcome_receipt_write_failure_recovers_from_index_information():
    store = Store()
    original_insert = store.receipts.insert_one
    count = 0

    async def fail_second(row, session=None):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("outcome write unavailable")
        return await original_insert(row, session=session)

    store.receipts.insert_one = fail_second
    with pytest.raises(IndexPreparationError, match="outcome evidence"):
        _run(prepare_required_indexes(
            OWNER, AUTHORITY, "receipt-crash", store=store, now=NOW,
        ))
    assert _actions(store) == [REQUESTED]
    result = _run(prepare_required_indexes(
        OWNER, AUTHORITY, "receipt-crash", store=store, now=NOW,
        recover_interrupted=True,
    ))
    assert result["action_type"] == RECONCILED


def test_completed_and_failed_results_are_idempotent_without_more_ddl():
    for fail in (False, True):
        store = Store()
        if fail:
            store.sim_runs.indexes[REQUIRED_INDEXES[0]["name"]] = {
                "key": [("wrong", 1)], "unique": True,
            }
        key = f"replay-{fail}"
        first = _run(prepare_required_indexes(
            OWNER, AUTHORITY, key, store=store, now=NOW,
        ))
        create_count = sum(call[0] == "create" for collection in (
            store.sim_runs, store.receipts, store.staff_tasks
        ) for call in collection.calls)
        second = _run(prepare_required_indexes(
            OWNER, AUTHORITY, key, store=store, now=NOW,
        ))
        assert second["receipt_id"] == first["receipt_id"]
        assert second["idempotent_replay"] is True
        assert second["action_type"] in {FAILED, first["action_type"]}
        assert sum(call[0] == "create" for collection in (
            store.sim_runs, store.receipts, store.staff_tasks
        ) for call in collection.calls) == create_count
