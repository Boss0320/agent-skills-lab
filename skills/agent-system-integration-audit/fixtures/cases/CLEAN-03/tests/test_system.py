from __future__ import annotations

import unittest

from src.component import CachedQuoteSource
from src.integration import load_quote


class IsolatedComponentTests(unittest.TestCase):
    def test_cache_labels_its_result_as_degraded(self) -> None:
        result = CachedQuoteSource().fetch()
        self.assertEqual("degraded", result["status"])
        self.assertEqual("cache", result["source"])


class RequiredPathTests(unittest.TestCase):
    def test_unavailable_primary_returns_a_typed_degraded_result(self) -> None:
        result = load_quote()
        self.assertEqual(
            {"status", "source", "value", "observed_at"},
            set(result),
        )
        self.assertEqual("degraded", result["status"])
        self.assertEqual("cache", result["source"])


if __name__ == "__main__":
    unittest.main()
