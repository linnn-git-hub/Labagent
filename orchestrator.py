import os
import json
import asyncio
from typing import Dict, Any

from schemas import (
    WebFetchArgs,
    GetWeatherResult,
    SummarizePDFArgs,
    SummarizePDFResult,
    TravelRiskArgs,
    TrafficRouteArgs,
)

import importlib

SKILLS = {}


def register_skill(name: str, func, schema_model):
    SKILLS[name] = {"func": func, "schema": schema_model}


# lazy import skills
def _load_skills():
    global SKILLS
    if SKILLS:
        return
    mod_weather = importlib.import_module("skills.get_weather")
    mod_pdf = importlib.import_module("skills.summarize_pdf")
    mod_trip = importlib.import_module("skills.travel_emergency_manager")
    mod_route = importlib.import_module("skills.get_route_status")
    register_skill("get_weather", mod_weather.get_weather, WebFetchArgs)
    register_skill("summarize_pdf", mod_pdf.summarize_pdf, SummarizePDFArgs)
    register_skill("assess_trip_risk", mod_trip.assess_trip_risk, TravelRiskArgs)
    register_skill("get_route_status", mod_route.get_route_status, TrafficRouteArgs)


async def _call_skill(name: str, args: Dict[str, Any]):
    _load_skills()
    if name not in SKILLS:
        raise ValueError(f"Unknown skill: {name}")
    func = SKILLS[name]["func"]
    if asyncio.iscoroutinefunction(func):
        return await func(args)
    else:
        return func(args)


async def handle_prompt(prompt: str, context: Dict[str, Any]):
    """
    Orchestrator: uses OpenAI function-calling if OPENAI_API_KEY set,
    otherwise fallback to simple rules.
    """
    _load_skills()

    openai_key = os.getenv("OPENAI_API_KEY")
    functions_meta = []
    for name, info in SKILLS.items():
        model = info["schema"]
        try:
            schema = model.schema()
        except Exception:
            schema = {"type": "object"}
        functions_meta.append({"name": name, "description": info["func"].__doc__ or "", "parameters": schema})

    if openai_key:
        try:
            import openai

            openai.api_key = openai_key
            messages = [{"role": "user", "content": prompt}]
            resp = openai.ChatCompletion.create(model="gpt-4o-mini", messages=messages, functions=functions_meta, function_call="auto")
            choice = resp["choices"][0]
            if choice.get("finish_reason") == "function_call" or choice.get("message", {}).get("function_call"):
                fn = choice["message"]["function_call"]["name"]
                args_text = choice["message"]["function_call"].get("arguments", "{}")
                args = json.loads(args_text)
                result = await _call_skill(fn, args)
                messages.append(choice["message"])
                messages.append({"role": "function", "name": fn, "content": json.dumps(result)})
                final = openai.ChatCompletion.create(model="gpt-4o-mini", messages=messages)
                return final["choices"][0]["message"]["content"]
            else:
                return choice.get("message", {}).get("content", "")
        except Exception as e:
            return {"error": f"openai call failed: {e}"}

    prompt_lower = prompt.lower()
    if any(k in prompt_lower for k in ["weather", "天气"]):
        location = context.get("location") or "".join([w for w in prompt.split() if w[0].isalpha()][:2]) or "London"
        args = {"location": location}
        return await _call_skill("get_weather", args)
    if any(k in prompt_lower for k in ["pdf", ".pdf", "总结", "摘要"]):
        path = context.get("path")
        args = {"path": path} if path else {"path": None}
        return await _call_skill("summarize_pdf", args)
    if any(k in prompt_lower for k in ["商业路演", "摄影", "团建", "户外", "旅行", "应急", "outdoor", "trip", "travel"]):
        args = {
            "activity_type": context.get("activity_type") or "户外活动",
            "current_location": context.get("current_location") or "Shanghai",
            "backup_location": context.get("backup_location") or "Shanghai Hotel Center",
            "itinerary_path": context.get("itinerary_path"),
            "venue_plan_path": context.get("venue_plan_path"),
        }
        return await _call_skill("assess_trip_risk", args)
    if any(k in prompt_lower for k in ["路线", "交通", "route", "traffic", "拥堵"]):
        args = {
            "origin": context.get("origin") or "当前地点",
            "destination": context.get("destination") or "备用场地",
            "mode": context.get("mode") or "driving",
        }
        return await _call_skill("get_route_status", args)

    return {"error": "No LLM available and couldn't route intent."}
