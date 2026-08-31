from __future__ import annotations

from src.contracts import DrawdownObservation


def normalized_observation(account_id: str) -> DrawdownObservation:
    """Return the account drawdown normalized to a zero-to-one ratio."""
    return {
        "account_id": account_id,
        "drawdown": 0.075,
        "drawdown_basis": "ratio",
    }
