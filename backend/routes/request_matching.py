"""Is a new resident request the same problem as an open one?

Duplicate detection used to key on category + resident only, so "my TV
remote stopped working" was filed as a repeat of an open "my sink is
leaking" (2026-10-03 voice bridge spike). A repeat ask now joins an open
request only when it is about the same thing:

- the new words share a content word with the open request (after dropping
  filler and request words, with a crude stem), or
- the new words carry no content of their own ("can you ask them again?"):
  it re-asks the newest open request in that category (filing "ask them
  again" as a new request would give staff nothing to act on).

Otherwise the ask is a new request. Deterministic and explainable; no model.
"""
import re
from typing import Optional

_FILLER = set("""
a an the my me i im i'm it its it's is are was were be been am to of in on at for with and or but
this that these those there here please can could would will you your someone somebody anyone
anybody help need needs want wants get got have has had do does did again still also too just
now today tonight ask asked asking tell let know about some more any request requests
send come look check fix see thanks thank okay ok yes no not hi hello hey up out over so
them they he she him his her their theirs we us our ours which what when where how why
coming come going go update updates forget forgot forgotten wait waiting yet soon long anymore
""".split())
_STEM_SUFFIXES = ("ing", "ed", "es", "s")


def _stem(word: str) -> str:
    for suffix in _STEM_SUFFIXES:
        if len(word) > len(suffix) + 2 and word.endswith(suffix):
            return word[: -len(suffix)]
    return word


def content_tokens(text: Optional[str]) -> set:
    words = re.findall(r"[a-z0-9']+", (text or "").lower())
    return {_stem(w) for w in words if w not in _FILLER and len(w) > 1}


def _request_text(task: dict) -> str:
    return " ".join(filter(None, (task.get("resident_words"), task.get("title"), task.get("description"))))


def match_open_request(new_text: Optional[str], open_tasks: list) -> Optional[dict]:
    """The open request this ask repeats, or None for a new request.
    `open_tasks` are same-category open requests for the resident/room,
    newest first."""
    if not open_tasks:
        return None
    new = content_tokens(new_text)
    if not new:
        return open_tasks[0]
    for task in open_tasks:
        if new & content_tokens(_request_text(task)):
            return task
    return None
