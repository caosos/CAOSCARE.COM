#!/usr/bin/env python3
"""Operator CLI for read-only Mongo checks or isolated simulator acceptance."""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            "Read Mongo topology and transaction support without writes by default. "
            "Scratch acceptance is separately and explicitly gated."
        )
    )
    result.add_argument(
        "--database",
        help="database used for the read-only transaction probe (default: DB_NAME)",
    )
    result.add_argument(
        "--scratch-db",
        help="fresh database named caoscare_sim_acceptance_<8-32 lowercase letters/digits>",
    )
    result.add_argument(
        "--production-db",
        help="production database name to refuse (default: original DB_NAME or caoscare)",
    )
    result.add_argument(
        "--cohort", choices=("community_75", "burn_in_10"), default=None,
        help="resident cohort for scratch acceptance (default: full 75-resident community)",
    )
    result.add_argument(
        "--confirm-scratch-mutations",
        action="store_true",
        help="explicitly authorize writes and exact scoped reset in --scratch-db only",
    )
    result.add_argument("--operator-id", help="receipt actor ID; required for scratch acceptance")
    result.add_argument("--operator-name", help="optional receipt actor display name")
    return result


async def _run(args) -> dict:
    from simulation.community_mongo_probe import (
        CommunityMongoAcceptanceError,
        probe_mongo,
        validate_scratch_database,
    )

    original_db = os.environ.get("DB_NAME", "").strip()
    production_dbs = tuple(
        value for value in (original_db, args.production_db, "caoscare") if value
    )
    if args.scratch_db:
        if args.database:
            raise CommunityMongoAcceptanceError(
                "--database and --scratch-db cannot be used together"
            )
        scratch = validate_scratch_database(
            args.scratch_db,
            production_db=production_dbs,
            confirmed=args.confirm_scratch_mutations,
        )
        if not args.operator_id:
            raise CommunityMongoAcceptanceError(
                "scratch acceptance requires --operator-id for receipt provenance"
            )
        os.environ["DB_NAME"] = scratch
        from deps import db
        from routes.departments import seed_default_departments
        from simulation.community_mongo_acceptance import run_scratch_acceptance

        reopened_clients = []

        def reopen():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            reopened_clients.append(client)
            return client[scratch]

        try:
            return await run_scratch_acceptance(
                db,
                database_name=scratch,
                production_databases=production_dbs,
                confirmed=args.confirm_scratch_mutations,
                operator_id=args.operator_id,
                operator_name=args.operator_name,
                reopen_store=reopen,
                seed_catalog=seed_default_departments,
                cohort=args.cohort,
            )
        finally:
            for client in reopened_clients:
                client.close()

    if args.confirm_scratch_mutations or args.operator_id or args.operator_name:
        raise CommunityMongoAcceptanceError(
            "mutation options require an explicit --scratch-db"
        )
    selected = args.database or original_db
    if not selected:
        raise CommunityMongoAcceptanceError("read-only probe requires --database or DB_NAME")
    os.environ["DB_NAME"] = selected
    from deps import db

    probe = await probe_mongo(db)
    return {
        "status": probe["status"], "mode": "read_only",
        "database": selected, "probe": probe,
    }


def main(argv=None) -> int:
    load_dotenv(BACKEND_DIR / ".env")
    args = parser().parse_args(argv)
    if not os.environ.get("MONGO_URL", "").strip():
        print("Mongo acceptance failed: MONGO_URL is not configured", file=sys.stderr)
        return 2
    try:
        result = asyncio.run(_run(args))
    except Exception as exc:
        from simulation.community_mongo_probe import CommunityMongoAcceptanceError

        if isinstance(exc, CommunityMongoAcceptanceError):
            message = str(exc)
        else:
            message = f"unexpected {type(exc).__name__}; connection details suppressed"
        print(f"Mongo acceptance failed: {message}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
