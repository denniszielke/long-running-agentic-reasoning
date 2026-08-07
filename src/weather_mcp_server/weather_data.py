"""Generated weather data backed by a static city catalog."""

from __future__ import annotations

import json
import os
import random
from datetime import date, timedelta
from pathlib import Path
from typing import Any

_CATALOG_PATH = Path(__file__).with_name("cities.json")
_CONDITIONS = ["clear sky", "partly cloudy", "overcast", "light rain", "heavy rain", "thunderstorm", "snow", "fog", "windy"]
_ALIASES = {"ocean": "sea", "seaside": "sea", "mountain": "mountains", "alpine": "mountains", "woods": "forest", "woodland": "forest", "urban": "city"}
_ACTIVITIES = {
    "clear": ["walking tour", "outdoor sightseeing", "picnic"],
    "rain": ["museum visit", "covered market", "local food tour"],
    "snow": ["winter sightseeing", "cafe visit", "photography walk"],
    "wind": ["sheltered neighborhood tour", "museum visit", "cafe visit"],
    "fog": ["museum visit", "local food tour", "indoor cultural experience"],
    "default": ["walking tour", "local food tour", "museum visit"],
}


def _reading(rng: random.Random, base_temperature: float) -> dict[str, Any]:
    temperature = round(base_temperature + rng.uniform(-6.0, 6.0), 1)
    return {
        "temperature_c": temperature,
        "feels_like_c": round(temperature + rng.uniform(-3.0, 2.0), 1),
        "condition": rng.choice(_CONDITIONS),
        "humidity_percent": rng.randint(30, 95),
        "wind_kph": round(rng.uniform(0, 45), 1),
        "precipitation_mm": round(max(0.0, rng.uniform(-4, 12)), 1),
    }


class WeatherStore:
    def __init__(self) -> None:
        seed = os.getenv("WEATHER_SEED", "")
        rng = random.Random(int(seed)) if seed.strip().lstrip("-").isdigit() else random.Random()
        self._catalog: list[dict[str, Any]] = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
        self._by_city = {item["city"].lower(): item for item in self._catalog}
        today = date.today()
        self._current = {item["city"].lower(): _reading(rng, item["base_temp_c"]) for item in self._catalog}
        self._forecast = {
            item["city"].lower(): [
                {"date": (today + timedelta(days=day)).isoformat(), **_reading(rng, item["base_temp_c"])}
                for day in range(7)
            ]
            for item in self._catalog
        }

    def city_names(self) -> list[str]:
        return [item["city"] for item in self._catalog]

    def cities(self) -> list[dict[str, Any]]:
        return [{key: item[key] for key in ("city", "country", "climate", "environments")} for item in self._catalog]

    def _resolve(self, city: str) -> dict[str, Any] | None:
        return self._by_city.get(city.strip().lower())

    def current(self, city: str) -> dict[str, Any] | None:
        metadata = self._resolve(city)
        if metadata is None:
            return None
        return {"city": metadata["city"], "country": metadata["country"], "climate": metadata["climate"], **self._current[metadata["city"].lower()]}

    def forecast(self, city: str, days: int) -> dict[str, Any] | None:
        metadata = self._resolve(city)
        if metadata is None:
            return None
        days = max(1, min(days, 7))
        return {"city": metadata["city"], "country": metadata["country"], "days": days, "forecast": self._forecast[metadata["city"].lower()][:days]}

    def propose_activity(self, city: str, conditions: str) -> dict[str, Any]:
        metadata = self._resolve(city)
        if metadata is None:
            return {"error": f"Unknown city '{city}'.", "known_cities": self.city_names()}
        normalized = conditions.lower()
        category = "default"
        for candidate, keywords in (("rain", ("rain", "wet", "storm")), ("snow", ("snow", "freezing", "icy")), ("wind", ("wind", "breezy", "gust")), ("fog", ("fog", "mist")), ("clear", ("clear", "sun", "dry", "warm", "hot"))):
            if any(keyword in normalized for keyword in keywords):
                category = candidate
                break
        activities = list(_ACTIVITIES[category])
        environments = set(metadata["environments"])
        if category == "clear" and environments & {"sea", "coast", "beach", "island"}:
            activities.insert(0, "waterfront or beach visit")
        if category == "clear" and environments & {"mountains", "highlands", "forest"}:
            activities.insert(0, "hiking")
        return {"city": metadata["city"], "country": metadata["country"], "conditions": conditions, "environments": metadata["environments"], "activities": activities[:3]}

    def propose_city(self, *, conditions: str | None = None, on_date: str | None = None, environment: str | None = None) -> dict[str, Any]:
        if not conditions and not environment:
            return {"error": "Provide conditions, environment, or both."}
        try:
            target_date = date.fromisoformat(on_date) if on_date else date.today()
        except ValueError:
            return {"error": "date must use ISO format YYYY-MM-DD."}
        day_index = (target_date - date.today()).days
        if not 0 <= day_index <= 6:
            return {"error": "date must be within the available 7-day forecast.", "available_from": date.today().isoformat(), "available_to": (date.today() + timedelta(days=6)).isoformat()}
        desired_environment = _ALIASES.get(environment.strip().lower(), environment.strip().lower()) if environment else None
        ranked = []
        for metadata in self._catalog:
            if desired_environment and desired_environment not in metadata["environments"]:
                continue
            reading = self._forecast[metadata["city"].lower()][day_index]
            score, matches = _score_conditions(reading, conditions)
            ranked.append({"city": metadata["city"], "country": metadata["country"], "date": reading["date"], "weather": reading, "environments": metadata["environments"], "matched_conditions": matches, "score": score + (1 if desired_environment else 0)})
        ranked.sort(key=lambda item: (-item["score"], item["city"]))
        return {"requested_conditions": conditions, "requested_environment": environment, "date": target_date.isoformat(), "proposals": ranked[:3]}


def _score_conditions(reading: dict[str, Any], conditions: str | None) -> tuple[int, list[str]]:
    if not conditions:
        return 0, []
    desired = conditions.lower()
    actual = reading["condition"]
    checks = [
        ("clear", "clear" in actual or "partly cloudy" in actual, ("clear", "sunny", "sun")),
        ("cloudy", "cloud" in actual or "overcast" in actual, ("cloud", "cloudy", "overcast")),
        ("rain", "rain" in actual or "thunderstorm" in actual, ("rain", "rainy", "wet")),
        ("snow", "snow" in actual, ("snow", "snowy")),
        ("windy", "windy" in actual or reading["wind_kph"] >= 25, ("windy", "wind")),
        ("fog", "fog" in actual, ("fog", "foggy")),
        ("hot", reading["temperature_c"] >= 25, ("hot",)),
        ("warm", reading["temperature_c"] >= 18, ("warm",)),
        ("mild", 10 <= reading["temperature_c"] <= 24, ("mild",)),
        ("cool", reading["temperature_c"] <= 15, ("cool",)),
        ("cold", reading["temperature_c"] <= 8, ("cold",)),
        ("dry", reading["precipitation_mm"] <= 1 and not any(word in actual for word in ("rain", "snow", "storm")), ("dry",)),
        ("humid", reading["humidity_percent"] >= 70, ("humid",)),
        ("calm", reading["wind_kph"] <= 15, ("calm",)),
    ]
    matches = [label for label, matched, keywords in checks if matched and any(keyword in desired for keyword in keywords)]
    return len(matches), matches