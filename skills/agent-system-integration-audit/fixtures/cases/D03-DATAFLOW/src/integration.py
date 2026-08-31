from __future__ import annotations

from src.component import DecisionRenderer, SignalProducer


def adapt_signal(record: dict[str, object]) -> dict[str, object]:
    """Prepare the producer record for the public decision renderer."""
    selected_fields = ("signal", "confidence")
    return {field: record[field] for field in selected_fields}


def render_decision(signal: str, confidence: float, basis: str) -> str:
    record = SignalProducer().build(signal, confidence, basis)
    return DecisionRenderer().render(adapt_signal(record))
