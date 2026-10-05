"""AI-backed itinerary generation with a useful local fallback."""

import json
import re
from datetime import date, timedelta
from typing import Any

import requests

from src.config import get_settings


class PlannerError(RuntimeError):
    """A user-facing itinerary generation error."""


def _prompt(
    trip: dict[str, Any],
    weather: dict[str, Any] | None,
    places: list[dict[str, Any]],
    forecasts: dict[str, dict[str, Any]],
) -> str:
    current_conditions = (
        f"Current conditions now (not a trip-date forecast): {weather['condition']}, "
        f"{weather['temperature']} C."
        if weather
        else "Current weather is unavailable."
    )
    weather_text = json.dumps(forecasts, ensure_ascii=False) if forecasts else (
        "No daily forecast is currently available. Do not invent or claim weather."
    )
    verified_places = [
        {"name": item["name"], "address": item["address"]} for item in places[:10]
    ]
    return f"""Create a useful, realistic travel itinerary as valid JSON only.
Return these top-level keys: trip_summary, budget_breakdown, travel_tips, safety_tips, days.
Each day has day, title, morning, afternoon, evening. Each period object has activity,
place, duration, food, transport, estimated_cost. Use the requested currency and numeric
costs; keep total spending within budget where practical. Respect the style and interests.
Use the exact date for each day. Select places only from the verified place list below.
Do not invent verified addresses, opening hours, or weather. Clearly mark costs as estimates.
Trip details: {json.dumps(trip, ensure_ascii=False)}
{current_conditions}
Verified daily weather forecasts by local destination date: {weather_text}
Places returned by the configured live places service: {json.dumps(verified_places, ensure_ascii=False)}
Return exactly {int(trip['days'])} days."""


def _parse_json(text: str) -> dict[str, Any]:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise PlannerError("The AI returned an unreadable itinerary. Please try again.") from exc
    if not isinstance(data, dict) or not isinstance(data.get("days"), list) or not data["days"]:
        raise PlannerError("The AI returned an incomplete itinerary. Please try again.")
    return data


def _openai(prompt: str, api_key: str) -> str:
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "temperature": 0.7,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": "You are a careful travel planner. Return valid JSON only."},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=60,
        )
        if response.status_code in (401, 403):
            raise PlannerError("OpenAI rejected the API key. Check OPENAI_API_KEY in .env.")
        if response.status_code == 429:
            raise PlannerError("OpenAI is rate-limited. Try again later.")
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except PlannerError:
        raise
    except requests.Timeout as exc:
        raise PlannerError("The AI request timed out. Please try again.") from exc
    except requests.RequestException as exc:
        raise PlannerError("The OpenAI itinerary service is unavailable right now.") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PlannerError("OpenAI returned an unexpected itinerary response.") from exc


def _gemini(prompt: str, api_key: str) -> str:
    try:
        response = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            params={"key": api_key},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
            },
            timeout=60,
        )
        if response.status_code in (400, 401, 403):
            raise PlannerError("Gemini rejected the API key or request. Check GEMINI_API_KEY in .env.")
        if response.status_code == 429:
            raise PlannerError("Gemini is rate-limited. Try again later.")
        response.raise_for_status()
        return response.json()["candidates"][0]["content"]["parts"][0]["text"]
    except PlannerError:
        raise
    except requests.Timeout as exc:
        raise PlannerError("The AI request timed out. Please try again.") from exc
    except requests.RequestException as exc:
        raise PlannerError("The Gemini itinerary service is unavailable right now.") from exc
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise PlannerError("Gemini returned an unexpected itinerary response.") from exc


