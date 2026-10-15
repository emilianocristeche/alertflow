"""Discord / Slack notifications.

Each sender returns a status string instead of raising: "skipped" (no URL
configured), "sent", or "failed: <reason>". A broken webhook must never cost
the caller the analysis it already has. Failure reasons never include the
webhook URL, because the URL itself is the secret.
"""

import logging
import os

import httpx

from llm import AlertAnalysis

log = logging.getLogger(__name__)

_SEVERITY_COLORS = {"P1": 0xFF0000, "P2": 0xFF8C00, "P3": 0xFFD700}

# Discord rejects embeds over these sizes with a 400.
_DISCORD_TITLE_MAX = 256
_DISCORD_DESCRIPTION_MAX = 4096
_SLACK_TEXT_MAX = 40_000


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _format_runbook(steps: list[str]) -> str:
    return "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))


def _post(name: str, url: str, payload: dict) -> str:
    try:
        resp = httpx.post(url, json=payload, timeout=10)
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        reason = f"HTTP {e.response.status_code}"
    except httpx.HTTPError as e:
        reason = type(e).__name__          # e.g. ConnectTimeout; str(e) may echo the URL
    else:
        return "sent"
    log.warning("%s webhook failed: %s", name, reason)
    return f"failed: {reason}"


def send_discord(result: AlertAnalysis, alert: str) -> str:
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        return "skipped"
    description = (
        f"**Alert:** {alert}\n\n"
        f"**Root Cause:** `{result.root_cause_category}`\n\n"
        f"**Runbook:**\n{_format_runbook(result.runbook)}"
    )
    payload = {
        "embeds": [
            {
                "title": _truncate(f"[{result.severity}] {result.summary}", _DISCORD_TITLE_MAX),
                "description": _truncate(description, _DISCORD_DESCRIPTION_MAX),
                "color": _SEVERITY_COLORS.get(result.severity, 0x808080),
            }
        ]
    }
    return _post("Discord", url, payload)


def send_slack(result: AlertAnalysis, alert: str) -> str:
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        return "skipped"
    text = (
        f"*[{result.severity}] {result.summary}*\n"
        f"*Alert:* {alert}\n"
        f"*Root Cause:* `{result.root_cause_category}`\n"
        f"*Runbook:*\n{_format_runbook(result.runbook)}"
    )
    return _post("Slack", url, {"text": _truncate(text, _SLACK_TEXT_MAX)})


def notify_all(result: AlertAnalysis, alert: str) -> dict[str, str]:
    return {"discord": send_discord(result, alert), "slack": send_slack(result, alert)}
