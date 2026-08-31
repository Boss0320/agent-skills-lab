from __future__ import annotations

from src.contracts import PublicSignal, SignalRecord


class SignalProducer:
    def build(self, signal: str, confidence: float, basis: str) -> SignalRecord:
        return {
            "signal": signal,
            "confidence": confidence,
            "decision_basis": basis,
        }


class DecisionRenderer:
    def render(self, record: PublicSignal) -> str:
        return f"{record['signal']} because {record['decision_basis']}"