def generate_local_itinerary(
    trip: dict[str, Any],
    places: list[dict[str, Any]],
    forecasts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Build a personalized starting itinerary without pretending it is live AI output."""
    destination = trip["destination"]
    interests = trip.get("interests") or ["local highlights"]
    currency = trip["currency"]
    days = int(trip["days"])
    budget = float(trip["budget"])
    travelers = int(trip["travelers"])
    names = [str(place["name"]) for place in places]
    amount = round(budget / max(days * travelers, 1) * 0.18, 2)
    day_plans: list[dict[str, Any]] = []
    for index in range(days):
        day_date = (date.fromisoformat(str(trip["start_date"])) + timedelta(days=index)).isoformat()
        day_weather = forecasts.get(day_date)
        first_place = names[index % len(names)] if names else "No verified place data available"
        second_place = names[(index + 1) % len(names)] if len(names) > 1 else (
            names[0] if names else "No verified place data available"
        )
        interest = interests[index % len(interests)]
        if day_weather:
            current_weather = (
                f" Forecast for {day_date}: {day_weather['condition']}, "
                f"{day_weather['temperature']} C."
            )
            if any(term in day_weather["condition"].casefold() for term in ("rain", "storm", "thunder", "snow")):
                morning_activity = (
                    "Keep the morning flexible and favor indoor options because the forecast "
                    f"shows {day_weather['condition'].lower()}."
                )
            elif day_weather["temperature"] >= 33:
                morning_activity = "Plan outdoor sightseeing early and take shaded, air-conditioned breaks."
            else:
                morning_activity = f"Ease into the day with an outdoor walk shaped around {interest.lower()}."
        else:
            current_weather = " No forecast is available for this date; check conditions before setting out."
            morning_activity = f"Ease into the day with a flexible walk shaped around {interest.lower()}."
        day_plans.append(
            {
                "day": index + 1,
                "title": f"Day {index + 1}: Discover {destination}",
                "morning": {
                    "activity": f"{morning_activity}{current_weather}",
                    "place": first_place,
                    "duration": "2-3 hours",
                    "food": f"Find a well-reviewed local breakfast near {first_place}.",
                    "transport": "Walk where practical; compare public transit and licensed taxi options.",
                    "estimated_cost": amount,
                },
                "afternoon": {
                    "activity": f"Explore a cultural stop, market, or outdoor area related to {interest.lower()}.",
                    "place": second_place,
                    "duration": "2-4 hours",
                    "food": "Choose a busy local restaurant and check menu prices before ordering.",
                    "transport": "Use public transit for longer hops and allow time for transfers.",
                    "estimated_cost": amount,
                },
                "evening": {
                    "activity": "Enjoy a relaxed dinner and a scenic neighborhood stroll.",
                    "place": names[(index + 2) % len(names)] if names else "No verified place data available",
                    "duration": "2-3 hours",
                    "food": "Try a regional specialty; confirm dietary needs and final prices.",
                    "transport": "Plan a safe, licensed ride back to your accommodation.",
                    "estimated_cost": amount,
                },
            }
        )
    return {
        "trip_summary": (
            f"A {days}-day {trip['travel_style'].lower()} trip to {destination} for "
            f"{travelers} traveler(s), centered on {', '.join(interests)}. This is a locally "
            "generated starting point; check current opening hours, routes, prices, and weather."
        ),
        "budget_breakdown": {
            "accommodation": round(budget * 0.35, 2),
            "food": round(budget * 0.25, 2),
            "transportation": round(budget * 0.18, 2),
            "activities": round(budget * 0.15, 2),
            "buffer": round(budget * 0.07, 2),
        },
        "travel_tips": [
            "Confirm opening hours and ticket requirements directly before visiting.",
            "Save bookings and your accommodation address so they are available offline.",
            "Keep an accepted payment option and a small emergency reserve.",
        ],
        "safety_tips": [
            "Use licensed transport and agree on a fare or check the meter before departure.",
            "Keep valuables secure in crowded places and follow local authority guidance.",
            "Share your plan with someone you trust and save local emergency numbers.",
        ],
        "days": day_plans,
        "generation_mode": "Local fallback",
        "currency": currency,
    }


def generate_itinerary(
    trip: dict[str, Any],
    weather: dict[str, Any] | None = None,
    places: list[dict[str, Any]] | None = None,
    forecasts: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settings = get_settings()
    places = places or []
    forecasts = forecasts or {}
    if not settings.openai_api_key and not settings.gemini_api_key:
        itinerary = generate_local_itinerary(trip, places, forecasts)
    else:
        prompt = _prompt(trip, weather, places, forecasts)
        if settings.openai_api_key:
            itinerary = _parse_json(_openai(prompt, settings.openai_api_key))
            itinerary["generation_mode"] = "OpenAI"
        else:
            itinerary = _parse_json(_gemini(prompt, settings.gemini_api_key))
            itinerary["generation_mode"] = "Gemini"
    return enrich_itinerary(trip, itinerary, places, forecasts)


def enrich_itinerary(
    trip: dict[str, Any],
    itinerary: dict[str, Any],
    places: list[dict[str, Any]],
    forecasts: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Attach trip dates, real place records, and only provider-backed forecasts."""
    start_date = date.fromisoformat(str(trip["start_date"]))
    expected_days = int(trip["days"])
    if len(itinerary.get("days", [])) != expected_days:
        raise PlannerError(
            f"The itinerary service returned {len(itinerary.get('days', []))} days; "
            f"{expected_days} were requested. Please try generating it again."
        )
    periods = ("morning", "afternoon", "evening")
    for index, day_plan in enumerate(itinerary.get("days", [])):
        day_date = (start_date + timedelta(days=index)).isoformat()
        day_plan["date"] = day_date
        day_plan["weather"] = forecasts.get(day_date)
        for period_index, period in enumerate(periods):
            activity = day_plan.get(period)
            if not isinstance(activity, dict):
                continue
            if places:
                place = places[(index * len(periods) + period_index) % len(places)]
                activity["place"] = place["name"]
                activity["place_address"] = place["address"]
                activity["latitude"] = place["latitude"]
                activity["longitude"] = place["longitude"]
                activity["place_category"] = place["description"]
            else:
                activity["place"] = "No verified place data available"
                activity["place_address"] = ""
                activity["latitude"] = None
                activity["longitude"] = None
                activity["place_category"] = ""
    itinerary["currency"] = trip["currency"]
    return itinerary
