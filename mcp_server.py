import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from orchestrator import handle_prompt

DEFAULT_GAODE_MAP_API_KEY = "50cf9bea928ded7a8e7986717a000cc1"
DEFAULT_GAODE_JS_API_KEY = "b5c9399821e1f475e7cbfe06f4250bea"
DEFAULT_GAODE_SECURITY_JS_CODE = "c336ce4b5450735d824a3ed40b666d28"

app = FastAPI(title="MCP Agent Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class DecideRequest(BaseModel):
    prompt: str
    context: dict = {}


@app.get("/")
async def index():
    return FileResponse("frontend/index.html")


@app.get("/app.js")
async def app_js():
    return FileResponse("frontend/app.js")


@app.get("/api/config")
async def app_config():
    key = (
        os.getenv("GAODE_MAP_API_KEY")
        or os.getenv("GAODE_MAP_KEY")
        or os.getenv("AMAP_KEY")
        or os.getenv("MAP_KEY")
        or DEFAULT_GAODE_MAP_API_KEY
    )
    js_key = os.getenv("GAODE_JS_API_KEY") or DEFAULT_GAODE_JS_API_KEY
    security_js_code = os.getenv("GAODE_SECURITY_JS_CODE") or DEFAULT_GAODE_SECURITY_JS_CODE
    return {
        "gaodeMapKey": key,
        "gaodeMapKeyConfigured": bool(key),
        "gaodeJsApiKey": js_key,
        "gaodeSecurityJsCode": security_js_code,
    }


@app.post("/mcp/decide")
async def decide(req: DecideRequest):
    try:
        resp = await handle_prompt(req.prompt, req.context)
        return {"ok": True, "result": resp}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
