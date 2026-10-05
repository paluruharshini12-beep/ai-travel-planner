"""Travel request validation shared by the dashboard and itinerary generator."""

from typing import Any
from datetime import date


class TripValidationError(ValueError):
    """A friendly input validation failure."""


def validate_trip(values: dict[str, Any]) -> dict[str, Any]:
    destination = str(values.get("destination", "")).strip()
    country = str(values.get("country", "")).strip()
    name = str(values.get("name", "")).strip()
    state = str(values.get("state", "")).strip()
    if not name or not destination:
        raise TripValidationError("Add your name and destination to plan a trip.")
    if len(destination) > 120 or len(country) > 80 or len(state) > 100:
        raise TripValidationError("One of the location fields is too long.")
    try:
        budget = float(values["budget"])
        days = int(values["days"])
        travelers = int(values["travelers"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TripValidationError("Enter valid trip budget, duration, and traveler values.") from exc
    if budget <= 0 or budget > 100_000_000:
        raise TripValidationError("Budget must be greater than zero and no more than 100,000,000.")
    if not 1 <= days <= 30:
        raise TripValidationError("Trip duration must be between 1 and 30 days.")
    if not 1 <= travelers <= 20:
        raise TripValidationError("Traveler count must be between 1 and 20.")
    raw_start_date = values.get("start_date", date.today())
    try:
        start_date = (
            raw_start_date.isoformat()
            if isinstance(raw_start_date, date)
            else date.fromisoformat(str(raw_start_date)).isoformat()
        )
    except (TypeError, ValueError) as exc:
        raise TripValidationError("Choose a valid trip start date.") from exc
    currency = str(values.get("currency", "USD")).strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise TripValidationError("Choose a valid three-letter currency code.")
    styles = {"Budget", "Relaxed", "Adventure", "Luxury", "Family", "Romantic", "Culture & Food"}
    style = str(values.get("travel_style", ""))
    if style not in styles:
        raise TripValidationError("Choose one of the available travel styles.")
    interests = values.get("interests", [])
    if not isinstance(interests, list):
        raise TripValidationError("Choose at least one interest.")
    normalized_interests = [str(item).strip() for item in interests if str(item).strip()]
    if not normalized_interests:
        raise TripValidationError("Choose at least one interest.")
    return {
        "name": name,
        "destination": destination,
        "country": country,
        "state": state,
        "start_date": start_date,
        "budget": budget,
        "currency": currency,
        "days": days,
        "travelers": travelers,
        "travel_style": style,
        "interests": normalized_interests,
    }
