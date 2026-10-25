from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from orchestrator import handle_prompt

app = FastAPI(title="MCP Agent Server")


class DecideRequest(BaseModel):
    prompt: str
    context: dict = {}


@app.post("/mcp/decide")
async def decide(req: DecideRequest):
    try:
        resp = await handle_prompt(req.prompt, req.context)
        return {"ok": True, "result": resp}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
