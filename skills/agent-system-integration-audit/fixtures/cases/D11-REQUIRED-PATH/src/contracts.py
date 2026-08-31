from __future__ import annotations

from typing import Literal, TypedDict


class DispatchRequest(TypedDict):
    request_id: str
    approved: bool


class DispatchResult(TypedDict):
    status: Literal["accepted", "denied"]
    request_id: str
