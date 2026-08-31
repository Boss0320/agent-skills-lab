from __future__ import annotations

from src.contracts import TicketSummary


class ProductionTicketAdapter:
    def fetch(self, ticket_id: str) -> TicketSummary:
        return {"ticket_id": ticket_id, "status": "open", "owner": "cedar"}


class MockTicketAdapter:
    def fetch(self, ticket_id: str) -> TicketSummary:
        return {"ticket_id": ticket_id, "status": "open", "owner": "cedar"}
