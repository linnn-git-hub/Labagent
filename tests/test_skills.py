import asyncio
from pathlib import Path

from skills.get_weather import get_weather
from skills.travel_emergency_manager import assess_trip_risk, _resolve_local_path
from skills.get_route_status import get_route_status, _gaode_key


async def test_weather():
    res = await get_weather({"location": "Shanghai"})
    assert "location" in res and res["location"]


async def test_route_status_skill_present():
    res = await get_route_status({"origin": "上海虹桥万怡会议中心", "destination": "上海外滩·黄浦江景观带", "mode": "driving"})
    assert "origin" in res and "destination" in res
    assert res["travel_time_minutes"] > 0


async def test_trip_risk_assessment():
    res = await assess_trip_risk({
        "activity_type": "商业路演",
        "current_location": "Shanghai",
        "backup_location": "Shanghai Hotel Center",
        "itinerary_path": "tests/sample_itinerary.txt",
        "venue_plan_path": "tests/sample_venue_plan.txt",
    })
    assert "overall_risk" in res
    assert "recommendations" in res
    assert isinstance(res["recommendations"], list)
    assert "上海外滩" in res.get("local_plan_summary", "") or "黄浦江" in res.get("local_plan_summary", "")


def test_local_path_resolution():
    resolved = _resolve_local_path("tests/sample_venue_plan.txt")
    assert Path(resolved).exists()


if __name__ == "__main__":
    asyncio.run(test_weather())
    asyncio.run(test_route_status_skill_present())
    asyncio.run(test_trip_risk_assessment())
