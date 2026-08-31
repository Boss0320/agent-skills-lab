from __future__ import annotations

import unittest

from src.component import DecisionRenderer, SignalProducer
from src.integration import render_decision


class IsolatedComponentTests(unittest.TestCase):
    def test_producer_builds_the_declared_record(self) -> None:
        record = SignalProducer().build("hold", 0.8, "inventory is constrained")
        self.assertEqual("inventory is constrained", record["decision_basis"])

    def test_renderer_accepts_a_complete_public_signal(self) -> None:
        rendered = DecisionRenderer().render(
            {
                "signal": "hold",
                "confidence": 0.8,
                "decision_basis": "inventory is constrained",
            }
        )
        self.assertIn("inventory is constrained", rendered)


class RequiredPathTests(unittest.TestCase):
    def test_required_route_preserves_the_decision_basis(self) -> None:
        rendered = render_decision("hold", 0.8, "inventory is constrained")
        self.assertIn("inventory is constrained", rendered)


if __name__ == "__main__":
    unittest.main()
