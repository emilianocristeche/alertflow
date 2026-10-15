from typing import Annotated, Literal

from anthropic import Anthropic
from pydantic import BaseModel, Field, StringConstraints, ValidationError

client = Anthropic()

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are an on-call incident response assistant. Analyze the alert and respond with ONLY valid JSON — no markdown, no explanation, just the JSON object.

Schema:
{
  "severity": "P1" | "P2" | "P3",
  "root_cause_category": "infra" | "app" | "network" | "data" | "external",
  "runbook": ["step 1", "step 2", "step 3"],
  "summary": "one-line summary of the incident"
}

Severity guide:
- P1: production down, data loss risk, full outage
- P2: degraded service, partial outage, high error rate
- P3: minor issue, non-urgent, low user impact

Root cause categories:
- infra: servers, Kubernetes, cloud provider, VMs, disk
- app: code bug, bad deploy, config error, memory leak
- network: DNS, load balancer, firewall, latency, packet loss
- data: database, cache, storage, query performance, replication
- external: third-party API, vendor, payment provider, CDN

Runbook: 3 to 5 actionable steps, specific and ordered by priority."""

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class AlertAnalysis(BaseModel):
    """The contract the LLM must meet. Anything else is rejected, not passed on."""

    severity: Literal["P1", "P2", "P3"]
    root_cause_category: Literal["infra", "app", "network", "data", "external"]
    runbook: list[NonEmptyStr] = Field(min_length=3, max_length=5)
    summary: NonEmptyStr


class LLMResponseError(ValueError):
    """The model answered, but not with a valid AlertAnalysis."""


def parse_analysis(text: str) -> AlertAnalysis:
    """Validate the model's raw text against AlertAnalysis."""
    try:
        return AlertAnalysis.model_validate_json(text)
    except ValidationError as e:
        if any(err["type"] == "json_invalid" for err in e.errors()):
            reason = "invalid JSON"
        else:
            problems = "; ".join(
                f"{'.'.join(map(str, err['loc'])) or '<root>'}: {err['msg']}" for err in e.errors()
            )
            reason = f"JSON that does not match the schema ({problems})"
        raise LLMResponseError(f"LLM returned {reason}. Raw: {text[:500]!r}") from e


def analyze_alert(alert: str) -> AlertAnalysis:
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Alert: {alert}"}],
    )
    # Text blocks only (a tool_use/thinking block has no string .text).
    texts = [b.text for b in response.content if isinstance(getattr(b, "text", None), str)]
    if not texts:
        raise LLMResponseError("LLM returned no text content")
    return parse_analysis(texts[0].strip())
