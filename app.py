"""Wanderly AI — a colorful, local-first travel planner."""

from __future__ import annotations

import html
import json
import secrets
from datetime import date, timedelta
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from src.ai_planner import PlannerError, enrich_itinerary, generate_itinerary
from src.auth import (
    AuthError,
    complete_google_login,
    create_account,
    create_password_reset,
    google_authorization_url,
    login,
    reset_password,
)
from src.config import get_settings
from src.database import DatabaseError, initialize_database
from src.maps import MapServiceError, geocode_destination
from src.places import get_places
from src.planner import TripValidationError, validate_trip
from src.trips import TripError, delete_trip, get_trip, list_trips, save_trip
from src.weather import WeatherError, get_current_weather, get_daily_forecast


st.set_page_config(
    page_title="Wanderly AI | Plan unforgettable journeys",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@500;600;700;800&display=swap');
:root { --ink:#25163f; --muted:#786d8d; --pink:#ff5f9e; --orange:#ff9b52; --purple:#7954e8; --blue:#53b8ef; --surface:#fff; }
html, body, [class*="css"] { font-family:'DM Sans',sans-serif; color:var(--ink); }
.stApp { background:linear-gradient(135deg,#fff8fb 0%,#f8f5ff 48%,#f1fbff 100%); }
[data-testid="stHeader"] { background:transparent; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#fff 0%,#fff7fb 100%); border-right:1px solid #f0e9f8; }
[data-testid="stSidebar"] > div:first-child { padding-top:1.1rem; }
h1,h2,h3 { font-family:'Manrope',sans-serif !important; color:#281746 !important; letter-spacing:-.035em; }
.brand { font-family:'Manrope',sans-serif; font-weight:800; font-size:1.25rem; color:#31204e; }
.brand span { background:linear-gradient(100deg,#ff4f9a,#ff9d4e,#8054e8); -webkit-background-clip:text; background-clip:text; color:transparent; }
.tagline { color:#837793; font-size:.88rem; margin-top:-.25rem; }
.hero { position:relative; overflow:hidden; border-radius:28px; padding:2.15rem 2.2rem; margin: .35rem 0 1.45rem; color:#fff; background:linear-gradient(115deg,#744be4 0%,#a94dd8 44%,#ff668b 100%); box-shadow:0 18px 45px rgba(126,72,205,.19); }
.hero:after { content:'✈'; position:absolute; right:7%; top:-35px; font-size:9rem; opacity:.14; transform:rotate(-16deg); }
.hero h1 { color:white !important; font-size:clamp(1.9rem,4vw,3rem); margin:0 0 .45rem; }
.hero p { color:#fff; opacity:.9; font-size:1.04rem; margin:0; max-width:620px; }
.eyebrow { text-transform:uppercase; letter-spacing:.13em; font-size:.72rem; font-weight:800; opacity:.82; margin-bottom:.5rem; }
.section-title { display:flex; align-items:center; gap:.55rem; font-family:'Manrope',sans-serif; font-weight:800; font-size:1.28rem; margin:.8rem 0 .35rem; }
.subtle { color:var(--muted); font-size:.91rem; }
.stButton > button, .stFormSubmitButton > button { border:0; border-radius:14px; background:linear-gradient(100deg,#ff5c9d,#ff9c54); color:white; font-weight:800; min-height:2.8rem; box-shadow:0 8px 20px rgba(255,104,144,.2); transition:transform .15s,box-shadow .15s; }
.stButton > button:hover, .stFormSubmitButton > button:hover { color:white; transform:translateY(-2px); box-shadow:0 11px 25px rgba(255,104,144,.28); border:0; }
.stButton > button[kind="secondary"] { background:white; color:#704dd2; border:1px solid #e7def5; box-shadow:none; }
.stTextInput input, .stNumberInput input, .stSelectbox div[data-baseweb="select"], .stMultiSelect div[data-baseweb="select"] { border-radius:12px; }
[data-testid="stMetric"] { background:#fff; padding:1rem 1.1rem; border:1px solid #f0e9f8; border-radius:18px; box-shadow:0 8px 26px rgba(63,37,96,.05); }
[data-testid="stMetricLabel"] { color:#837793; }
[data-testid="stMetricValue"] { color:#30204d; }
.stAlert { border-radius:14px; }
.place-card { background:white; border:1px solid #f0e9f8; padding:1rem 1.05rem; border-radius:17px; margin:.55rem 0; box-shadow:0 8px 24px rgba(50,30,80,.045); }
.place-card h4 { margin:0 0 .3rem; color:#34204f; font-size:1rem; }
.place-card p { margin:0; color:#81758e; font-size:.85rem; }
.activity { background:#fff; border:1px solid #f0e9f8; border-radius:16px; padding:1rem; height:100%; box-shadow:0 7px 21px rgba(50,30,80,.04); }
.activity small { color:#8258d8; font-weight:800; letter-spacing:.08em; text-transform:uppercase; }
.activity h4 { color:#312047; margin:.35rem 0; }
.activity p { color:#726882; font-size:.9rem; margin:.35rem 0; }
.auth-wrap { max-width:850px; margin:3vh auto 0; background:#fff; padding:2.1rem; border-radius:26px; box-shadow:0 20px 60px rgba(72,42,111,.12); border:1px solid #f0e8f7; }
.auth-logo { font-family:'Manrope',sans-serif; font-size:2rem; font-weight:800; background:linear-gradient(100deg,#ff4f9a,#ff9d4e,#8054e8); -webkit-background-clip:text; background-clip:text; color:transparent; }
div[data-testid="stExpander"] { background:rgba(255,255,255,.75); border:1px solid #efe8f6; border-radius:17px; }
@media(max-width:700px) { .hero { padding:1.6rem; border-radius:21px; } .auth-wrap { padding:1.2rem; margin-top:1vh; } }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

try:
    initialize_database()
except DatabaseError as exc:
    st.error(f"Database is unavailable: {exc}")
    st.stop()

for key, initial in {
    "user": None,
    "view": "🧭 Trip Planner",
    "trip": None,
    "itinerary": None,
    "weather": None,
    "weather_error": None,
    "forecast_by_date": {},
    "forecast_error": None,
    "geocode": None,
    "map_error": None,
    "places": [],
    "places_error": None,
    "saved_trip_id": None,
    "oauth_state": None,
    "reset_token": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = initial


def _consume_query_params() -> None:
    auth_error = st.query_params.get("error")
    code = st.query_params.get("code")
    returned_state = st.query_params.get("state")
    if auth_error:
        st.session_state["oauth_message"] = "Google sign-in was cancelled or denied."
        st.query_params.clear()
        return
    if code:
        expected_state = st.session_state.get("oauth_state")
        st.query_params.clear()
        st.session_state["oauth_state"] = None
        if not expected_state or not returned_state or not secrets.compare_digest(
            str(expected_state), str(returned_state)
        ):
            st.session_state["oauth_message"] = "Google sign-in could not be verified. Please try again."
            return
        try:
            st.session_state["user"] = complete_google_login(str(code))
            st.session_state["oauth_message"] = None
        except (AuthError, DatabaseError) as exc:
            st.session_state["oauth_message"] = str(exc)


def _money(value: Any, currency: str) -> str:
    try:
        return f"{currency} {float(value):,.2f}"
    except (TypeError, ValueError):
        return f"{currency} —"


def _itinerary_markdown(trip: dict[str, Any], itinerary: dict[str, Any]) -> str:
    currency = str(itinerary.get("currency") or trip.get("currency", "USD"))
    lines = [
        f"# Wanderly AI — {trip['destination']}",
        "",
        f"**{trip.get('start_date', '')} · {trip.get('days', len(itinerary.get('days', [])))} days · {trip.get('travelers', 1)} traveler(s) · "
        f"{trip.get('travel_style', 'Personalized')} · Budget {_money(trip.get('budget', 0), currency)}**",
        "",
        str(itinerary.get("trip_summary", "")),
        "",
        f"_Generated with {itinerary.get('generation_mode', 'Wanderly AI')}_",
        "",
    ]
    for day in itinerary.get("days", []):
        day_title = day.get("title") or f"Day {day.get('day', '')}"
        day_weather = day.get("weather")
        lines.extend([f"**Date:** {day.get('date', 'Date unavailable')}", ""])
        if day_weather:
            lines.extend(
                [
                    f"**Weather:** {day_weather['condition']}, {day_weather['temperature']}°C "
                    f"(feels like {day_weather['feels_like']}°C), humidity {day_weather['humidity']}%, "
                    f"wind {day_weather['wind_speed']} m/s.",
                    "",
                ]
            )
        else:
            lines.extend(["**Weather:** Forecast not available for this date.", ""])
        lines.extend([f"## {day_title}", ""])
        for period in ("morning", "afternoon", "evening"):
            activity = day.get(period, {})
            if not isinstance(activity, dict):
                continue
            lines.extend(
                [
                    f"### {period.title()}",
                    f"- **Activity:** {activity.get('activity', 'Explore at your own pace')}",
                    f"- **Place:** {activity.get('place', 'See local recommendations')}",
                    f"- **Address:** {activity.get('place_address') or 'Address unavailable'}",
                    f"- **Coordinates:** {activity.get('latitude')}, {activity.get('longitude')}"
                    if activity.get("latitude") is not None
                    else "- **Coordinates:** unavailable",
                    f"- **Duration:** {activity.get('duration', 'Flexible')}",
                    f"- **Food:** {activity.get('food', 'Explore local cuisine')}",
                    f"- **Transport:** {activity.get('transport', 'Check local transit')}",
                    f"- **Estimated cost:** {_money(activity.get('estimated_cost', 0), currency)}",
                    "",
                ]
            )
    lines.extend(["## Budget breakdown", ""])
    for category, value in itinerary.get("budget_breakdown", {}).items():
        lines.append(f"- **{category.replace('_', ' ').title()}:** {_money(value, currency)}")
    for key, title in (("travel_tips", "Travel tips"), ("safety_tips", "Safety tips")):
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {tip}" for tip in itinerary.get(key, []))
    return "\n".join(lines)


def _render_itinerary(trip: dict[str, Any], itinerary: dict[str, Any]) -> None:
    currency = str(itinerary.get("currency") or trip.get("currency", "USD"))
    st.markdown('<div class="section-title">📋 Your dream trip itinerary</div>', unsafe_allow_html=True)
    if itinerary.get("generation_mode") == "Local fallback":
        st.info("Created with Wanderly's local planner. Add an OpenAI or Gemini key for AI-generated suggestions.")
    else:
        st.success(f"Personalized itinerary generated with {itinerary.get('generation_mode')}.")
    if st.session_state.get("forecast_error"):
        st.caption(f"Daily weather: {st.session_state['forecast_error']}")
    st.write(itinerary.get("trip_summary", ""))
    for day in itinerary.get("days", []):
        title = str(day.get("title") or f"Day {day.get('day', '')}")
        day_date = day.get("date", "")
        title = f"{title} · {day_date}" if day_date else title
        with st.expander(f"🗓️ {title}", expanded=len(itinerary.get("days", [])) == 1):
            day_weather = day.get("weather")
            if day_weather:
                st.info(
                    f"🌤️ Forecast for {day_date}: {day_weather['condition']} · "
                    f"{day_weather['temperature']}°C (feels like {day_weather['feels_like']}°C) · "
                    f"Humidity {day_weather['humidity']}% · Wind {day_weather['wind_speed']} m/s"
                )
            else:
                st.caption(
                    f"🌤️ No OpenWeather forecast is available for {day_date or 'this date'}. "
                    "Forecast data is not invented."
                )
            columns = st.columns(3)
            for col, period, icon in zip(columns, ("morning", "afternoon", "evening"), ("🌅", "☀️", "🌙")):
                details = day.get(period, {})
                if not isinstance(details, dict):
                    details = {}
                with col:
                    st.markdown(
                        f"""<div class="activity"><small>{icon} {html.escape(period)}</small>
<h4>{html.escape(str(details.get('place', 'Explore')))}</h4>
<p>{html.escape(str(details.get('activity', 'Explore at your own pace')))}</p>
<p>⏱️ {html.escape(str(details.get('duration', 'Flexible')))}</p>
<p>🍽️ {html.escape(str(details.get('food', 'Discover local cuisine')))}</p>
<p>🚆 {html.escape(str(details.get('transport', 'Check local options')))}</p>
<p><b>Estimated:</b> {html.escape(_money(details.get('estimated_cost', 0), currency))}</p></div>""",
                        unsafe_allow_html=True,
                    )
                    if details.get("latitude") is not None and details.get("longitude") is not None:
                        st.caption(
                            f"📍 {details.get('place_address', 'Address unavailable')} · "
                            f"{details['latitude']:.5f}, {details['longitude']:.5f}"
                        )
    left, right = st.columns(2)
    with left:
        st.markdown("#### 💸 Budget breakdown")
        breakdown = itinerary.get("budget_breakdown", {})
        if isinstance(breakdown, dict) and breakdown:
            for category, amount in breakdown.items():
                st.write(f"**{str(category).replace('_', ' ').title()}:** {_money(amount, currency)}")
        else:
            st.info("No budget breakdown was returned.")
    with right:
        st.markdown("#### ✨ Travel tips")
        for tip in itinerary.get("travel_tips", []):
            st.write(f"• {tip}")
        st.markdown("#### 🛡️ Safety tips")
        for tip in itinerary.get("safety_tips", []):
            st.write(f"• {tip}")
    md = _itinerary_markdown(trip, itinerary)
    st.download_button(
        "⬇️ Download itinerary",
        data=md,
        file_name=f"wanderly-{''.join(c.lower() if c.isalnum() else '-' for c in trip['destination']).strip('-')}.md",
        mime="text/markdown",
        key="download-current-trip",
    )


def _render_map(destination: str, geocode: dict[str, Any] | None, places: list[dict[str, Any]]) -> None:
    if not geocode:
        st.info(st.session_state.get("map_error") or "Generate a trip to explore its map.")
        return
    token = get_settings().mapbox_access_token
    if not token:
        st.info("Add MAPBOX_ACCESS_TOKEN to .env to display the interactive Mapbox map.")
        st.write(f"**{geocode['name']}** · {geocode['latitude']:.5f}, {geocode['longitude']:.5f}")
        return
    features = [
        {
            "name": item["name"],
            "coordinates": [item["longitude"], item["latitude"]],
        }
        for item in places
    ]
    safe_token = json.dumps(token).replace("<", "\\u003c")
    safe_features = json.dumps(features, ensure_ascii=False).replace("<", "\\u003c")
    map_html = f"""<!DOCTYPE html><html><head>
<meta charset="utf-8"><meta name="viewport" content="initial-scale=1,maximum-scale=1,user-scalable=no">
<link href="https://api.mapbox.com/mapbox-gl-js/v3.9.4/mapbox-gl.css" rel="stylesheet">
<style>body{{margin:0}}#map{{position:absolute;top:0;bottom:0;width:100%;border-radius:16px}}</style></head><body>
<div id="map"></div><script src="https://api.mapbox.com/mapbox-gl-js/v3.9.4/mapbox-gl.js"></script>
<script>
mapboxgl.accessToken={safe_token};
const map=new mapboxgl.Map({{container:'map',style:'mapbox://styles/mapbox/streets-v12',
center:[{float(geocode['longitude'])},{float(geocode['latitude'])}],zoom:11}});
map.addControl(new mapboxgl.NavigationControl());
const places={safe_features};
new mapboxgl.Marker({{color:'#8b52df'}}).setLngLat([{float(geocode['longitude'])},{float(geocode['latitude'])}]).setPopup(new mapboxgl.Popup().setText({json.dumps(str(geocode['name']))})).addTo(map);
places.forEach(place=>{{const marker=new mapboxgl.Marker({{color:'#ff668e'}}).setLngLat(place.coordinates);
const popup=document.createElement('div'); popup.textContent=place.name;
marker.setPopup(new mapboxgl.Popup().setDOMContent(popup)).addTo(map);}});
</script></body></html>"""
    components.html(map_html, height=420, scrolling=False)
    st.caption(f"📍 {geocode['name']} · {geocode['latitude']:.5f}, {geocode['longitude']:.5f}")


def _render_weather(weather: dict[str, Any] | None, message: str | None) -> None:
    if not weather:
        st.info(message or "Generate a trip to see destination weather.")
        return
    cols = st.columns([1, 3])
    with cols[0]:
        st.image(f"https://openweathermap.org/img/wn/{weather['icon']}@2x.png", width=90)
    with cols[1]:
        st.markdown(f"### {weather['temperature']}°C · {weather['condition']}")
        st.caption(f"Feels like {weather['feels_like']}°C in {weather['city']}")
    a, b, c = st.columns(3)
    a.metric("Humidity", f"{weather['humidity']}%")
    b.metric("Wind", f"{weather['wind_speed']} m/s")
    c.metric("Feels like", f"{weather['feels_like']}°C")


def _render_places(
    places: list[dict[str, Any]],
    error: str | None,
    trip: dict[str, Any] | None = None,
    itinerary: dict[str, Any] | None = None,
) -> None:
    if error:
        st.info(error)
        return
    if not places:
        st.info("No live places to show yet. Check your Mapbox configuration or try another destination.")
        return
    schedule: dict[str, list[str]] = {}
    if itinerary:
        for day in itinerary.get("days", []):
            for period in ("morning", "afternoon", "evening"):
                activity = day.get(period, {})
                if isinstance(activity, dict) and activity.get("place"):
                    schedule.setdefault(str(activity["place"]).casefold(), []).append(
                        f"Day {day.get('day', '')} · {day.get('date', '')} · {period.title()}"
                    )
    for place in places:
        planned_dates = schedule.get(str(place["name"]).casefold(), [])
        planning = " · ".join(planned_dates) if planned_dates else "Not scheduled in this itinerary"
        st.markdown(
            f"""<div class="place-card"><h4>📍 {html.escape(str(place['name']))}</h4>
<p>{html.escape(str(place.get('description', 'Place of interest')))} · {html.escape(str(place.get('address', 'Address not provided')))}</p>
<p>Coordinates: {float(place['latitude']):.5f}, {float(place['longitude']):.5f}</p>
<p>🗓️ {html.escape(planning)}</p></div>""",
            unsafe_allow_html=True,
        )


def _auth_screen() -> None:
    st.markdown('<div class="auth-wrap">', unsafe_allow_html=True)
    left, right = st.columns([1.05, 1])
    with left:
        st.markdown('<div class="auth-logo">✈️ Wanderly AI</div>', unsafe_allow_html=True)
        st.markdown("### Plan unforgettable journeys with AI.")
        st.markdown(
            "Your colorful AI travel companion. Discover places, check the weather, "
            "and turn your next big idea into a day-by-day plan."
        )
        st.markdown("🌍 Thoughtful itineraries  ·  🎨 Your travel style  ·  📍 Real places")
        st.markdown(
            '<div class="hero" style="margin-top:1.3rem"><div class="eyebrow">YOUR NEXT CHAPTER</div>'
            '<h1>Wander further.<br>Wonder more.</h1><p>Big trip energy, made easy.</p></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown("### Welcome to Wanderly")
        tabs = st.tabs(["Log in", "Create account", "Forgot password"])
        with tabs[0]:
            with st.form("login-form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in to Wanderly", use_container_width=True)
            if submitted:
                try:
                    st.session_state["user"] = login(email, password)
                    st.rerun()
                except (AuthError, DatabaseError) as exc:
                    st.error(str(exc))
            try:
                state = st.session_state.get("oauth_state")
                if not state:
                    state = secrets.token_urlsafe(32)
                    st.session_state["oauth_state"] = state
                url = google_authorization_url(state)
                st.link_button("Continue with Google", url, use_container_width=True)
            except AuthError as exc:
                st.info(str(exc))
            message = st.session_state.pop("oauth_message", None)
            if message:
                st.error(message)
        with tabs[1]:
            with st.form("signup-form"):
                name = st.text_input("Your name")
                email = st.text_input("Email address", placeholder="you@example.com", key="signup-email")
                password = st.text_input("Password", type="password", key="signup-password")
                confirmation = st.text_input("Confirm password", type="password")
                submitted = st.form_submit_button("Create my account", use_container_width=True)
            if submitted:
                if password != confirmation:
                    st.error("Those passwords don't match.")
                else:
                    try:
                        st.session_state["user"] = create_account(name, email, password)
                        st.success("Your account is ready!")
                        st.rerun()
                    except (AuthError, DatabaseError) as exc:
                        st.error(str(exc))
        with tabs[2]:
            st.caption("Reset links are single-use and expire after 30 minutes.")
            with st.form("forgot-form"):
                email = st.text_input("Account email", placeholder="you@example.com", key="forgot-email")
                submitted = st.form_submit_button("Create reset link", use_container_width=True)
            if submitted:
                try:
                    token = create_password_reset(email)
                    if token:
                        st.session_state["reset_token"] = token
                        st.success("Local demo reset link created. Copy the one-time token below to reset your password.")
                    else:
                        st.info("If an account exists for that address, a reset link can be issued by the configured email service.")
                except (AuthError, DatabaseError) as exc:
                    st.error(str(exc))
            reset_token = st.session_state.get("reset_token")
            if reset_token:
                st.code(reset_token)
                with st.form("reset-form"):
                    entered_token = st.text_input("One-time reset token", value=reset_token)
                    new_password = st.text_input("New password", type="password")
                    submitted = st.form_submit_button("Set new password", use_container_width=True)
                if submitted:
                    try:
                        reset_password(entered_token, new_password)
                        st.session_state["reset_token"] = None
                        st.success("Password updated. Log in with your new password.")
                    except (AuthError, DatabaseError) as exc:
                        st.error(str(exc))
    st.markdown("</div>", unsafe_allow_html=True)


def _fetch_trip_context(trip: dict[str, Any]) -> None:
    location = ", ".join(
        part for part in (trip["destination"], trip.get("state", ""), trip.get("country", "")) if part
    )
    try:
        st.session_state["weather"] = get_current_weather(
            trip["destination"], trip.get("country", "")
        )
        st.session_state["weather_error"] = None
    except WeatherError as exc:
        st.session_state["weather"] = None
        st.session_state["weather_error"] = str(exc)
    try:
        st.session_state["forecast_by_date"] = get_daily_forecast(
            trip["destination"],
            trip.get("country", ""),
            trip["start_date"],
            int(trip["days"]),
        )
        st.session_state["forecast_error"] = None
    except WeatherError as exc:
        st.session_state["forecast_by_date"] = {}
        st.session_state["forecast_error"] = str(exc)
    try:
        geocode = geocode_destination(location)
        st.session_state["geocode"] = geocode
        st.session_state["map_error"] = None
    except MapServiceError as exc:
        geocode = None
        st.session_state["geocode"] = None
        st.session_state["map_error"] = str(exc)
    try:
        st.session_state["places"] = get_places(trip["destination"])
        st.session_state["places_error"] = None
    except MapServiceError as exc:
        st.session_state["places"] = []
        st.session_state["places_error"] = str(exc)


def _planner_page(user: dict[str, Any]) -> None:
    st.markdown(
        f"""<div class="hero"><div class="eyebrow">YOUR COLORFUL AI TRAVEL COMPANION</div>
<h1>Hey {html.escape(user['name'].split()[0])}, where to next?</h1>
<p>Tell us what makes your perfect trip. We'll help turn the daydream into a plan.</p></div>""",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="section-title">🌈 Create your dream trip</div>', unsafe_allow_html=True)
    st.markdown('<p class="subtle">A few details are all it takes to start planning.</p>', unsafe_allow_html=True)
    styles = ["Budget", "Relaxed", "Adventure", "Luxury", "Family", "Romantic", "Culture & Food"]
    interests = [
        "Beaches", "Temples", "Shopping", "Food", "Nature", "Museums", "Nightlife",
        "Adventure", "Architecture", "History", "Wellness", "Photography",
    ]
    with st.form("trip-planner-form"):
        first, second = st.columns(2)
        with first:
            name = st.text_input("Your name", value=user["name"])
            destination = st.text_input("Destination city or place", placeholder="e.g. Kyoto")
            country = st.text_input("Country (optional)", placeholder="e.g. Japan")
            state = st.text_input("State / Region (optional)", placeholder="e.g. Kyoto Prefecture")
        with second:
            budget = st.number_input("Total budget", min_value=1.0, value=1500.0, step=100.0)
            currency = st.selectbox("Currency", ["USD", "EUR", "GBP", "INR", "CAD", "AUD", "JPY", "SGD"])
            start_date = st.date_input("Trip start date", value=date.today())
            days = st.number_input("Number of days", min_value=1, max_value=30, value=5)
            travelers = st.number_input("Number of travelers", min_value=1, max_value=20, value=2)
        style_col, interests_col = st.columns(2)
        with style_col:
            travel_style = st.selectbox("Travel style", styles)
        with interests_col:
            selected_interests = st.multiselect(
                "Interests", interests, default=["Food", "Nature"]
            )
        submitted = st.form_submit_button("🌈 CREATE MY DREAM TRIP", use_container_width=True)
    if submitted:
        try:
            trip = validate_trip(
                {
                    "name": name, "destination": destination, "country": country,
                    "state": state, "budget": budget, "currency": currency,
                    "start_date": start_date,
                    "days": days, "travelers": travelers, "travel_style": travel_style,
                    "interests": selected_interests,
                }
            )
        except TripValidationError as exc:
            st.error(str(exc))
            trip = None
        if trip:
            with st.spinner("Finding destination details and designing your journey…"):
                _fetch_trip_context(trip)
                try:
                    itinerary = generate_itinerary(
                        trip,
                        st.session_state["weather"],
                        st.session_state["places"],
                        st.session_state["forecast_by_date"],
                    )
                except PlannerError as exc:
                    st.error(str(exc))
                    itinerary = None
                if itinerary:
                    st.session_state["trip"] = trip
                    st.session_state["itinerary"] = itinerary
                    try:
                        trip_id = save_trip(user["id"], trip, itinerary)
                        st.session_state["saved_trip_id"] = trip_id
                        st.success("Your itinerary is ready and saved in My Trips.")
                    except TripError as exc:
                        st.warning(str(exc))
                        st.session_state["saved_trip_id"] = None

    trip = st.session_state.get("trip")
    itinerary = st.session_state.get("itinerary")
    if trip and itinerary:
        st.divider()
        summary_cols = st.columns(4)
        summary_cols[0].metric("📍 Destination", trip["destination"])
        summary_cols[1].metric("🗓️ Dates", f"{trip['start_date']} · {trip['days']} days")
        summary_cols[2].metric("👥 Travelers", trip["travelers"])
        summary_cols[3].metric("💰 Total budget", _money(trip["budget"], trip["currency"]))
        weather_col, map_col = st.columns([1, 1.5])
        with weather_col:
            st.markdown('<div class="section-title">🌤️ Live weather</div>', unsafe_allow_html=True)
            _render_weather(st.session_state["weather"], st.session_state["weather_error"])
        with map_col:
            st.markdown('<div class="section-title">🗺️ Explore the map</div>', unsafe_allow_html=True)
            _render_map(trip["destination"], st.session_state["geocode"], st.session_state["places"])
        st.markdown('<div class="section-title">📍 Places to explore</div>', unsafe_allow_html=True)
        _render_places(
            st.session_state["places"],
            st.session_state["places_error"],
            trip,
            itinerary,
        )
        _render_itinerary(trip, itinerary)


def _places_page() -> None:
    st.markdown('<div class="hero"><div class="eyebrow">THE GOOD STUFF, FOUND</div><h1>Places to explore</h1><p>Live points of interest from Mapbox, centered around your destination.</p></div>', unsafe_allow_html=True)
    trip = st.session_state.get("trip")
    if not trip:
        st.info("Create a trip in Trip Planner to discover real nearby places.")
        return
    st.markdown(f"#### ✨ Around {trip['destination']}")
    _render_places(
        st.session_state["places"],
        st.session_state["places_error"],
        trip,
        st.session_state.get("itinerary"),
    )


def _map_page() -> None:
    st.markdown('<div class="hero"><div class="eyebrow">PLOT YOUR NEXT ADVENTURE</div><h1>Explore the map</h1><p>Browse your destination and real nearby places.</p></div>', unsafe_allow_html=True)
    trip = st.session_state.get("trip")
    if not trip:
        st.info("Create a trip in Trip Planner to see a Mapbox map.")
        return
    _render_map(trip["destination"], st.session_state["geocode"], st.session_state["places"])


def _weather_page() -> None:
    st.markdown('<div class="hero"><div class="eyebrow">PACK SMART, TRAVEL HAPPY</div><h1>Destination weather</h1><p>Current conditions from OpenWeather for your planned destination.</p></div>', unsafe_allow_html=True)
    trip = st.session_state.get("trip")
    if not trip:
        st.info("Create a trip in Trip Planner to see destination weather.")
        return
    _render_weather(st.session_state["weather"], st.session_state["weather_error"])
    st.markdown("### 🌦️ Weather on your travel dates")
    forecast = st.session_state.get("forecast_by_date", {})
    for offset in range(int(trip["days"])):
        forecast_date = (
            date.fromisoformat(trip["start_date"]) + timedelta(days=offset)
        ).isoformat()
        day_weather = forecast.get(forecast_date)
        if not day_weather:
            st.info(
                f"**{forecast_date}:** No forecast is available. OpenWeather provides only a "
                "limited forward forecast; past and farther-out dates are not predicted here."
            )
            continue
        with st.container(border=True):
            left, middle, right = st.columns([1, 3, 2])
            with left:
                st.image(
                    f"https://openweathermap.org/img/wn/{day_weather['icon']}@2x.png",
                    width=72,
                )
            with middle:
                st.markdown(
                    f"**{forecast_date} · {day_weather['condition']}**  \n"
                    f"{day_weather['temperature']}°C · feels like {day_weather['feels_like']}°C"
                )
            with right:
                st.caption(
                    f"Low {day_weather['min_temperature']}° · High {day_weather['max_temperature']}°  \n"
                    f"Humidity {day_weather['humidity']}% · Wind {day_weather['wind_speed']} m/s"
                )


def _trips_page(user: dict[str, Any]) -> None:
    st.markdown('<div class="hero"><div class="eyebrow">THE JOURNEYS YOU DREAMED UP</div><h1>My trips</h1><p>Pick up a saved itinerary or revisit the places you planned to explore.</p></div>', unsafe_allow_html=True)
    try:
        trips = list_trips(user["id"])
    except TripError as exc:
        st.error(str(exc))
        return
    if not trips:
        st.info("No trips saved yet. Your first adventure is one plan away.")
        if st.button("Plan my first trip"):
            st.session_state["view"] = "🧭 Trip Planner"
            st.rerun()
        return
    for trip_row in trips:
        columns = st.columns([4, 1, 1])
        with columns[0]:
            st.markdown(
                f"### 🌍 {trip_row['destination']}, {trip_row['country']}\n"
                f"{trip_row['days']} days · {trip_row['travel_style']} · "
                f"Starts {trip_row['start_date']} · "
                f"{_money(trip_row['budget'], trip_row['currency'])} · "
                f"Saved {trip_row['created_at']}"
            )
        with columns[1]:
            if st.button("Open trip", key=f"open-trip-{trip_row['id']}"):
                try:
                    saved = get_trip(user["id"], trip_row["id"])
                    if saved:
                        st.session_state["trip"] = {
                            "name": user["name"],
                            "destination": saved["destination"],
                            "country": saved["country"],
                            "state": saved["state"],
                            "budget": saved["budget"],
                            "currency": saved["currency"],
                            "start_date": saved["start_date"],
                            "days": saved["days"],
                            "travelers": saved["travelers"],
                            "travel_style": saved["travel_style"],
                            "interests": saved["interests"],
                        }
                        st.session_state["itinerary"] = saved["itinerary"]
                        st.session_state["saved_trip_id"] = saved["id"]
                        _fetch_trip_context(st.session_state["trip"])
                        st.session_state["itinerary"] = enrich_itinerary(
                            st.session_state["trip"],
                            st.session_state["itinerary"],
                            st.session_state["places"],
                            st.session_state["forecast_by_date"],
                        )
                        st.session_state["view"] = "🧭 Trip Planner"
                        st.rerun()
                    st.warning("That saved trip is no longer available.")
                except TripError as exc:
                    st.error(str(exc))
        with columns[2]:
            if st.button("Delete", key=f"delete-trip-{trip_row['id']}", type="secondary"):
                try:
                    delete_trip(user["id"], trip_row["id"])
                    st.success("Trip deleted.")
                    st.rerun()
                except TripError as exc:
                    st.error(str(exc))
        st.divider()


def _settings_page(user: dict[str, Any]) -> None:
    st.markdown('<div class="hero"><div class="eyebrow">YOUR WANDERLY SPACE</div><h1>Settings</h1><p>Your account and connected travel services.</p></div>', unsafe_allow_html=True)
    st.markdown("### 👤 Account")
    st.write(f"**Name:** {user['name']}")
    st.write(f"**Email:** {user['email']}")
    settings = get_settings()
    st.markdown("### 🔌 Integrations")
    configured = [
        ("OpenWeather", bool(settings.openweather_api_key)),
        ("Mapbox", bool(settings.mapbox_access_token)),
        ("OpenAI", bool(settings.openai_api_key)),
        ("Gemini", bool(settings.gemini_api_key)),
        ("Google OAuth", bool(settings.google_client_id and settings.google_client_secret)),
    ]
    for name, is_configured in configured:
        st.write(f"{'✅' if is_configured else '⚪'} **{name}:** {'Connected' if is_configured else 'Not configured'}")
    st.caption("Add keys to .env and restart Streamlit. Values are never displayed here.")
    st.markdown("### 🔒 Local account")
    st.info("Passwords are stored as bcrypt hashes. App sessions live in the current browser session.")


def main() -> None:
    _consume_query_params()
    user = st.session_state.get("user")
    if not user:
        _auth_screen()
        return

    with st.sidebar:
        st.markdown('<div class="brand">✈️ <span>Wanderly AI</span></div>', unsafe_allow_html=True)
        st.markdown('<div class="tagline">Plan unforgettable journeys with AI.</div>', unsafe_allow_html=True)
        st.divider()
        st.markdown(f"Hi, **{user['name'].split()[0]}** 👋")
        menu = [
            "🧭 Trip Planner", "🌍 Places", "🗺️ Map", "🌤️ Weather",
            "📋 My Trips", "⚙️ Settings",
        ]
        current = st.session_state.get("view", menu[0])
        selected_index = menu.index(current) if current in menu else 0
        selected = st.radio("Explore", menu, index=selected_index, label_visibility="collapsed")
        st.session_state["view"] = selected
        st.divider()
        if st.button("🚪 Log out", use_container_width=True, type="secondary"):
            for key in ("user", "trip", "itinerary", "weather", "weather_error", "geocode",
                        "forecast_by_date", "forecast_error", "map_error", "places",
                        "places_error", "saved_trip_id", "oauth_state"):
                st.session_state[key] = {} if key == "forecast_by_date" else (
                    [] if key == "places" else None
                )
            st.session_state["view"] = menu[0]
            st.rerun()
        st.caption("Made for big plans and happy detours. ✨")

    if selected == "🧭 Trip Planner":
        _planner_page(user)
    elif selected == "🌍 Places":
        _places_page()
    elif selected == "🗺️ Map":
        _map_page()
    elif selected == "🌤️ Weather":
        _weather_page()
    elif selected == "📋 My Trips":
        _trips_page(user)
    elif selected == "⚙️ Settings":
        _settings_page(user)


main()
