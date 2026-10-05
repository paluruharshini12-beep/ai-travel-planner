"""OpenWeather current conditions and 5-day forecast integrations."""

from datetime import date, datetime, timedelta, timezone
from typing import Any

import requests

from src.config import get_settings


class WeatherError(RuntimeError):
    """A friendly weather service failure."""


def _request_weather(path: str, params: dict[str, Any], feature: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openweather_api_key:
        raise WeatherError("Add OPENWEATHER_API_KEY to .env to see live weather.")
    params["appid"] = settings.openweather_api_key
    params["units"] = "metric"
    try:
        response = requests.get(
            f"https://api.openweathermap.org/data/2.5/{path}",
            params=params,
            timeout=12,
        )
        if response.status_code == 404:
            raise WeatherError("We couldn't find weather for that destination. Check its spelling.")
        if response.status_code in (401, 403):
            raise WeatherError("OpenWeather rejected the API key. Check OPENWEATHER_API_KEY in .env.")
        if response.status_code == 429:
            raise WeatherError("OpenWeather rate limit reached. Try again shortly.")
        response.raise_for_status()
        return response.json()
    except WeatherError:
        raise
    except requests.Timeout as exc:
        raise WeatherError(f"The OpenWeather {feature} request timed out.") from exc
    except requests.RequestException as exc:
        raise WeatherError(f"Live {feature} is temporarily unavailable.") from exc
    except ValueError as exc:
        raise WeatherError(f"OpenWeather returned an unreadable {feature} response.") from exc


def get_current_weather(destination: str, country: str = "") -> dict[str, Any]:
    query = ", ".join(part.strip() for part in (destination, country) if part.strip())
    payload = _request_weather(
        "weather", {"q": query}, "current weather"
    )
    try:
        main = payload["main"]
        wind = payload.get("wind", {})
        condition = payload["weather"][0]
        return {
            "city": payload.get("name", destination),
            "temperature": round(float(main["temp"])),
            "feels_like": round(float(main["feels_like"])),
            "condition": str(condition["description"]).capitalize(),
            "icon": str(condition["icon"]),
            "humidity": int(main["humidity"]),
            "wind_speed": round(float(wind.get("speed", 0)), 1),
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise WeatherError("OpenWeather returned an incomplete current-weather response.") from exc


def get_daily_forecast(
    destination: str, country: str, start_date: str, days: int
) -> dict[str, dict[str, Any]]:
    """Aggregate OpenWeather's real 3-hour forecast into local destination dates."""
    query = ", ".join(part.strip() for part in (destination, country) if part.strip())
    payload = _request_weather("forecast", {"q": query}, "forecast")
    try:
        offset = int(payload.get("city", {}).get("timezone", 0))
        local_start = date.fromisoformat(start_date)
        result: dict[str, dict[str, Any]] = {}
        buckets: dict[str, list[dict[str, Any]]] = {}
        for item in payload.get("list", []):
            local_time = datetime.fromtimestamp(
                int(item["dt"]), tz=timezone.utc
            ) + timedelta(seconds=offset)
            day_key = local_time.date().isoformat()
            buckets.setdefault(day_key, []).append(item)

        for day_offset in range(days):
            day_key = (local_start + timedelta(days=day_offset)).isoformat()
            entries = buckets.get(day_key, [])
            if not entries:
                continue
            representative = min(
                entries,
                key=lambda item: abs(
                    (
                        datetime.fromtimestamp(int(item["dt"]), tz=timezone.utc)
                        + timedelta(seconds=offset)
                    ).hour
                    - 12
                ),
            )
            main = representative["main"]
            weather = representative["weather"][0]
            result[day_key] = {
                "date": day_key,
                "temperature": round(sum(float(item["main"]["temp"]) for item in entries) / len(entries)),
                "min_temperature": round(min(float(item["main"]["temp_min"]) for item in entries)),
                "max_temperature": round(max(float(item["main"]["temp_max"]) for item in entries)),
                "feels_like": round(float(main["feels_like"])),
                "condition": str(weather["description"]).capitalize(),
                "icon": str(weather["icon"]),
                "humidity": round(sum(int(item["main"]["humidity"]) for item in entries) / len(entries)),
                "wind_speed": round(
                    sum(float(item.get("wind", {}).get("speed", 0)) for item in entries)
                    / len(entries),
                    1,
                ),
                "sample_count": len(entries),
                "city": payload.get("city", {}).get("name", destination),
            }
        return result
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        raise WeatherError("OpenWeather returned an incomplete forecast response.") from exc
