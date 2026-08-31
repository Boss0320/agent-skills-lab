from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from src.contracts import WeatherObservation


class WeatherAdapter(Protocol):
    """Common callable surface for HarborWeather observations."""
    def fetch(self, station: str) -> WeatherObservation:
        ...


@dataclass(frozen=True)
class Station:
    code: str
    display_name: str
    timezone_name: str


class StationRegistry:
    """Resolve the small invented station set used by this fixture."""

    def __init__(self) -> None:
        self._stations = {
            "HBR-1": Station("HBR-1", "North Pier", "UTC"),
        }

    def require(self, code: str) -> Station:
        return self._stations[code]


def _iso_timestamp() -> str:
    return datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc).isoformat()


def _base_observation(station: str) -> WeatherObservation:
    return {
        "station": station,
        "temperature_c": 18.0,
        "observed_at": _iso_timestamp(),
    }


class ProductionWeatherAdapter:
    """Production-shaped deterministic adapter aligned with the contract."""

    def __init__(self, registry: StationRegistry | None = None) -> None:
        self._registry = registry or StationRegistry()

    def fetch(self, station: str) -> WeatherObservation:
        resolved = self._registry.require(station)
        observation = _base_observation(resolved.code)
        observation["temperature_c"] = 18.5
        return observation


class ObservationPresenter:
    """Format a complete observation for the system boundary."""

    def render(self, observation: WeatherObservation) -> str:
        timestamp = observation["observed_at"]
        return f"{observation['station']}@{timestamp}:{observation['temperature_c']:.1f}C"


class MockWeatherAdapter:
    """Deterministic adapter used by the fixture's isolated component test."""

    def __init__(self, registry: StationRegistry | None = None) -> None:
        self._registry = registry or StationRegistry()

    def station_name(self, station: str) -> str:
        return self._registry.require(station).display_name

    def fixed_temperature(self) -> float:
        return 19.5

    def fetch(self, station: str) -> WeatherObservation:
        return {"station": station, "temperature_c": 19.5}
