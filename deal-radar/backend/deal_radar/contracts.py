"""Cross-lane contracts.

Keep this module deliberately small. Agent lanes may implement internals independently,
but pipeline boundaries must remain compatible with these contracts.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class Decision(StrEnum):
    BUY = "BUY"
    WATCH = "WATCH"
    PASS = "PASS"


class SourceResult(BaseModel):
    source: str
    source_listing_id: str
    canonical_url: HttpUrl
    fetched_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
    parsed: dict[str, Any] = Field(default_factory=dict)


class MoneyRange(BaseModel):
    low: float = Field(ge=0)
    median: float = Field(ge=0)
    high: float = Field(ge=0)


class ValuationInputs(BaseModel):
    purchase_cost: float = Field(ge=0)
    buyer_premium: float = Field(default=0, ge=0)
    tax: float = Field(default=0, ge=0)
    shipping: float = Field(default=0, ge=0)
    travel_cost: float = Field(default=0, ge=0)
    repair: MoneyRange
    cleanup: float = Field(default=0, ge=0)
    disposal: float = Field(default=0, ge=0)
    contingency: float = Field(default=0, ge=0)


class DealScore(BaseModel):
    decision: Decision
    score: float
    expected_profit: MoneyRange
    cash_multiple: float | None = None
    confidence: float = Field(ge=0, le=1)
    max_offer: float | None = Field(default=None, ge=0)
    blockers: list[str] = Field(default_factory=list)
    questions_to_ask_seller: list[str] = Field(default_factory=list)
    receipt_id: str
