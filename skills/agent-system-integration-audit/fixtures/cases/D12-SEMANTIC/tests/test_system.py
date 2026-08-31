from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.component import normalized_observation
from src.integration import load_rule


class MeridianLimitsComponentTests(unittest.TestCase):
    def test_component_normalizes_drawdown_to_ratio(self) -> None:
        self.assertEqual(
            normalized_observation("ACCT-7"),
            {"account_id": "ACCT-7", "drawdown": 0.075, "drawdown_basis": "ratio"},
        )

    def test_configuration_loads_percent_threshold(self) -> None:
        config = json.loads(Path("config/system.json").read_text(encoding="utf-8"))
        self.assertEqual(load_rule(config), {"threshold": 5.0, "threshold_basis": "percent"})


if __name__ == "__main__":
    unittest.main()
