"""Settings > Documents: the curated CAOSCare project documents, read-only.

GET /documents            catalog for the signed-in owner/admin: name, category,
                          description, revision (last commit touching the file)
GET /documents/{doc_id}   the document text (Markdown)

Only files listed in CATALOG can be read (no path from the request is ever
opened), only by owner/admin, and owner-only entries only by the owner.
Reading changes nothing, so it writes no receipt.
"""
import subprocess
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from deps import require_admin

router = APIRouter(prefix="/documents", tags=["documents"])
REPO = Path(__file__).resolve().parents[2]
OWNER = ("owner",)

CATEGORIES = [
    ("architecture", "Blueprint and architecture"),
    ("product", "Product specifications"),
    ("procedures", "Operating procedures"),
    ("hardware", "Hardware and installation guides"),
    ("simulator", "Simulator documentation"),
    ("plans", "Project plans and reports"),
]


def _doc(doc_id, path, title, category, description, roles=("owner", "admin")):
    return {"id": doc_id, "path": path, "title": title, "category": category,
            "description": description, "roles": roles}


CATALOG = [
    _doc("product-baseline", "docs/CAOSCARE_PRODUCT_BASELINE.md", "Product baseline", "architecture",
         "Canonical durable product truth: room architecture, staff clients, invariants."),
    _doc("blueprint", "docs/CAOSCARE_BLUEPRINT.md", "CAOSCare blueprint", "architecture",
         "System architecture (placeholder until written with Michael).", OWNER),
    _doc("engineering-contract", "docs/ENGINEERING_CONTRACT.md", "Engineering contract", "architecture",
         "Ratified service-layer decisions: one canonical layer, actor context, receipts, simulator gate."),
    _doc("repo-map", "docs/REPO_MAP.md", "Repository map", "architecture", "Where each part of the implementation lives."),
    _doc("room-audio", "docs/ROOM_AUDIO_ARCHITECTURE.md", "Room audio architecture", "architecture",
         "Room voice endpoint (Voice PE), audio path and echo-cancellation reasoning."),
    _doc("wake-word", "docs/ARIA_WAKE_WORD_ARCHITECTURE.md", "Wake word architecture", "architecture",
         "Local wake detection: status, decisions and evidence."),
    _doc("trust-layer", "docs/CCE_LITE_TRUST_LAYER_PROPOSAL.md", "Trust layer proposal (CCE-lite)", "architecture",
         "Intent, risk gate, verifier and receipts for sensitive outputs (proposal)."),
    _doc("facility-ops", "docs/CAOSCARE_FACILITY_OPERATIONS_CONTRACT.md", "Facility operations contract", "product",
         "How departments, requests and staff work together."),
    _doc("privacy-north-star", "docs/CAOSCARE_PRIVACY_SAFETY_SECURITY_NORTH_STAR.md", "Privacy, safety and security",
         "product", "North-star rules for resident privacy, safety and security."),
    _doc("aria-contract", "docs/ARIA_CONTRACT.md", "Aria contract", "product", "Who Aria is (placeholder until written)."),
    _doc("public-onboarding", "docs/PUBLIC_ONBOARDING_PACKAGE.md", "Public onboarding package", "product",
         "Audience paths, feature inventory and the public demo."),
    _doc("room-builder", "docs/ROOM_BUILDER_DESIGN.md", "Room builder design", "product",
         "Public room-experience builder design."),
    _doc("deployment", "docs/DEPLOYMENT_RUNBOOK.md", "Deployment runbook", "procedures", "Server deployment path."),
    _doc("test-gate", "docs/BACKEND_TEST_GATE.md", "Backend test gate", "procedures", "The canonical backend test command."),
    _doc("room-page-rebuild", "docs/ROOM_PAGE_REBUILD_RUNBOOK.md", "Room page rebuild", "procedures",
         "Rebuilding and reloading the room screen."),
    _doc("communications", "docs/PILOT1_COMMUNICATIONS.md", "Communications setup", "procedures",
         "Email, SMS and phone setup and acceptance tests."),
    _doc("demo-kit", "docs/CAOSCARE_DEMO_KIT_AND_SELF_INSTALL_RUNBOOK.md", "Demo kit and self-install", "procedures",
         "Demo kit contents and self-install steps."),
    _doc("ha-vm-recovery", "docs/HA_VM_RECOVERY.md", "Home Assistant VM recovery", "procedures",
         "Recovering the Home Assistant virtual machine."),
    _doc("room1-hardware", "docs/PILOT1_ROOM1_HARDWARE_INVENTORY.md", "Pilot room hardware", "hardware",
         "Pilot room bill of materials: owned, ordered, required."),
    _doc("elitedesk-build", "docs/ELITEDESK_NODE_BUILD.md", "EliteDesk server build", "hardware",
         "Building the central community server."),
    _doc("ir-mate", "room-node/ir_mate/README.md", "IR Mate (TV control puck)", "hardware",
         "Infrared TV control: setup, touch behaviour and acceptance."),
    _doc("hearing", "docs/PILOT_HEARING_AUDIO_REQUIREMENTS.md", "Hearing and handset requirements", "hardware",
         "Pilot room hearing and handset procurement and tests."),
    _doc("tablet-bridge", "docs/CAOSCARE_TABLET_BRIDGE_SETUP_RUNBOOK.md", "RF bridge setup", "hardware",
         "Pendant RF receiver setup."),
    _doc("simulator", "docs/CAOSCARE_OPERATIONS_SIMULATOR.md", "Operations simulator", "simulator",
         "Receipt-backed simulated community: rules and acceptance."),
    _doc("mongo-acceptance", "docs/LIVING_COMMUNITY_MONGO_ACCEPTANCE.md", "Simulator database acceptance", "simulator",
         "Real-MongoDB acceptance procedure for the living community."),
    _doc("project-state", "docs/PROJECT_STATE.md", "Project state log", "plans", "Dated build log and handoffs.", OWNER),
    _doc("pilot-checklist", "docs/PILOT1_EXECUTION_CHECKLIST.md", "Pilot 1 checklist", "plans", "Pilot 1 phases and status."),
    _doc("current-priority", "docs/CURRENT_PRIORITY.md", "Current priority", "plans", "What is being worked on now."),
    _doc("design-migration", "docs/reports/2026-10-14-design-migration-map.md", "Design migration map", "plans",
         "Every staff page and its move into the new design."),
    _doc("decision-packets", "docs/MICHAEL_DECISION_PACKETS.md", "Owner decision packets", "plans",
         "Decisions waiting for the owner.", OWNER),
]
BY_ID = {d["id"]: d for d in CATALOG}


