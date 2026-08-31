from __future__ import annotations

import unittest

from src.component import build_report


class NorthstarMetricsComponentTests(unittest.TestCase):
    def test_collector_emits_declared_quarterly_record(self) -> None:
        report = build_report("aurora")
        self.assertEqual(report, {"project": "aurora", "period": "quarterly", "value": 42.0})


if __name__ == "__main__":
    unittest.main()
