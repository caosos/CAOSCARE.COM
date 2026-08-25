"""Weather router — current conditions + short forecast for the AI tool.

Backed by Open-Meteo (https://open-meteo.com), a fully free no-key weather
API. Default location comes from FACILITY_LAT / FACILITY_LON / FACILITY_LABEL
in `.env`; the AI tool can override per call (e.g., "what's the weather in
Boston where my daughter lives?").

Returns a SHORT spoken-friendly summary because the AI just reads the
`narrative` aloud — no need to expose tabular data.
"""
import os
import logging
import httpx
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from routes.realtime_facility import get_active_facility

router = APIRouter(prefix="/weather", tags=["weather"])
logger = logging.getLogger(__name__)

# Env fallback only - preferred source is the live facility record's own
# lat/lon/name (2026-08-25: no FACILITY_LAT/LON were ever set, so this
# fallback silently served Pennsylvania-area coordinates for a facility
# actually in Conway, Arkansas; see get_active_facility() below).
DEFAULT_LAT = float(os.environ.get("FACILITY_LAT") or 40.0379)
DEFAULT_LON = float(os.environ.get("FACILITY_LON") or -76.3055)
DEFAULT_LABEL = os.environ.get("FACILITY_LABEL") or "the facility"
DEFAULT_TZ = os.environ.get("FACILITY_TZ") or "America/New_York"

# Open-Meteo "weather code" -> short human phrase. Drawn from WMO 4677.
# Kept compact so the spoken sentence stays short.
WEATHER_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow flurries",
    80: "rain showers", 81: "rain showers", 82: "heavy rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail", 99: "severe thunderstorms",
}


class WeatherSnapshot(BaseModel):
    label: str
    temperature_f: float
    feels_like_f: Optional[float] = None
    condition: str
    high_f: Optional[float] = None
    low_f: Optional[float] = None
    chance_of_rain: Optional[int] = None
    narrative: str   # the line CAOS speaks aloud


def _c_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 0)


async def _geocode(name: str) -> tuple[float, float, str] | None:
    """Resolve a free-form city name to (lat, lon, resolved_label) via
    Open-Meteo's free geocoding API. Returns None if not found. Used so the
    AI tool can say 'weather in Boston' and we actually look up Boston —
    not just relabel the facility's weather."""
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            r = await client.get(
                "https://geocoding-api.open-meteo.com/v1/search",
                params={"name": name, "count": 1, "language": "en", "format": "json"},
            )
            r.raise_for_status()
            results = (r.json() or {}).get("results") or []
            if not results:
                return None
            top = results[0]
            label_parts = [top.get("name"), top.get("admin1"), top.get("country_code")]
            label = ", ".join([p for p in label_parts if p])
            return float(top["latitude"]), float(top["longitude"]), label or name
    except Exception as e:
        logger.warning(f"geocode fail for '{name}': {e}")
        return None


async def current_weather(
    lat: float = DEFAULT_LAT,
    lon: float = DEFAULT_LON,
    label: str = DEFAULT_LABEL,
) -> WeatherSnapshot:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,weather_code,precipitation",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "temperature_unit": "celsius",
        "timezone": DEFAULT_TZ,
        "forecast_days": 1,
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)
        r.raise_for_status()
        data = r.json()

    cur = data.get("current") or {}
    daily = data.get("daily") or {}
    temp_f = _c_to_f(cur.get("temperature_2m") or 0)
    feels_f = _c_to_f(cur.get("apparent_temperature") or cur.get("temperature_2m") or 0)
    code = int(cur.get("weather_code") or 0)
    condition = WEATHER_CODES.get(code, "")
    high_f = _c_to_f((daily.get("temperature_2m_max") or [None])[0]) if daily.get("temperature_2m_max") else None
    low_f = _c_to_f((daily.get("temperature_2m_min") or [None])[0]) if daily.get("temperature_2m_min") else None
    pop = (daily.get("precipitation_probability_max") or [None])[0]

    # Build a calm, spoken narrative. Mention rain probability only if it's
    # meaningful (>= 30%) so we don't overload the resident with stats.
    parts = []
    parts.append(f"It's {int(temp_f)} degrees")
    if condition:
        parts.append(f"and {condition}")
    parts.append(f"around {label}")
    if high_f is not None and low_f is not None:
        parts.append(f"— a high of {int(high_f)} and a low of {int(low_f)} today")
    if pop is not None and pop >= 30:
        parts.append(f"with about a {int(pop)} percent chance of precipitation")
    narrative = " ".join(parts).rstrip(", ") + "."
    # Light cleanup — collapse double spaces, ensure single period
    narrative = " ".join(narrative.split())

    return WeatherSnapshot(
        label=label,
        temperature_f=temp_f,
        feels_like_f=feels_f,
        condition=condition or "no data",
        high_f=high_f,
        low_f=low_f,
        chance_of_rain=int(pop) if pop is not None else None,
        narrative=narrative,
    )


@router.get("/current", response_model=WeatherSnapshot)
async def get_current_weather(
    lat: Optional[float] = Query(None),
    lon: Optional[float] = Query(None),
    label: Optional[str] = Query(None),
):
    """Public endpoint — used by the kiosk Realtime tool dispatcher.
    If both lat and lon are provided they take precedence. If only `label` is
    given, we geocode it (free Open-Meteo geocoding API). Otherwise we use
    the live facility record's own coordinates/name when set, falling back
    to .env, then the hardcoded default."""
    try:
        if lat is None and lon is None and label:
            geo = await _geocode(label)
            if geo:
                lat, lon, label = geo
        facility_lat, facility_lon, facility_label = DEFAULT_LAT, DEFAULT_LON, DEFAULT_LABEL
        if lat is None and lon is None:
            facility = await get_active_facility()
            if facility and facility.get("lat") is not None and facility.get("lon") is not None:
                facility_lat, facility_lon = facility["lat"], facility["lon"]
                place = ", ".join(p for p in [facility.get("city"), facility.get("state")] if p)
                facility_label = place or facility.get("name") or DEFAULT_LABEL
        return await current_weather(
            lat=lat if lat is not None else facility_lat,
            lon=lon if lon is not None else facility_lon,
            label=label or facility_label,
        )
    except Exception as e:
        logger.error(f"weather error: {e}")
        raise HTTPException(status_code=502, detail=f"Weather fetch failed: {e}")
