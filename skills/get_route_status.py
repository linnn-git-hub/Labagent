import os
import re
from typing import Any, Dict, Optional, Tuple

import httpx

from schemas import TrafficRouteArgs, TrafficRouteResult

DEFAULT_GAODE_MAP_API_KEY = "50cf9bea928ded7a8e7986717a000cc1"


def _gaode_key() -> str:
    return (
        os.getenv("GAODE_MAP_API_KEY")
        or os.getenv("GAODE_MAP_KEY")
        or os.getenv("AMAP_KEY")
        or os.getenv("MAP_KEY")
        or DEFAULT_GAODE_MAP_API_KEY
    )


KNOWN_ROUTE_GEO_POINTS = {
    "shanghai": (31.2304, 121.4737),
    "上海": (31.2304, 121.4737),
    "上海虹桥万怡会议中心": (31.1943, 121.3349),
    "上海虹桥万怡会议中心（上海市长宁区）": (31.1943, 121.3349),
    "上海外滩黄浦江景观带": (31.2396, 121.4883),
    "上海外滩·黄浦江景观带": (31.2396, 121.4883),
    "shanghai hotel center": (31.1887, 121.4207),
}


def _normalize_query(value: str) -> str:
    if not value:
        return ""
    text = value.strip().lower()
    text = text.replace("·", "").replace("・", "")
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"[()\-_/]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _known_geocode_lookup(query: str) -> Optional[Tuple[float, float]]:
    if not query:
        return None
    normalized = _normalize_query(query)
    for key, (lat, lon) in KNOWN_ROUTE_GEO_POINTS.items():
        if _normalize_query(key) == normalized:
            return float(lat), float(lon)
    for key, (lat, lon) in KNOWN_ROUTE_GEO_POINTS.items():
        if normalized in _normalize_query(key):
            return float(lat), float(lon)
    return None


async def _gaode_geocode(query: str) -> Optional[Tuple[float, float]]:
    if not query or not query.strip():
        return None

    known = _known_geocode_lookup(query)
    if known is not None:
        return known

    api_key = _gaode_key()
    if not api_key:
        raise ValueError("未配置高德 Web服务 API Key，请设置 GAODE_MAP_API_KEY")

    url = "https://restapi.amap.com/v3/geocode/geo"
    params = {
        "key": api_key,
        "address": query,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                return None
            payload = resp.json()
            if payload.get("status") != "1":
                return None
            geocodes = payload.get("geocodes") or []
            if not geocodes:
                return None
            location = geocodes[0].get("location")
            if not location:
                return None
            lng, lat = map(float, location.split(","))
            return lat, lng
    except Exception:
        return None


async def _gaode_direction(origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
    origin_geo = await _gaode_geocode(origin)
    destination_geo = await _gaode_geocode(destination)
    if origin_geo is None or destination_geo is None:
        raise ValueError(f"无法定位起点或终点：{origin} -> {destination}")

    origin_lat, origin_lng = origin_geo
    dest_lat, dest_lng = destination_geo

    mode_map = {"driving": "driving", "transit": "transit", "walking": "walking"}
    route_mode = mode_map.get(mode, "driving")
    url = "https://restapi.amap.com/v3/direction/driving"
    if route_mode == "walking":
        url = "https://restapi.amap.com/v3/direction/walking"
    elif route_mode == "transit":
        url = "https://restapi.amap.com/v3/direction/transit/integrated"

    api_key = _gaode_key()
    if not api_key:
        raise ValueError("未配置高德 Web服务 API Key，请设置 GAODE_MAP_API_KEY")

    params = {
        "key": api_key,
        "origin": f"{origin_lng},{origin_lat}",
        "destination": f"{dest_lng},{dest_lat}",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(url, params=params)
        if resp.status_code != 200:
            raise ValueError(f"高德路线接口失败: HTTP {resp.status_code}")

        payload = resp.json()
        if payload.get("status") != "1":
            raise ValueError(f"高德路线接口返回错误: {payload.get('info')}")

        route = None
        if route_mode == "transit":
            route = (payload.get("route") or {}).get("transits") or []
            if route:
                route = route[0]
        else:
            route = (payload.get("route") or {}).get("paths") or []
            if route:
                route = route[0]

        if not route:
            raise ValueError("高德路线接口未返回有效路径")

        distance = float(route.get("distance", 0) or 0)
        if route_mode == "transit":
            duration = int(route.get("duration", 0) or 0)
            if not duration:
                duration = int(route.get("transit_time", 0) or 0)
        else:
            duration = int(route.get("duration", 0) or 0)

        if duration <= 0:
            duration = max(1, int(round(distance / 1000.0 * 1.7)))

        status = "畅通"
        if duration > 45:
            status = "交通较拥堵"
        elif duration > 25:
            status = "中度拥堵"

        return {
            "origin": origin,
            "destination": destination,
            "mode": route_mode,
            "status": status,
            "travel_time_minutes": max(1, int(round(duration / 60))) if duration else 1,
            "distance_km": round(distance / 1000.0, 1),
            "api": "gaode_map_api",
            "simulated": False,
        }


async def get_route_status(args: Dict[str, Any]):
    """Get real route status and ETA for emergency relocation using Gaode map APIs."""
    if isinstance(args, dict):
        parsed = TrafficRouteArgs(**args)
    else:
        parsed = args

    origin = parsed.origin or "当前地点"
    destination = parsed.destination or "备用场地"

    try:
        route = await _gaode_direction(origin, destination, parsed.mode)
    except Exception:
        fallback_minutes = max(15, int(len(origin) * 0.7 + len(destination) * 0.8 + 10))
        fallback_distance = max(6.0, round((fallback_minutes * 1.7), 1))
        route = {
            "origin": origin,
            "destination": destination,
            "mode": parsed.mode,
            "status": "服务暂时不可用",
            "travel_time_minutes": fallback_minutes,
            "distance_km": fallback_distance,
            "api": "gaode_map_api_fallback",
            "simulated": True,
            "error": "route api unavailable; showing estimated fallback time",
        }

    result = TrafficRouteResult(**route)
    return result.model_dump()
