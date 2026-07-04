from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

from llm import analyze_alert
from webhook import send_discord, send_slack


class AlertRequest(BaseModel):
    alert: str
    notify: bool = False


class AlertResponse(BaseModel):
    severity: str
    root_cause_category: str
    runbook: list[str]
    summary: str


app = FastAPI(title="AlertFlow", version="1.0.0", description="AI-powered on-call assistant")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AlertResponse)
async def analyze(req: AlertRequest):
    if not req.alert.strip():
        raise HTTPException(status_code=422, detail="alert cannot be empty")
    try:
        result = analyze_alert(req.alert)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if req.notify:
        send_discord(result, req.alert)
        send_slack(result, req.alert)

    return result
