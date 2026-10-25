import os
import json
import asyncio
from typing import Dict, Any

from schemas import WebFetchArgs, GetWeatherResult, SummarizePDFArgs, SummarizePDFResult

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
    register_skill("get_weather", mod_weather.get_weather, WebFetchArgs)
    register_skill("summarize_pdf", mod_pdf.summarize_pdf, SummarizePDFArgs)


async def _call_skill(name: str, args: Dict[str, Any]):
    _load_skills()
    if name not in SKILLS:
        raise ValueError(f"Unknown skill: {name}")
    func = SKILLS[name]["func"]
    # call skill (might be async)
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

    # If OpenAI key present, call OpenAI function-calling API
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
                # send result back to model for finalization
                messages.append(choice["message"])
                messages.append({"role": "function", "name": fn, "content": json.dumps(result)})
                final = openai.ChatCompletion.create(model="gpt-4o-mini", messages=messages)
                return final["choices"][0]["message"]["content"]
            else:
                return choice.get("message", {}).get("content", "")
        except Exception as e:
            return {"error": f"openai call failed: {e}"}

    # Fallback simple router
    prompt_lower = prompt.lower()
    if "weather" in prompt_lower or "天气" in prompt_lower:
        # expect a location in prompt
        location = context.get("location") or "".join([w for w in prompt.split() if w[0].isalpha()][:2]) or "London"
        args = {"location": location}
        return await _call_skill("get_weather", args)
    if "pdf" in prompt_lower or ".pdf" in prompt_lower or "总结" in prompt_lower:
        # look for path in context
        path = context.get("path")
        args = {"path": path} if path else {"path": None}
        return await _call_skill("summarize_pdf", args)

    return {"error": "No LLM available and couldn't route intent."}
