import json
import os

from anthropic import Anthropic

client = Anthropic()

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


def analyze_alert(alert: str) -> dict:
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Alert: {alert}"}],
    )
    text = response.content[0].text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM returned invalid JSON: {e}\nRaw: {text}") from e
