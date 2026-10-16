"""Application-owned singleton for living-community process composition."""

import logging
import os
from uuid import uuid4

from simulation.community_process_runtime import CommunityProcessRuntime


_runtime = None
_store = None
_process_id = f"{os.getpid()}:{uuid4().hex}"
_holder_id = f"community-process:{_process_id}"


def community_process_holder_id() -> str:
    return _holder_id


def community_process_runtime(store) -> CommunityProcessRuntime:
    global _runtime, _store
    if _runtime is None:
        _runtime = CommunityProcessRuntime(
            store=store, process_id=_process_id, holder_id=_holder_id,
        )
        _store = store
    elif store is not _store:
        raise RuntimeError("living-community process runtime is already bound")
    return _runtime


async def recover_community_on_startup(store):
    """Fail closed without preventing the rest of CAOSCare from starting."""
    try:
        result = await community_process_runtime(store).recover_startup()
        if result.status not in {"disabled", "no_running_run"}:
            logging.info("living-community startup recovery: %s", result)
        return result
    except Exception:
        logging.exception("living-community startup recovery refused")
        return None


async def stop_community_on_shutdown(store):
    try:
        return await community_process_runtime(store).shutdown()
    except Exception:
        logging.exception("living-community loop shutdown failed")
        return ()
