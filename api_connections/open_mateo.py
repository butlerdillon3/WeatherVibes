"""Today's weather from Open-Meteo, fetched when today() is called.

Weather data by Open-Meteo.com, https://open-meteo.com/
"""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes, from the Open-Meteo forecast docs.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    97: "Heavy thunderstorm",
    99: "Thunderstorm with heavy hail",
}


class OpenMateoError(Exception):
    """A zip code could not be resolved, or an Open-Meteo request failed."""


class OpenMateo:
    """Fetches today's weather for a US zip code when today() is called."""

    def __init__(self, zip_code: str) -> None:
        self.zip_code = _normalize_zip(zip_code)

    def today(self) -> dict[str, object]:
        """Look up the zip code and return today's place, code, condition, high, and low."""
        place = self._geocode()
        daily = self._forecast(place["latitude"], place["longitude"])
        code = int(daily["weather_code"][0])
        return {
            "place": place["name"],
            "weather_code": code,
            "condition": WEATHER_CODES.get(code, f"Unknown ({code})"),
            "high": daily["temperature_2m_max"][0],
            "low": daily["temperature_2m_min"][0],
        }

    def _geocode(self) -> dict:
        payload = _get_json(
            GEOCODING_URL,
            {"name": self.zip_code, "count": 20, "language": "en", "countryCode": "US"},
        )
        for place in payload.get("results", []):
            if self.zip_code in place.get("postcodes", []):
                return place
        raise OpenMateoError(f"No location found for zip code {self.zip_code}.")

    def _forecast(self, latitude: float, longitude: float) -> dict:
        payload = _get_json(
            FORECAST_URL,
            {
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "forecast_days": 1,
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
            },
        )
        return payload["daily"]


def _normalize_zip(zip_code: str) -> str:
    base = zip_code.strip().split("-", 1)[0].strip()
    if len(base) != 5 or not base.isdigit():
        raise OpenMateoError(f"Expected a 5-digit zip code, got {zip_code!r}.")
    return base


def _get_json(url: str, params: dict[str, object]) -> dict:
    try:
        with urlopen(f"{url}?{urlencode(params)}", timeout=10) as response:
            payload = json.load(response)
    except HTTPError as exc:
        reason = exc.reason
        try:
            reason = json.load(exc).get("reason", reason)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
        raise OpenMateoError(f"Open-Meteo request failed ({exc.code}): {reason}") from exc
    except URLError as exc:
        raise OpenMateoError(f"Could not reach Open-Meteo: {exc.reason}") from exc

    if not isinstance(payload, dict) or payload.get("error"):
        reason = payload.get("reason", "unexpected response") if isinstance(payload, dict) else "unexpected response"
        raise OpenMateoError(f"Open-Meteo returned an error: {reason}")
    return payload
