from __future__ import annotations

import unittest

from src.component import AuditSink, PolicyGate
from src.integration import run_required_path


class IsolatedComponentTests(unittest.TestCase):
    def test_gate_allows_an_approved_request(self) -> None:
        self.assertEqual("allow", PolicyGate().evaluate({"request_id": "R-1", "approved": True}))

    def test_audit_sink_records_an_event(self) -> None:
        sink = AuditSink()
        sink.record("R-1", "accepted")
        self.assertEqual([{"request_id": "R-1", "outcome": "accepted"}], sink.events)


class RequiredPathTests(unittest.TestCase):
    def test_accepted_request_records_the_required_audit_event(self) -> None:
        sink = AuditSink()
        result = run_required_path(
            {"request_id": "R-1", "approved": True},
            PolicyGate(),
            sink,
        )
        self.assertEqual("accepted", result["status"])
        self.assertEqual(
            [{"request_id": "R-1", "outcome": "accepted"}],
            sink.events,
            "approval audit event missing",
        )


if __name__ == "__main__":
    unittest.main()
