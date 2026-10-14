"""Mongo-like async test boundary for living-community runtime acceptance.

This is deliberately an in-memory test double, not direct MongoDB evidence.
It implements only the collection/session operations used by provisioning,
the fenced executor/lease, and transactional community reset.
"""
from copy import deepcopy


def _value(document, path):
    value = document
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _matches(document, query):
    for key, expected in query.items():
        if key == "$or":
            if not any(_matches(document, option) for option in expected):
                return False
            continue
        actual = _value(document, key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$exists" in expected and (actual is not None) != expected["$exists"]:
                return False
            if "$lte" in expected and not (actual is not None and actual <= expected["$lte"]):
                return False
            if "$gt" in expected and not (actual is not None and actual > expected["$gt"]):
                return False
        elif actual != expected:
            return False
    return True


def _set(document, path, value):
    target = document
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = deepcopy(value)


def _unset(document, path):
    target = document
    parts = path.split(".")
    for part in parts[:-1]:
        target = target.get(part, {})
    target.pop(parts[-1], None)


class Cursor:
    def __init__(self, documents):
        self.documents = documents

    async def to_list(self, limit):
        selected = self.documents if limit is None else self.documents[:limit]
        return deepcopy(selected)


class DeleteResult:
    def __init__(self, count):
        self.deleted_count = count


class Collection:
    def __init__(self, store, name, documents=None):
        self.store = store
        self.name = name
        self.documents = [deepcopy(row) for row in (documents or [])]

    @property
    def docs(self):
        return self.documents

    def find(self, query, projection=None, session=None):
        self.store.check_session(session)
        return Cursor([row for row in self.documents if _matches(row, query)])

    async def find_one(self, query, projection=None, session=None):
        self.store.check_session(session)
        return next(
            (deepcopy(row) for row in self.documents if _matches(row, query)),
            None,
        )

    async def insert_one(self, document, session=None):
        self.store.check_session(session)
        self.documents.append(deepcopy(document))
        return object()

    async def delete_many(self, query, session=None):
        self.store.check_session(session)
        kept = [row for row in self.documents if not _matches(row, query)]
        count = len(self.documents) - len(kept)
        self.documents = kept
        if self.store.fail_delete == self.name:
            raise RuntimeError("injected transactional delete failure")
        return DeleteResult(count)

    async def find_one_and_update(
        self, query, update, projection=None, return_document=None, session=None,
    ):
        self.store.check_session(session)
        for row in self.documents:
            if not _matches(row, query):
                continue
            for path, amount in update.get("$inc", {}).items():
                _set(row, path, (_value(row, path) or 0) + amount)
            for path, value in update.get("$set", {}).items():
                _set(row, path, value)
            for path in update.get("$unset", {}):
                _unset(row, path)
            return deepcopy(row)
        return None


class Transaction:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, _exc, _traceback):
        if exc_type:
            await self.session.abort_transaction()
        else:
            await self.session.commit_transaction()
        return False


class Session:
    def __init__(self, store):
        self.store = store
        self.in_transaction = False
        self.snapshot = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, _exc_type, _exc, _traceback):
        if self.in_transaction:
            await self.abort_transaction()
        return False

    def start_transaction(self):
        if self.in_transaction:
            raise RuntimeError("transaction already active")
        self.in_transaction = True
        self.snapshot = self.store.snapshot()
        return Transaction(self)

    async def commit_transaction(self):
        if not self.in_transaction:
            raise RuntimeError("no active transaction")
        self.in_transaction = False
        self.snapshot = None

    async def abort_transaction(self):
        if not self.in_transaction:
            raise RuntimeError("no active transaction")
        self.store.restore(self.snapshot)
        self.in_transaction = False
        self.snapshot = None


class Client:
    def __init__(self, store):
        self.store = store

    async def start_session(self):
        return self.store.session


class RuntimeStore:
    def __bool__(self):
        # Real pymongo/Motor Database objects refuse truth testing (SIM-003).
        raise NotImplementedError("Database objects do not implement truth value testing")

    collection_names = (
        "residents", "users", "receipts", "staff_tasks", "notifications", "sim_runs",
        "sim_shift_covers",
    )

    def __init__(self, *, fail_delete=None):
        self.fail_delete = fail_delete
        self.session = Session(self)
        self.client = Client(self)
        for name in self.collection_names:
            setattr(self, name, Collection(self, name))

    def check_session(self, session):
        if session is not None and session is not self.session:
            raise AssertionError("unknown in-memory session")
        if session is not None and not session.in_transaction:
            raise AssertionError("session write/read must be inside the transaction")

    def snapshot(self):
        return {
            name: deepcopy(getattr(self, name).documents)
            for name in self.collection_names
        }

    def restore(self, snapshot):
        for name, documents in snapshot.items():
            getattr(self, name).documents = deepcopy(documents)
