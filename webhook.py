import os

import httpx

_SEVERITY_COLORS = {"P1": 0xFF0000, "P2": 0xFF8C00, "P3": 0xFFD700}


def _format_runbook(steps: list[str]) -> str:
    return "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps))


def send_discord(result: dict, alert: str) -> None:
    url = os.getenv("DISCORD_WEBHOOK_URL")
    if not url:
        return
    steps = _format_runbook(result["runbook"])
    payload = {
        "embeds": [
            {
                "title": f"[{result['severity']}] {result['summary']}",
                "description": (
                    f"**Alert:** {alert}\n\n"
                    f"**Root Cause:** `{result['root_cause_category']}`\n\n"
                    f"**Runbook:**\n{steps}"
                ),
                "color": _SEVERITY_COLORS.get(result["severity"], 0x808080),
            }
        ]
    }
    httpx.post(url, json=payload, timeout=10)


def send_slack(result: dict, alert: str) -> None:
    url = os.getenv("SLACK_WEBHOOK_URL")
    if not url:
        return
    steps = _format_runbook(result["runbook"])
    payload = {
        "text": (
            f"*[{result['severity']}] {result['summary']}*\n"
            f"*Alert:* {alert}\n"
            f"*Root Cause:* `{result['root_cause_category']}`\n"
            f"*Runbook:*\n{steps}"
        )
    }
    httpx.post(url, json=payload, timeout=10)
