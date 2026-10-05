"""User-owned trip storage and retrieval."""

import json
import sqlite3
from typing import Any

from src.database import DatabaseError, connection


class TripError(RuntimeError):
    """A friendly saved-trip failure."""


def save_trip(user_id: int, trip: dict[str, Any], itinerary: dict[str, Any]) -> int:
    try:
        with connection() as db:
            cursor = db.execute(
                """INSERT INTO trips
                   (user_id, destination, country, state, budget, currency, start_date, days,
                    travelers, travel_style, interests, itinerary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    user_id,
                    trip["destination"],
                    trip["country"],
                    trip.get("state", ""),
                    float(trip["budget"]),
                    trip["currency"],
                    trip.get("start_date", ""),
                    int(trip["days"]),
                    int(trip["travelers"]),
                    trip["travel_style"],
                    json.dumps(trip.get("interests", []), ensure_ascii=False),
                    json.dumps(itinerary, ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)
    except (DatabaseError, sqlite3.Error, KeyError, TypeError, ValueError) as exc:
        raise TripError("We couldn't save this trip. Please try again.") from exc


def list_trips(user_id: int) -> list[dict[str, Any]]:
    try:
        with connection() as db:
            rows = db.execute(
                """SELECT id, destination, country, state, budget, currency, start_date, days,
                          travelers, travel_style, created_at
                   FROM trips WHERE user_id = ? ORDER BY created_at DESC, id DESC""",
                (user_id,),
            ).fetchall()
        return [dict(row) for row in rows]
    except DatabaseError as exc:
        raise TripError("We couldn't load your saved trips.") from exc


def get_trip(user_id: int, trip_id: int) -> dict[str, Any] | None:
    try:
        with connection() as db:
            row = db.execute(
                "SELECT * FROM trips WHERE user_id = ? AND id = ?", (user_id, trip_id)
            ).fetchone()
        if not row:
            return None
        trip = dict(row)
        trip["interests"] = json.loads(trip["interests"])
        trip["itinerary"] = json.loads(trip["itinerary"])
        return trip
    except (DatabaseError, json.JSONDecodeError, TypeError) as exc:
        raise TripError("We couldn't open this saved trip.") from exc


def delete_trip(user_id: int, trip_id: int) -> bool:
    try:
        with connection() as db:
            cursor = db.execute(
                "DELETE FROM trips WHERE user_id = ? AND id = ?", (user_id, trip_id)
            )
        return cursor.rowcount > 0
    except DatabaseError as exc:
        raise TripError("We couldn't delete this trip. Please try again.") from exc
