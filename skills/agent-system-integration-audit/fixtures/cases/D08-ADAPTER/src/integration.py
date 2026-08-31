from __future__ import annotations

from src.component import MockWeatherAdapter, ObservationPresenter, ProductionWeatherAdapter, WeatherAdapter


def select_adapter(name: str) -> WeatherAdapter:
    if name == "mock":
        return MockWeatherAdapter()
    if name == "production":
        return ProductionWeatherAdapter()
    raise ValueError(f"unknown adapter: {name}")


def render_station(adapter_name: str, station: str = "HBR-1") -> str:
    observation = select_adapter(adapter_name).fetch(station)
    return ObservationPresenter().render(observation)
