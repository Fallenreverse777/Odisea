"""Weather rules, using Open-Meteo (free, no API key, no sign-up)."""


from __future__ import annotations
import json
import urllib.parse
import urllib.request

from .memory import Memory

GEOCODE = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST = "https://api.open-meteo.com/v1/forecast"

# Open-Meteo weather codes -> words
CODES = {
    0: "clear skies", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "foggy", 51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "freezing drizzle", 61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain", 71: "light snow", 73: "snow", 75: "heavy snow",
    77: "snow grains", 80: "rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers", 95: "a thunderstorm",
    96: "a thunderstorm with hail", 99: "a thunderstorm with hail",
}


class WeatherError(Exception):
    pass


def _get(url: str, params: dict) -> dict:
    full = f"{url}?{urllib.parse.urlencode(params)}"
    try:
        with urllib.request.urlopen(full, timeout=10) as res:
            return json.load(res)
    except OSError as e:
        raise WeatherError("I can't reach the weather service right now. Are you online?") from e


def find_place(name: str) -> dict | None:
    results = _get(GEOCODE, {"name": name, "count": 1}).get("results")
    return results[0] if results else None


def forecast(place: dict) -> dict:
    data = _get(FORECAST, {
        "latitude": place["latitude"], "longitude": place["longitude"],
        "current": "temperature_2m,weather_code",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto", "forecast_days": 2,
    })
    if data.get("error"):
        raise WeatherError(f"The weather service said: {data.get('reason', 'error')}")
    return data


def _place_for(m, mem: Memory) -> dict | str:
    """The place asked about, or the user's home city. A string means an error reply."""
    city = (m.groupdict().get("city") or "").strip(" ?.!")
    if not city:
        city = mem.get("city")
        if not city:
            return "Which city? Tell me 'I live in ...' and I'll remember it."
    place = find_place(city)
    if not place:
        return f"I couldn't find a place called {city.title()}."
    return place


def weather(m, text, mem: Memory):
    try:
        place = _place_for(m, mem)
        if isinstance(place, str):
            return place
        data = forecast(place)
    except WeatherError as e:
        return str(e)

    daily = data["daily"]
    day = 1 if "tomorrow" in text else 0
    sky = CODES.get(daily["weather_code"][day], "mixed weather")
    high, low = round(daily["temperature_2m_max"][day]), round(daily["temperature_2m_min"][day])
    rain = daily["precipitation_probability_max"][day]
    name = place["name"]

    if day == 0:
        now = data["current"]
        reply = (f"Right now in {name}: {round(now['temperature_2m'])}°C, "
                 f"{CODES.get(now['weather_code'], 'mixed weather')}. Today: {low}–{high}°C.")
    else:
        reply = f"Tomorrow in {name}: {sky}, {low}–{high}°C."

    if rain is not None and rain >= 50:
        reply += f" {rain}% chance of rain, so take an umbrella."
    elif rain is not None and rain >= 20:
        reply += f" Small chance of rain ({rain}%)."
    return reply


def set_city(m, text, mem: Memory):
    city = m.group("city").strip(" .!")
    try:
        place = find_place(city)
    except WeatherError:
        place = None
    name = place["name"] if place else city.title()
    mem.set("city", name)
    return f"{name}, got it. Now just ask 'what's the weather?'"


WEATHER_RULES = [
    (r"^(i live in|i'?m from|my city is) (?P<city>[a-z][a-z .'-]{1,40})$", set_city),
    (r"\b(weather|temperature|forecast|rain|raining|umbrella)\b.*?(\bin (?P<city>[a-z][a-z .'-]{1,40}?))?\??$", weather),
]
