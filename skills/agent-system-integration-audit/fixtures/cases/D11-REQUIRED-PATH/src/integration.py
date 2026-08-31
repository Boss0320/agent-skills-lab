from __future__ import annotations

from src.component import AuditSink, PolicyGate
from src.contracts import DispatchRequest, DispatchResult


def run_required_path(
    request: DispatchRequest,
    gate: PolicyGate,
    audit_sink: AuditSink,
) -> DispatchResult:
    decision = gate.evaluate(request)
    if decision != "allow":
        return {"status": "denied", "request_id": request["request_id"]}
    return {"status": "accepted", "request_id": request["request_id"]}
