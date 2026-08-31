from __future__ import annotations

from typing import TypedDict


class SignalRecord(TypedDict):
    signal: str
    confidence: float
    decision_basis: str


class PublicSignal(TypedDict):
    signal: str
    confidence: float
    decision_basis: str