@lru_cache(maxsize=256)
def _revision(path: str, mtime: float) -> dict:
    """Last commit touching the file; mtime keys the cache to file changes."""
    try:
        out = subprocess.run(["git", "-C", str(REPO), "log", "-1", "--format=%h|%cs|%s", "--", path],
                             capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        out = ""
    if not out:
        return {"commit": None, "date": None, "subject": None}
    commit, date, subject = out.split("|", 2)
    return {"commit": commit, "date": date, "subject": subject[:120]}


def _visible(doc, user) -> bool:
    return user.get("role") in doc["roles"]


@router.get("")
async def list_documents(user=Depends(require_admin)):
    out = []
    for d in CATALOG:
        if not _visible(d, user):
            continue
        f = REPO / d["path"]
        exists = f.is_file()
        out.append({**{k: d[k] for k in ("id", "title", "category", "description", "path")},
                    "owner_only": d["roles"] == OWNER, "available": exists,
                    "revision": _revision(d["path"], f.stat().st_mtime) if exists else None})
    return {"categories": [{"id": c, "label": label} for c, label in CATEGORIES], "documents": out}


@router.get("/{doc_id}")
async def read_document(doc_id: str, user=Depends(require_admin)):
    d = BY_ID.get(doc_id)
    if not d or not _visible(d, user):
        raise HTTPException(404, "Document not found")
    f = REPO / d["path"]
    if not f.is_file():
        raise HTTPException(404, "Document file is not present in this installation")
    return {"id": d["id"], "title": d["title"], "path": d["path"],
            "revision": _revision(d["path"], f.stat().st_mtime), "text": f.read_text(encoding="utf-8")[:400_000]}
