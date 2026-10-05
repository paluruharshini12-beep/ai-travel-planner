"""Mapbox Search Box integration for real destination points of interest."""

from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from src.config import get_settings
from src.maps import MapServiceError


def get_places(destination: str) -> list[dict[str, Any]]:
    """Search multiple POI categories across the destination, deduplicating live results."""
    settings = get_settings()
    if not settings.mapbox_access_token:
        raise MapServiceError("Add MAPBOX_ACCESS_TOKEN to your .env file to enable maps and places.")
    destination = destination.strip()
    if not destination:
        raise MapServiceError("Enter a destination to search for places.")

    categories = (
        "tourist attractions",
        "historic landmarks",
        "museums",
        "parks and gardens",
        "markets",
    )

    def search(category: str) -> list[dict[str, Any]]:
        try:
            response = requests.get(
                "https://api.mapbox.com/search/searchbox/v1/forward",
                params={
                    "q": f"{category} in {destination}",
                    "limit": 10,
                    "language": "en",
                    "types": "poi",
                    "access_token": settings.mapbox_access_token,
                },
                timeout=15,
            )
            if response.status_code in (401, 403):
                raise MapServiceError("Mapbox rejected the access token. Check MAPBOX_ACCESS_TOKEN in .env.")
            if response.status_code == 429:
                raise MapServiceError("Mapbox places search is rate-limited. Try again shortly.")
            response.raise_for_status()
            payload = response.json()
        except MapServiceError:
            raise
        except requests.Timeout as exc:
            raise MapServiceError("Mapbox places search timed out. Please try again.") from exc
        except requests.RequestException as exc:
            raise MapServiceError("Mapbox places search is temporarily unavailable.") from exc
        except ValueError as exc:
            raise MapServiceError("Mapbox returned an unreadable places response.") from exc

        results: list[dict[str, Any]] = []
        for feature in payload.get("features", []):
            properties = feature.get("properties", {})
            point = feature.get("geometry", {}).get("coordinates", [])
            if len(point) != 2:
                continue
            name = properties.get("name") or feature.get("text")
            if not name:
                continue
            results.append(
                {
                    "name": str(name),
                    "address": properties.get("full_address")
                    or properties.get("place_formatted")
                    or properties.get("address")
                    or "Address not provided",
                    "description": properties.get("poi_category")
                    or properties.get("category")
                    or category.title(),
                    "longitude": float(point[0]),
                    "latitude": float(point[1]),
                }
            )
        return results

    try:
        with ThreadPoolExecutor(max_workers=len(categories)) as pool:
            batches = list(pool.map(search, categories))
    except MapServiceError:
        raise
    unique: dict[tuple[str, float, float], dict[str, Any]] = {}
    for batch in batches:
        for place in batch:
            key = (
                place["name"].strip().casefold(),
                round(place["longitude"], 5),
                round(place["latitude"], 5),
            )
            unique.setdefault(key, place)
    return list(unique.values())
