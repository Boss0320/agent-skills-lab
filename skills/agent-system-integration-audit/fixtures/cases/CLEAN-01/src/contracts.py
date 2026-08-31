from __future__ import annotations

from typing import Protocol, TypedDict


class TicketSummary(TypedDict):
    ticket_id: str
    status: str
    owner: str


class TicketAdapter(Protocol):
    def fetch(self, ticket_id: str) -> TicketSummary:
        ...
