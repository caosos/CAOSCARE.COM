"""Content-aware duplicate lookup for resident requests (RQ-032 / D2).
Split out of resident_requests.py. Same department + same resident/room is
not enough: the open request must also be clearly the same issue
(request_similarity.py). Nothing here writes."""
from typing import Optional

from deps import db
from request_similarity import best_match, content_words


async def find_same_issue(dup_q: Optional[dict], summary: str, resident_words: Optional[str]) -> Optional[dict]:
    """The open request (already narrowed by `dup_q`: category, resident or
    room, run scope) that is clearly the same issue as the new wording, or
    None when it is a different issue and needs its own request."""
    if not dup_q:
        return None
    candidates = await db.staff_tasks.find(dup_q, {"_id": 0}).sort("created_at", -1).to_list(30)
    return best_match(content_words(summary, resident_words), candidates)
