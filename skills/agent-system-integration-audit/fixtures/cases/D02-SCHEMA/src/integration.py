from __future__ import annotations

from src.component import build_report
from src.contracts import ConsumerReport


def summarize(report: ConsumerReport) -> str:
    return f"{report['project']}:{report['period']}:{report['value']:.1f}"


def run_pipeline() -> str:
    produced = build_report()
    return summarize(produced)
