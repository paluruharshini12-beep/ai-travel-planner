"""Local account authentication, password reset, and Google OAuth helpers."""

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import sqlite3
from typing import Any
from urllib.parse import urlencode

import bcrypt
import requests

from src.config import get_settings
from src.database import DatabaseError, connection


class AuthError(ValueError):
    """A user-facing authentication or account validation error."""


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if len(normalized) > 254 or "@" not in normalized or normalized.startswith("@"):
        raise AuthError("Enter a valid email address.")
    local, _, domain = normalized.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise AuthError("Enter a valid email address.")
    return normalized


def _password_bytes(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if len(encoded) < 8:
        raise AuthError("Your password must contain at least 8 characters.")
    if len(encoded) > 72:
        raise AuthError("Your password must be no longer than 72 UTF-8 bytes.")
    return encoded


def create_account(name: str, email: str, password: str) -> dict[str, Any]:
    name = name.strip()
    if not name or len(name) > 100:
        raise AuthError("Enter a name between 1 and 100 characters.")
    normalized_email = _normalize_email(email)
    hashed = bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt(rounds=12)).decode()
    try:
        with connection() as db:
            cursor = db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, normalized_email, hashed),
            )
            row = db.execute(
                "SELECT id, name, email FROM users WHERE id = ?", (cursor.lastrowid,)
            ).fetchone()
            return dict(row)
    except DatabaseError as exc:
        if isinstance(exc.__cause__, sqlite3.IntegrityError):
            raise AuthError("An account with this email already exists.") from exc
        raise


def login(email: str, password: str) -> dict[str, Any]:
    normalized_email = _normalize_email(email)
    with connection() as db:
        row = db.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (normalized_email,),
        ).fetchone()
    if not row or not row["password_hash"]:
        raise AuthError("Email or password is incorrect.")
    try:
        valid = bcrypt.checkpw(password.encode("utf-8"), row["password_hash"].encode())
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise AuthError("Email or password is incorrect.")
    return {"id": row["id"], "name": row["name"], "email": row["email"]}


def create_password_reset(email: str) -> str | None:
    """Create a single-use reset token; return it only to support local setup."""
    normalized_email = _normalize_email(email)
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat()
    with connection() as db:
        user = db.execute(
            "SELECT id FROM users WHERE email = ?", (normalized_email,)
        ).fetchone()
        if not user:
            return None
        db.execute("DELETE FROM password_reset_tokens WHERE user_id = ?", (user["id"],))
        db.execute(
            """INSERT INTO password_reset_tokens (user_id, token_hash, expires_at)
               VALUES (?, ?, ?)""",
            (user["id"], token_hash, expires),
        )
    return token


def reset_password(token: str, new_password: str) -> None:
    token_hash = hashlib.sha256(token.strip().encode()).hexdigest()
    hashed = bcrypt.hashpw(_password_bytes(new_password), bcrypt.gensalt(rounds=12)).decode()
    now = datetime.now(timezone.utc).isoformat()
    with connection() as db:
        row = db.execute(
            """SELECT id, user_id FROM password_reset_tokens
               WHERE token_hash = ? AND expires_at > ?""",
            (token_hash, now),
        ).fetchone()
        if not row:
            raise AuthError("This reset link is invalid or has expired. Request a new one.")
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (hashed, row["user_id"]))
        db.execute("DELETE FROM password_reset_tokens WHERE id = ?", (row["id"],))


def google_authorization_url(state: str) -> str:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise AuthError("Google sign-in is not configured. Add both Google OAuth credentials to .env.")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def complete_google_login(code: str) -> dict[str, Any]:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise AuthError("Google sign-in is not configured.")
    try:
        response = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
            timeout=15,
        )
        response.raise_for_status()
        access_token = response.json().get("access_token")
        if not access_token:
            raise AuthError("Google sign-in did not return an access token.")
        profile_response = requests.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
    except requests.RequestException as exc:
        raise AuthError("Google sign-in could not connect. Please try again.") from exc
    if not profile.get("email") or not profile.get("sub") or not profile.get("email_verified"):
        raise AuthError("Google did not provide a verified email address.")

    email = _normalize_email(profile["email"])
    name = str(profile.get("name") or email.split("@", 1)[0])[:100]
    try:
        with connection() as db:
            row = db.execute(
                "SELECT id, name, email, google_sub FROM users WHERE email = ?", (email,)
            ).fetchone()
            if row:
                if row["google_sub"] not in (None, profile["sub"]):
                    raise AuthError("This email is already linked to another Google account.")
                db.execute("UPDATE users SET google_sub = ? WHERE id = ?", (profile["sub"], row["id"]))
                return {"id": row["id"], "name": row["name"], "email": row["email"]}
            cursor = db.execute(
                "INSERT INTO users (name, email, google_sub) VALUES (?, ?, ?)",
                (name, email, profile["sub"]),
            )
            return {"id": cursor.lastrowid, "name": name, "email": email}
    except DatabaseError as exc:
        if isinstance(exc.__cause__, sqlite3.IntegrityError):
            raise AuthError("This Google account could not be linked. Please contact support.") from exc
        raise
