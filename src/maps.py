"""Mapbox geocoding integration."""

from typing import Any

import requests

from src.config import get_settings


class MapServiceError(RuntimeError):
    """A friendly Mapbox integration failure."""


def _request(url: str, params: dict[str, Any], feature: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.mapbox_access_token:
        raise MapServiceError("Add MAPBOX_ACCESS_TOKEN to your .env file to enable maps and places.")
    params["access_token"] = settings.mapbox_access_token
    try:
        response = requests.get(url, params=params, timeout=15)
        if response.status_code in (401, 403):
            raise MapServiceError("Mapbox rejected the access token. Check MAPBOX_ACCESS_TOKEN in .env.")
        response.raise_for_status()
        return response.json()
    except MapServiceError:
        raise
    except requests.Timeout as exc:
        raise MapServiceError(f"Mapbox {feature} timed out. Please try again.") from exc
    except requests.RequestException as exc:
        raise MapServiceError(f"Mapbox {feature} is temporarily unavailable.") from exc
    except ValueError as exc:
        raise MapServiceError(f"Mapbox returned an unreadable {feature} response.") from exc


def geocode_destination(destination: str) -> dict[str, Any]:
    if not destination.strip():
        raise MapServiceError("Enter a destination to locate it on the map.")
    url = (
        "https://api.mapbox.com/geocoding/v5/mapbox.places/"
        f"{requests.utils.quote(destination)}.json"
    )
    data = _request(url, {"limit": 1, "types": "place,locality,region,country"}, "geocoding")
    features = data.get("features", [])
    if not features:
        raise MapServiceError("We couldn't locate that destination. Check its spelling.")
    feature = features[0]
    center = feature.get("center", [])
    if len(center) != 2:
        raise MapServiceError("Mapbox could not provide coordinates for this destination.")
    return {
        "name": feature.get("place_name", destination),
        "longitude": float(center[0]),
        "latitude": float(center[1]),
    }
