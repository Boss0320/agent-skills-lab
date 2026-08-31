from __future__ import annotations

from src.contracts import DispatchRequest


class PolicyGate:
    def evaluate(self, request: DispatchRequest) -> str:
        return "allow" if request["approved"] else "deny"


class AuditSink:
    def __init__(self) -> None:
        self.events: list[dict[str, str]] = []

    def record(self, request_id: str, outcome: str) -> None:
        self.events.append({"request_id": request_id, "outcome": outcome})
