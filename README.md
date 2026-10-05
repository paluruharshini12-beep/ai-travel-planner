# Wanderly AI — AI Travel Planner

Wanderly AI is a local-first travel planning app built with Streamlit and SQLite. Create an account, describe a trip, and generate a multi-day itinerary using OpenAI or Gemini. If neither AI key is configured, a clearly labeled local itinerary generator keeps the planner usable. Live weather and destination/places data are available through OpenWeather and Mapbox when configured.

## Features

- Email/password signup and login with bcrypt password hashing
- Optional Google OAuth 2.0 sign-in
- One-time, expiring password reset flow for local demonstrations
- Trip planning by destination, optional country/region, start date, budget, currency, duration, group size, style, and interests
- OpenAI or Gemini itinerary generation, with a practical local fallback
- Budget breakdown, day-by-day morning/afternoon/evening plans, food, transport, duration, costs, and safety/travel tips
- Current OpenWeather conditions plus real 5-day/3-hour forecasts aggregated by travel date; dates outside the provider forecast window are explicitly marked unavailable
- Real points of interest from multiple Mapbox Search Box categories, with address, coordinates, and scheduled itinerary date; country/region are optional and do not bound POI search
- Mapbox geocoding and an interactive destination map
- Save, open, download, and delete trips in a user-scoped SQLite database
- Responsive, colorful Streamlit interface; missing external services do not prevent local itinerary planning

## Technologies

Python 3.10+, Streamlit, SQLite, bcrypt, Requests, python-dotenv, OpenAI Chat Completions API, Google Gemini REST API, OpenWeather API, and Mapbox Geocoding/Search Box APIs.

## Folder structure

```text
ai-travel-planner/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
├── src/
│   ├── __init__.py
│   ├── config.py
│   ├── database.py
│   ├── auth.py
│   ├── ai_planner.py
│   ├── weather.py
│   ├── maps.py
│   ├── places.py
│   ├── trips.py
│   └── planner.py
├── assets/
│   ├── logo.png
│   └── .gitkeep
└── screenshots/
    └── .gitkeep
```

## Windows setup

Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/) and enable the Python launcher/PATH option. In PowerShell, change to the project folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

If PowerShell blocks virtual-environment activation, allow it for the current process only, then activate:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

The database is created automatically at `data/wanderly.db` on first launch. It can be changed with `DATABASE_PATH`.

## Environment variables and API keys

Copy `.env.example` to `.env` and fill only the integrations you want. No key is needed to use accounts, saved trips, or the local itinerary mode.

| Variable | Purpose |
| --- | --- |
| `OPENWEATHER_API_KEY` | Current destination weather |
| `MAPBOX_ACCESS_TOKEN` | Geocoding, places search, and interactive map |
| `OPENAI_API_KEY` | Optional AI itinerary generation (takes priority if both AI keys are set) |
| `GEMINI_API_KEY` | Optional Google Gemini itinerary generation |
| `GOOGLE_CLIENT_ID` | Optional Google OAuth web client ID |
| `GOOGLE_CLIENT_SECRET` | Optional Google OAuth web client secret |
| `GOOGLE_REDIRECT_URI` | OAuth callback; local default is `http://localhost:8501` |
| `DATABASE_PATH` | Optional SQLite file path; default is `data/wanderly.db` |

Obtain credentials from the providers' official dashboards. In Google Cloud Console, enable Google Identity/OAuth, configure the consent screen, and add `http://localhost:8501` as an authorized redirect URI. The application performs the OAuth authorization-code flow and requires both Google credentials. Restrict API keys to the required APIs and, where supported, to your application.

When adding secrets, stop and restart Streamlit so the `.env` values are reloaded.

## Running the application

Run `streamlit run app.py`, then open the local URL Streamlit prints (normally `http://localhost:8501`). Create an account or optionally use configured Google sign-in. Choose a destination, generate a trip, and use the sidebar to open the weather, map, places, saved trips, and settings views. The itinerary can be downloaded as Markdown from its download button.

Google sign-in callback state is checked against the browser session. The local password reset demonstration displays a single-use link in the app because no email-delivery provider is configured; do not deploy that reset flow publicly without replacing it with verified email delivery.

## Troubleshooting

- **`streamlit` is not recognized:** activate `.venv` and run `python -m streamlit run app.py`.
- **Package installation fails:** upgrade pip with `python -m pip install --upgrade pip`, then retry the requirements installation.
- **Live weather, map, or places is unavailable:** confirm the relevant key in `.env`, API activation, quotas, and destination spelling. The app gives provider-specific status messages.
- **AI request fails:** check the configured key, provider account/model access, quota, and network connection. If no AI key is present, local fallback generation is automatic.
- **Database error:** ensure the project/data directory is writable and `DATABASE_PATH` points to a valid local file.
- **Google redirect mismatch:** the Google Console redirect URI must exactly match `GOOGLE_REDIRECT_URI`, including protocol, port, and trailing path.
- **Port is busy:** run `streamlit run app.py --server.port 8502` and set the matching Google OAuth redirect URI if using Google sign-in.

## Security notes

- `.env`, database files, and Streamlit secrets are excluded by `.gitignore`; never commit credentials or a real `.env`.
- Passwords are hashed using bcrypt. Password reset tokens are random, stored only as hashes, expire after 30 minutes, and can be used once.
- Local sessions use Streamlit's per-browser session state and are not a replacement for a production identity/session service.
- The password reset link is shown in the app for local demonstration only; configure email delivery before public deployment.
- Mapbox access tokens used by browser map rendering are visible to the browser. Use a public token restricted by URL and required scopes; never put server-side secret tokens in this setting.
- Use HTTPS, managed secret storage, database backups, rate limiting, and provider key restrictions before deployment.

## Deployment

For a demonstration, run the app on a trusted local machine. For hosting, deploy the Streamlit application to a platform that supports persistent storage, HTTPS, and secret management. Set environment variables through the host's secret manager (not a committed `.env`), provision durable storage for the SQLite database, set an externally reachable HTTPS OAuth redirect URI, restrict keys, and replace the local reset-token display with secure email delivery. SQLite is intended for local/small single-instance usage; use a managed database for concurrent or horizontally scaled deployments.
