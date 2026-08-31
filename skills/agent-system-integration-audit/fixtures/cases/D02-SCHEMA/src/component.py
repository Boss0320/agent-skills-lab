from __future__ import annotations

from src.contracts import ProducerReport


class MetricsCollector:
    """Create one deterministic NorthstarMetrics observation."""

    def collect(self, project: str) -> ProducerReport:
        return {"project": project, "period": "quarterly", "value": 42.0}


def build_report(project: str = "north") -> ProducerReport:
    return MetricsCollector().collect(project)
