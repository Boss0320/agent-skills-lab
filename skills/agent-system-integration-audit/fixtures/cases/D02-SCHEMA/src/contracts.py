from __future__ import annotations

from typing import Literal, TypedDict


class ProducerReport(TypedDict):
    """Record emitted by the NorthstarMetrics collector."""

    project: str
    period: Literal["quarterly"]
    value: float

class ConsumerReport(TypedDict):
    """Record required by the NorthstarMetrics summary boundary.

    This consumer accepts only cumulative year-to-date observations.
    """

    project: str
    value: float
    period: Literal["year_to_date"]
