import logging
from typing import Annotated

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StringConstraints

load_dotenv()

from llm import AlertAnalysis, LLMResponseError, analyze_alert  # noqa: E402
from webhook import notify_all  # noqa: E402

log = logging.getLogger(__name__)


class AlertRequest(BaseModel):
    alert: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    notify: bool = False


class AnalyzeResponse(AlertAnalysis):
    # Per-channel webhook outcome ("sent" / "skipped" / "failed: ..."); empty
    # when notify is false. A failed webhook never turns the response into an error.
    notifications: dict[str, str] = {}


app = FastAPI(title="AlertFlow", version="1.0.0", description="AI-powered on-call assistant")


# Plain `def` (not `async def`): the Anthropic client and the webhook calls are
# blocking, so FastAPI must run these handlers in its threadpool instead of on
# the event loop, where they would stall every other request.
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AlertRequest):
    try:
        result = analyze_alert(req.alert)
    except LLMResponseError as e:
        log.warning("Rejected LLM output: %s", e)
        raise HTTPException(status_code=502, detail="LLM returned an invalid analysis")
    except anthropic.APIError as e:
        log.warning("LLM call failed: %s", e)
        raise HTTPException(status_code=502, detail="LLM request failed")
    except Exception:
        # Anything else (e.g. missing API key): full traceback in the logs,
        # nothing internal in the response.
        log.exception("Unexpected error analyzing alert")
        raise HTTPException(status_code=500, detail="Internal error analyzing the alert")

    notifications = notify_all(result, req.alert) if req.notify else {}
    return AnalyzeResponse(**result.model_dump(), notifications=notifications)
