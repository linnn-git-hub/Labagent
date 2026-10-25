from typing import Dict, Any
import httpx
from schemas import WebFetchArgs, GetWeatherResult


async def get_weather(args: Dict[str, Any]):
    """Get weather for a location string using Open-Meteo geocoding + forecast."""
    if isinstance(args, dict):
        parsed = WebFetchArgs(**args)
    else:
        parsed = args

    location = parsed.location
    # geocode via open-meteo
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(geo_url, params={"name": location, "count": 1})
        if r.status_code != 200:
            return {"error": "geocoding failed", "raw": r.text}
        data = r.json()
        if not data.get("results"):
            return {"error": "location not found", "location": location}
        first = data["results"][0]
        lat = first["latitude"]
        lon = first["longitude"]

        # call simple current weather
        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {"latitude": lat, "longitude": lon, "current_weather": True, "timezone": "UTC"}
        wr = await client.get(weather_url, params=params)
        if wr.status_code != 200:
            return {"error": "weather fetch failed", "raw": wr.text}
        wdata = wr.json()
        current = wdata.get("current_weather", {})
        temp = current.get("temperature")
        summary = f"Current temperature at {first.get('name')} is {temp}° ({current.get('weathercode')})."
        result = GetWeatherResult(location=first.get("name"), latitude=lat, longitude=lon, temperature=temp, summary=summary, raw=wdata)
        return result.dict()
