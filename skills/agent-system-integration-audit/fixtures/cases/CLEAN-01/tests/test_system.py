from __future__ import annotations

import json
from pathlib import Path
import unittest

from src.component import MockTicketAdapter, ProductionTicketAdapter
from src.integration import TicketCoordinator, build_coordinator


class JuniperTicketsSystemTests(unittest.TestCase):
    def test_both_configured_adapter_shapes_reach_the_coordinator(self) -> None:
        for adapter in (ProductionTicketAdapter(), MockTicketAdapter()):
            summary = TicketCoordinator(adapter).summarize("JT-100")
            self.assertEqual(summary, {"ticket_id": "JT-100", "status": "open", "owner": "cedar"})

    def test_system_config_selects_the_declared_adapter(self) -> None:
        config = json.loads(Path("config/system.json").read_text(encoding="utf-8"))
        summary = build_coordinator(config).summarize("JT-100")
        self.assertEqual(set(summary), set(config["required_fields"]))

    def test_unknown_coordinator_fails_closed(self) -> None:
        config = json.loads(Path("config/system.json").read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            build_coordinator(config | {"coordinator": "unknown"})

    def test_incompatible_required_fields_fail_closed(self) -> None:
        config = json.loads(Path("config/system.json").read_text(encoding="utf-8"))
        with self.assertRaises(ValueError):
            build_coordinator(config | {"required_fields": ["missing_field"]})

    def test_coordinator_rejects_an_incomplete_adapter_record(self) -> None:
        class IncompleteAdapter:
            def fetch(self, ticket_id: str) -> dict[str, str]:
                return {"ticket_id": ticket_id, "status": "open"}

        with self.assertRaises(ValueError):
            TicketCoordinator(IncompleteAdapter()).summarize("JT-100")

    def test_coordinator_rejects_an_extra_field_adapter_record(self) -> None:
        class ExtraFieldAdapter:
            def fetch(self, ticket_id: str) -> dict[str, str]:
                return {"ticket_id": ticket_id, "status": "open", "owner": "cedar", "debug": "on"}

        with self.assertRaises(ValueError):
            TicketCoordinator(ExtraFieldAdapter()).summarize("JT-100")

    def test_coordinator_constructor_cannot_weaken_required_fields(self) -> None:
        class IncompleteAdapter:
            def fetch(self, ticket_id: str) -> dict[str, str]:
                return {"ticket_id": ticket_id, "status": "open"}

        with self.assertRaises(TypeError):
            TicketCoordinator(IncompleteAdapter(), ("ticket_id", "status"))


if __name__ == "__main__":
    unittest.main()
