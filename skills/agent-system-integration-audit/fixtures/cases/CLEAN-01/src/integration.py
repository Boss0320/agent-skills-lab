from __future__ import annotations

from src.component import MockTicketAdapter, ProductionTicketAdapter
from src.contracts import TicketAdapter, TicketSummary


CONFIG_KEYS = {"adapter", "coordinator", "required_fields"}
REQUIRED_FIELDS = tuple(TicketSummary.__annotations__)


class TicketCoordinator:
    def __init__(self, adapter: TicketAdapter) -> None:
        self._adapter = adapter
        self._required_fields = frozenset(REQUIRED_FIELDS)

    def summarize(self, ticket_id: str) -> TicketSummary:
        summary = self._adapter.fetch(ticket_id)
        if set(summary) != self._required_fields:
            raise ValueError("adapter record does not match required_fields")
        return summary


def build_coordinator(config: dict[str, object]) -> TicketCoordinator:
    if not isinstance(config, dict) or set(config) != CONFIG_KEYS:
        raise ValueError("config keys must be exact")
    if config["coordinator"] != "ticket_summary":
        raise ValueError("unknown coordinator")
    required_fields = config["required_fields"]
    if not isinstance(required_fields, list) or tuple(required_fields) != REQUIRED_FIELDS:
        raise ValueError("required_fields must match TicketSummary")
    adapter_name = config.get("adapter")
    if adapter_name == "production":
        adapter: TicketAdapter = ProductionTicketAdapter()
    elif adapter_name == "mock":
        adapter = MockTicketAdapter()
    else:
        raise ValueError(f"unknown adapter: {adapter_name}")
    return TicketCoordinator(adapter)
