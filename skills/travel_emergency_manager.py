import os
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

import httpx
import PyPDF2

from schemas import TravelRiskArgs, TravelRiskResult, TrafficRouteArgs, TrafficRouteResult


KNOWN_GEO_POINTS = {
    "shanghai": (31.2304, 121.4737),
    "上海": (31.2304, 121.4737),
    "上海虹桥万怡会议中心": (31.1943, 121.3349),
    "上海虹桥万怡会议中心（上海市长宁区）": (31.1943, 121.3349),
    "上海外滩黄浦江景观带": (31.2396, 121.4883),
    "上海外滩·黄浦江景观带": (31.2396, 121.4883),
    "上海外滩·黄浦江景观带户外主舞台": (31.2396, 121.4883),
    "shanghai hotel center": (31.1887, 121.4207),
    "shanghai hotel center china": (31.1887, 121.4207),
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


def _resolve_local_path(path: str | None) -> str | None:
    if not path:
        return None
    raw = Path(path)
    if raw.is_absolute():
        return str(raw)

    candidates = [
        Path.cwd(),
        Path(__file__).resolve().parent.parent,
        Path(__file__).resolve().parent.parent / "tests",
    ]
    for base in candidates:
        candidate = (base / raw).resolve()
        if candidate.exists():
            return str(candidate)
    return str((Path(__file__).resolve().parent.parent / raw).resolve())


def _known_geo_lookup(query: str) -> Optional[Tuple[float, float, str]]:
    if not query:
        return None
    normalized = _normalize_query(query)
    for key, (lat, lon) in KNOWN_GEO_POINTS.items():
        if _normalize_query(key) == normalized:
            return float(lat), float(lon), key
    for key, (lat, lon) in KNOWN_GEO_POINTS.items():
        if normalized in _normalize_query(key):
            return float(lat), float(lon), key
    return None


def _safe_read_text(path: str | None) -> str:
    resolved = _resolve_local_path(path)
    if not resolved:
        return ""
    try:
        with open(resolved, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


async def _fetch_weather_snapshot(location: str) -> Dict[str, Any]:
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    async with httpx.AsyncClient(timeout=15) as client:
        geo = await client.get(geo_url, params={"name": location, "count": 1})
        if geo.status_code != 200:
            return {"error": "geocoding failed", "raw": geo.text}
        data = geo.json()
        results = data.get("results") or []
        if not results:
            return {"error": "location not found", "location": location}
        first = results[0]
        lat, lon = first["latitude"], first["longitude"]
        weather_url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True,
            "forecast_days": 2,
            "timezone": "auto",
        }
        wr = await client.get(weather_url, params=params)
        if wr.status_code != 200:
            return {"error": "weather fetch failed", "raw": wr.text}
        payload = wr.json()
        current = payload.get("current_weather") or {}
        return {
            "location": first.get("name"),
            "latitude": lat,
            "longitude": lon,
            "current": current,
            "forecast": payload.get("daily", {}),
        }


async def _geocode_location(query: str) -> Optional[Tuple[float, float, str]]:
    if not query or not query.strip():
        return None

    known = _known_geo_lookup(query)
    if known is not None:
        return known

    params = {
        "q": query,
        "format": "jsonv2",
        "limit": 1,
        "addressdetails": 1,
    }
    headers = {"User-Agent": "labAgent/1.0 (+https://example.com)"}

    try:
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            resp = await client.get("https://nominatim.openstreetmap.org/search", params=params)
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data:
                return None
            first = data[0]
            return float(first["lat"]), float(first["lon"]), str(first.get("display_name") or query)
    except Exception:
        return None


async def _fetch_real_route_status(origin: str, destination: str, mode: str = "driving") -> Dict[str, Any]:
    profile = "driving" if mode == "driving" else "walking" if mode == "walking" else "driving"
    origin_geo = await _geocode_location(origin)
    destination_geo = await _geocode_location(destination)

    if origin_geo is None or destination_geo is None:
        raise ValueError(f"无法定位起点或终点：{origin} -> {destination}")

    start_lat, start_lon, _ = origin_geo
    end_lat, end_lon, _ = destination_geo

    route_url = (
        f"https://router.project-osrm.org/route/v1/{profile}/{start_lon},{start_lat};{end_lon},{end_lat}"
        "?overview=false&geometries=geojson&alternatives=false"
    )

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(route_url)
        if resp.status_code != 200:
            raise ValueError(f"路线服务返回异常: HTTP {resp.status_code}")

        payload = resp.json()
        route = payload.get("routes", [{}])[0]
        distance_m = float(route.get("distance", 0.0) or 0.0)
        duration_s = float(route.get("duration", 0.0) or 0.0)

        if distance_m <= 0 or duration_s <= 0:
            raise ValueError("路线服务未返回有效距离或时间")

        status = "畅通"
        if duration_s / 60 > 45:
            status = "交通较拥堵"
        elif duration_s / 60 > 25:
            status = "中度拥堵"

        return {
            "origin": origin,
            "destination": destination,
            "mode": mode,
            "status": status,
            "travel_time_minutes": max(1, int(round(duration_s / 60))),
            "distance_km": round(distance_m / 1000.0, 1),
            "api": "osrm_route_api",
            "simulated": False,
            "origin_geo": {"lat": start_lat, "lon": start_lon},
            "destination_geo": {"lat": end_lat, "lon": end_lon},
        }


async def get_route_status(args: Dict[str, Any]):
    """Calculate traffic and travel time to a backup venue or hotel for emergency relocation using real map routing."""
    if isinstance(args, dict):
        parsed = TrafficRouteArgs(**args)
    else:
        parsed = args

    origin = parsed.origin or "当前地点"
    destination = parsed.destination or "备用场地"
    if not destination:
        return {"error": "missing destination", "origin": origin}

    try:
        route = await _fetch_real_route_status(origin, destination, parsed.mode)
    except Exception:
        # Last-resort fallback only if the live map service is unavailable.
        base_time = max(15, len(origin) + len(destination) // 2)
        congestion = "轻度拥堵" if (len(origin) + len(destination)) % 3 == 0 else "中度拥堵" if (len(origin) + len(destination)) % 2 == 0 else "畅通"
        travel_time = base_time + (10 if congestion == "中度拥堵" else 5 if congestion == "轻度拥堵" else 0)
        route = {
            "origin": origin,
            "destination": destination,
            "mode": parsed.mode,
            "status": congestion,
            "travel_time_minutes": travel_time,
            "distance_km": round(max(5.0, travel_time * 0.8), 1),
            "api": "osrm_route_api_fallback",
            "simulated": True,
        }

    result = TrafficRouteResult(**route)
    return result.model_dump()


def _extract_locations_from_text(text: str) -> List[str]:
    if not text:
        return []

    text = text.replace("\r", "\n")
    patterns = [
        r"地点[:：]\s*([^\n]+)",
        r"应急预案场地[:：]\s*([^\n]+)",
        r"场地方案[:：]\s*([^\n]+)",
    ]
    candidates: List[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            raw = match.group(1).strip()
            cleaned = re.split(r"\s*(?:\(|（|\d{4}-\d{2}-\d{2}|室内|设备|交通|参与人员|场地要求|风险关注)", raw, maxsplit=1)[0].strip()
            cleaned = cleaned.strip(" 。,；:：")
            if cleaned and cleaned not in candidates:
                candidates.append(cleaned)

    if not candidates:
        for name in ["上海", "北京", "杭州", "广州"]:
            if name in text:
                candidates.append(name)

    return candidates[:6]


def _read_local_document_text(path: str | None) -> str:
    if not path:
        return ""
    resolved = _resolve_local_path(path)
    if not resolved:
        return ""

    suffix = Path(resolved).suffix.lower()
    try:
        if suffix == ".pdf":
            reader = PyPDF2.PdfReader(resolved)
            pieces = []
            for page in reader.pages:
                text = page.extract_text() or ""
                pieces.append(text)
            return "\n".join(pieces)
        with open(resolved, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        try:
            with open(resolved, "r", encoding="gbk") as f:
                return f.read()
        except Exception:
            return ""


def _extract_activity_type(itinerary_text: str, venue_text: str) -> str:
    text = "\n".join(filter(None, [itinerary_text, venue_text]))
    patterns = [
        r"活动名称[:：]\s*(.+)",
        r"活动类型[:：]\s*(.+)",
        r"商业路演",
        r"摄影采风",
        r"户外团建",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            value = match.group(1) if match.lastindex else match.group(0)
            return value.strip()
    return "户外活动"


def _extract_current_location(itinerary_text: str) -> str:
    candidates = _extract_locations_from_text(itinerary_text)
    if candidates:
        return candidates[0]
    return "上海"


def _extract_backup_location(venue_text: str) -> str:
    candidates = _extract_locations_from_text(venue_text)
    if len(candidates) > 1:
        return candidates[1]
    if candidates:
        return candidates[0]
    return "上海虹桥万怡会议中心"


async def assess_trip_risk(args: Dict[str, Any]):
    """Assess outdoor event risk by combining local activity plans with live weather and road conditions."""
    if isinstance(args, dict):
        parsed = TravelRiskArgs(**args)
    else:
        parsed = args

    itinerary_path = parsed.itinerary_path or "tests/sample_itinerary.txt"
    venue_path = parsed.venue_plan_path or "tests/sample_venue_plan.txt"
    itinerary_text = _read_local_document_text(itinerary_path)
    venue_text = _read_local_document_text(venue_path)
    if not itinerary_text and hasattr(parsed, 'itinerary_path'):
        itinerary_text = _safe_read_text(parsed.itinerary_path)
    if not venue_text and hasattr(parsed, 'venue_plan_path'):
        venue_text = _safe_read_text(parsed.venue_plan_path)

    if not parsed.activity_type or not parsed.activity_type.strip():
        parsed.activity_type = _extract_activity_type(itinerary_text, venue_text)
    if not parsed.current_location or not parsed.current_location.strip():
        parsed.current_location = _extract_current_location(itinerary_text)
    if not parsed.backup_location or not parsed.backup_location.strip():
        parsed.backup_location = _extract_backup_location(venue_text)

    weather = await _fetch_weather_snapshot(parsed.current_location)

    if isinstance(weather, dict) and weather.get("error"):
        weather_summary = weather.get("error")
        weather_risk = 2
    else:
        current = weather.get("current") or {}
        wind = float(current.get("windspeed", 0) or 0)
        precip = float(current.get("precipitation", 0) or 0)
        temp = float(current.get("temperature", 20) or 20)
        weather_code = int(current.get("weathercode", 0) or 0)

        risk_score = 0
        if wind >= 16:
            risk_score += 2
        if precip > 0:
            risk_score += 2
        if temp < 5 or temp > 35:
            risk_score += 1
        if weather_code in {95, 96, 99}:
            risk_score += 3

        weather_summary = (
            f"当前 {weather.get('location')}：{temp}°C，风速 {wind} km/h，降水 {precip} mm，天气代码 {weather_code}."
        )
        weather_risk = min(risk_score, 5)

    text_summary = "\n".join(filter(None, [itinerary_text, venue_text]))
    risk_factors = []
    if "暴雨" in text_summary or "降雨" in text_summary:
        risk_factors.append("活动文本中要求关注降雨/暴雨风险")
    if "大风" in text_summary or "风力" in text_summary:
        risk_factors.append("活动文本中明确提示大风风险")
    if weather_risk >= 3:
        risk_factors.append("实时天气条件对户外活动存在较高影响")
    if not risk_factors:
        risk_factors.append("当前风险主要来自环境变动因素，需要重点关注现场协同")

    if weather_risk <= 1:
        overall_risk = "low"
    elif weather_risk <= 3:
        overall_risk = "medium"
    else:
        overall_risk = "high"

    recommendations = [
        f"优先检查 {parsed.current_location} 的实时天气，避免在高风险时段开展户外主活动。",
        f"若风险持续升高，建议尽快转移至备用场地：{parsed.backup_location}。",
        "提前准备应急装备：防雨布、防风装置、备用投影设备、移动电源和通讯工具。",
        "同步所有参会人员确认应急路线与转移时间，确保现场指挥链清晰。",
    ]
    if "商业路演" in (parsed.activity_type or ""):
        recommendations.append("商业路演场景下，建议将关键演示内容提前备份至云端，以便快速在室内场地切换。）")
    if "摄影" in (parsed.activity_type or ""):
        recommendations.append("摄影采风场景下，建议保留机位与快门防护策略，避免强风和降雨导致器材受损。")
    if "团建" in (parsed.activity_type or ""):
        recommendations.append("户外团建场景下，建议将互动项目调整为室内或半室内形式，减少人员不必要暴露。")

    route = await get_route_status({
        "origin": parsed.current_location,
        "destination": parsed.backup_location,
        "mode": "driving",
    })

    result = TravelRiskResult(
        activity_type=parsed.activity_type,
        current_location=parsed.current_location,
        backup_location=parsed.backup_location,
        weather_summary=weather_summary,
        weather_risk_score=weather_risk,
        overall_risk=overall_risk,
        risk_factors=risk_factors,
        recommendations=recommendations,
        route_status=route,
        local_plan_summary=text_summary[:800],
    )
    return result.model_dump()
