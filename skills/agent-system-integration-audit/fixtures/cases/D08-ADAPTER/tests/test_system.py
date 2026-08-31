from __future__ import annotations

import unittest

from src.component import MockWeatherAdapter, ProductionWeatherAdapter


class HarborWeatherComponentTests(unittest.TestCase):
    def test_production_adapter_supplies_a_timestamp(self) -> None:
        observation = ProductionWeatherAdapter().fetch("HBR-1")
        self.assertIn("observed_at", observation)

    def test_mock_adapter_uses_the_fixed_temperature(self) -> None:
        observation = MockWeatherAdapter().fetch("HBR-1")
        self.assertEqual(observation["temperature_c"], 19.5)


if __name__ == "__main__":
    unittest.main()
