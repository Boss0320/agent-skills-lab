from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.component import normalized_observation
from src.integration import evaluate_account, load_rule


class WillowLimitsSystemTests(unittest.TestCase):
    def test_component_and_policy_keep_their_declared_bases(self) -> None:
        self.assertEqual(
            normalized_observation("ACCT-7"),
            {"account_id": "ACCT-7", "drawdown": 0.075, "drawdown_basis": "ratio"},
        )
        config = json.loads(Path("config/system.json").read_text(encoding="utf-8"))
        self.assertEqual(load_rule(config), {"threshold": 5.0, "threshold_basis": "percent"})

    def test_evaluator_applies_percent_threshold_to_ratio_observation(self) -> None:
        self.assertEqual(evaluate_account("ACCT-7"), "BLOCK")


if __name__ == "__main__":
    unittest.main()
