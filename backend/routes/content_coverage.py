"""Menu and activity-schedule coverage: is anything published for today, and what is the last published
day. Read-only, staff only. Uses the same "what residents and Aria see" filters as the public reads
(menu: approved items; schedule: not draft/superseded, not staff-only rows), so an empty-looking screen
can say why instead of looking broken."""
from datetime import date as _date
from fastapi import APIRouter, Depends

from deps import db, get_current_user
from routes.realtime_facility import today_facility_date
from routes.schedule import _NOT_LIVE, _STAFF_ONLY_CATEGORIES

router = APIRouter(tags=["content-coverage"])


async def _coverage(collection, live_query: dict) -> dict:
    today = today_facility_date()
    days = sorted(await collection.distinct("date", live_query))
    last = days[-1] if days else None
    ahead = [d for d in days if d >= today]
    return {
        "today": today,
        "covers_today": today in days,
        "last_date": last,
        "days_ago": (_date.fromisoformat(today) - _date.fromisoformat(last)).days if last and last < today else 0,
        "days_ahead": len(ahead),
    }


@router.get("/menu/coverage")
async def menu_coverage(user=Depends(get_current_user)):
    return await _coverage(db.menu_items, {"status": "approved"})


@router.get("/schedule/coverage")
async def schedule_coverage(user=Depends(get_current_user)):
    return await _coverage(db.schedule_items, {"status": {"$nin": _NOT_LIVE}, "category": {"$nin": _STAFF_ONLY_CATEGORIES}})
