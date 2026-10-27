import os
from typing import Dict, Any

import httpx

from schemas import WebFetchArgs, GetWeatherResult

DEFAULT_GAODE_MAP_API_KEY = "50cf9bea928ded7a8e7986717a000cc1"


def _gaode_key() -> str:
    return (
        os.getenv("GAODE_MAP_API_KEY")
        or os.getenv("GAODE_MAP_KEY")
        or os.getenv("AMAP_KEY")
        or os.getenv("MAP_KEY")
        or DEFAULT_GAODE_MAP_API_KEY
    )


async def get_weather(args: Dict[str, Any]):
    """Get weather for a location string using Gaode when configured, otherwise use Open-Meteo as a working fallback."""
    if isinstance(args, dict):
        parsed = WebFetchArgs(**args)
    else:
        parsed = args

    location = parsed.location
    api_key = _gaode_key()

    if api_key:
        geo_url = "https://restapi.amap.com/v3/geocode/geo"
        async with httpx.AsyncClient(timeout=20) as client:
            geo_resp = await client.get(geo_url, params={"key": api_key, "address": location})
            if geo_resp.status_code != 200:
                return {"error": "geocoding failed", "raw": geo_resp.text}

            geo_data = geo_resp.json()
            if geo_data.get("status") != "1":
                return {"error": geo_data.get("info", "location not found"), "location": location}

            geocodes = geo_data.get("geocodes") or []
            if not geocodes:
                return {"error": "location not found", "location": location}

            first = geocodes[0]
            location_name = first.get("formatted_address") or location
            loc = first.get("location", "")
            if not loc:
                return {"error": "location missing coordinates", "location": location}

            lng, lat = map(float, loc.split(","))
            adcode = first.get("adcode")

            weather_url = "https://restapi.amap.com/v3/weather/weatherInfo"
            weather_params = {"key": api_key, "city": adcode or location, "extensions": "base"}
            weather_resp = await client.get(weather_url, params=weather_params)
            if weather_resp.status_code != 200:
                return {"error": "weather fetch failed", "raw": weather_resp.text}

            weather_data = weather_resp.json()
            forecasts = weather_data.get("lives") or []
            if not forecasts:
                return {"error": "weather data not found", "location": location_name, "raw": weather_data}

            current = forecasts[0]
            temp = current.get("temperature")
            weather = current.get("weather")
            wind_speed = current.get("windpower")
            humidity = current.get("humidity")
            summary = (
                f"{location_name} 当前天气：{weather}，温度 {temp}°C，湿度 {humidity}%，风力 {wind_speed}."
            )

            result = GetWeatherResult(
                location=location_name,
                latitude=lat,
                longitude=lng,
                temperature=float(temp) if temp not in (None, "") else None,
                summary=summary,
                raw=weather_data,
            )
            return result.dict()

    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    async with httpx.AsyncClient(timeout=20) as client:
        geo_resp = await client.get(geo_url, params={"name": location, "count": 1})
        if geo_resp.status_code != 200:
            return {"error": "geocoding failed", "raw": geo_resp.text}
        geo_data = geo_resp.json()
        results = geo_data.get("results") or []
        if not results:
            return {"error": "location not found", "location": location}

        first = results[0]
        lat = float(first["latitude"])
        lng = float(first["longitude"])
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_resp = await client.get(
            weather_url,
            params={
                "latitude": lat,
                "longitude": lng,
                "current_weather": True,
                "forecast_days": 2,
                "timezone": "auto",
            },
        )
        if weather_resp.status_code != 200:
            return {"error": "weather fetch failed", "raw": weather_resp.text}

        weather_data = weather_resp.json()
        current = weather_data.get("current_weather") or {}
        temp = current.get("temperature")
        wind_speed = current.get("windspeed")
        weather = current.get("weathercode")
        summary = (
            f"{first.get('name', location)} 当前天气：代码 {weather}，温度 {temp}°C，风速 {wind_speed} km/h。"
        )
        result = GetWeatherResult(
            location=first.get("name", location),
            latitude=lat,
            longitude=lng,
            temperature=float(temp) if temp is not None else None,
            summary=summary,
            raw=weather_data,
        )
        return result.dict()
