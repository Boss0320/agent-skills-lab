from __future__ import annotations

from src.contracts import QuoteResult


class PrimaryQuoteSource:
    def fetch(self) -> QuoteResult:
        raise LookupError("primary source unavailable")


class CachedQuoteSource:
    def fetch(self) -> QuoteResult:
        return {
            "status": "degraded",
            "source": "cache",
            "value": 42.5,
            "observed_at": "2026-01-02T03:04:00+00:00",
        }
