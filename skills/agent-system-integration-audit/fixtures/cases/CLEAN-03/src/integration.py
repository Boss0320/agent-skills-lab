from __future__ import annotations

from src.component import CachedQuoteSource, PrimaryQuoteSource
from src.contracts import QuoteResult


def load_quote(
    primary: PrimaryQuoteSource | None = None,
    cache: CachedQuoteSource | None = None,
) -> QuoteResult:
    primary_source = primary or PrimaryQuoteSource()
    cache_source = cache or CachedQuoteSource()
    try:
        return primary_source.fetch()
    except LookupError:
        return cache_source.fetch()
