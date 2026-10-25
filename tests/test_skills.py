import asyncio
from skills.get_weather import get_weather


async def test_weather():
    res = await get_weather({"location": "London"})
    assert "location" in res and res["location"]


if __name__ == "__main__":
    asyncio.run(test_weather())
