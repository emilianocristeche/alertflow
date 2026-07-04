import json
import os
from unittest.mock import MagicMock, patch

import pytest

SAMPLE = {
    "severity": "P1",
    "root_cause_category": "data",
    "runbook": [
        "Check database connection pool metrics",
        "Identify long-running queries and kill them",
        "Increase max_connections in PostgreSQL config",
        "Restart application pods to reset connection state",
    ],
    "summary": "Database connection pool exhausted causing 503 errors",
}


def _mock_response(data: dict) -> MagicMock:
    m = MagicMock()
    m.content = [MagicMock(text=json.dumps(data))]
    return m


@patch("llm.client.messages.create")
def test_severity_is_valid(mock_create):
    mock_create.return_value = _mock_response(SAMPLE)
    from llm import analyze_alert

    result = analyze_alert("db pool exhausted")
    assert result["severity"] in ("P1", "P2", "P3")


@patch("llm.client.messages.create")
def test_root_cause_is_valid(mock_create):
    mock_create.return_value = _mock_response(SAMPLE)
    from llm import analyze_alert

    result = analyze_alert("db pool exhausted")
    assert result["root_cause_category"] in ("infra", "app", "network", "data", "external")


@patch("llm.client.messages.create")
def test_runbook_has_3_to_5_steps(mock_create):
    mock_create.return_value = _mock_response(SAMPLE)
    from llm import analyze_alert

    result = analyze_alert("db pool exhausted")
    assert 3 <= len(result["runbook"]) <= 5


@patch("llm.client.messages.create")
def test_summary_is_present(mock_create):
    mock_create.return_value = _mock_response(SAMPLE)
    from llm import analyze_alert

    result = analyze_alert("db pool exhausted")
    assert result.get("summary")


@patch("llm.client.messages.create")
def test_invalid_json_raises_value_error(mock_create):
    bad = MagicMock()
    bad.content = [MagicMock(text="not json at all")]
    mock_create.return_value = bad
    from llm import analyze_alert

    with pytest.raises(ValueError, match="invalid JSON"):
        analyze_alert("something")


@patch("httpx.post")
def test_discord_skipped_when_no_url(mock_post):
    os.environ.pop("DISCORD_WEBHOOK_URL", None)
    from webhook import send_discord

    send_discord(SAMPLE, "test alert")
    mock_post.assert_not_called()


@patch("httpx.post")
def test_slack_skipped_when_no_url(mock_post):
    os.environ.pop("SLACK_WEBHOOK_URL", None)
    from webhook import send_slack

    send_slack(SAMPLE, "test alert")
    mock_post.assert_not_called()
