from __future__ import annotations

from typing import TypedDict


class WeatherObservation(TypedDict):
    """Fields every HarborWeather adapter must return."""

    station: str
    temperature_c: float
    observed_at: str
