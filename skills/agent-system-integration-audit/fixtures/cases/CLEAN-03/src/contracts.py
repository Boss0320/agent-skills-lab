from __future__ import annotations

from typing import Literal, TypedDict


class QuoteResult(TypedDict):
    status: Literal["normal", "degraded"]
    source: Literal["primary", "cache"]
    value: float
    observed_at: str
