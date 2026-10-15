"""Tests run the real parsing/validation code; only the network edges are faked
(the Anthropic client's messages.create and httpx.post)."""

import inspect
import json
import logging
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient

import api
from llm import AlertAnalysis, LLMResponseError, analyze_alert
from webhook import send_discord, send_slack

VALID = {
    "severity": "P1",
    "root_cause_category": "data",
    "runbook": [
        "Check database connection pool metrics",
        "Identify long-running queries and kill them",
        "Increase max_connections in PostgreSQL config",
    ],
    "summary": "Database connection pool exhausted causing 503 errors",
}

DISCORD_URL = "https://discord.com/api/webhooks/123/SECRET-TOKEN"


def _llm_reply(text: str):
    """What client.messages.create returns: an object with a list of text blocks."""
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)])


def _with(**overrides) -> str:
    return json.dumps({**VALID, **overrides})


def _without(key: str) -> str:
    return json.dumps({k: v for k, v in VALID.items() if k != key})


# --- LLM output validation -----------------------------------------------------

@patch("llm.client.messages.create")
def test_valid_reply_parses_into_model(mock_create):
    mock_create.return_value = _llm_reply(json.dumps(VALID))
    result = analyze_alert("db pool exhausted")
    assert isinstance(result, AlertAnalysis)
    assert result.severity == "P1"
    assert len(result.runbook) == 3


@patch("llm.client.messages.create")
def test_extra_keys_from_llm_are_dropped(mock_create):
    mock_create.return_value = _llm_reply(_with(confidence=0.9))
    assert "confidence" not in analyze_alert("x").model_dump()


@pytest.mark.parametrize("reply, expected", [
    ("not json at all", "invalid JSON"),
    ('```json\n' + json.dumps(VALID) + '\n```', "invalid JSON"),    # markdown fence
    ('Here you go: ' + json.dumps(VALID), "invalid JSON"),          # prose prefix
    ('{"severity": "P1", "root_cause', "invalid JSON"),             # truncated (max_tokens)
    ('["P1", "data"]', "does not match the schema"),                # wrong shape
    (_with(severity="P0"), "severity"),                             # off-menu severity
    (_with(severity="p1"), "severity"),                             # wrong case
    (_with(root_cause_category="database"), "root_cause_category"),
    (_with(runbook=["only one step"]), "runbook"),                  # < 3 steps
    (_with(runbook=[f"step {i}" for i in range(6)]), "runbook"),    # > 5 steps
    (_with(runbook=["a", "  ", "c"]), "runbook"),                   # blank step
    (_with(runbook="restart everything"), "runbook"),               # string, not list
    (_with(summary=""), "summary"),
    (_without("summary"), "summary"),
    (_without("severity"), "severity"),
])
@patch("llm.client.messages.create")
def test_malformed_reply_is_rejected(mock_create, reply, expected):
    mock_create.return_value = _llm_reply(reply)
    with pytest.raises(LLMResponseError, match=expected):
        analyze_alert("something")


@patch("llm.client.messages.create")
def test_reply_without_text_block_is_rejected(mock_create):
    mock_create.return_value = SimpleNamespace(content=[])
    with pytest.raises(LLMResponseError, match="no text"):
        analyze_alert("something")


# --- webhooks ---------------------------------------------------------------------

RESULT = AlertAnalysis(**VALID)


@patch("httpx.post")
def test_webhooks_skipped_when_no_url(mock_post, monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    assert send_discord(RESULT, "a") == "skipped"
    assert send_slack(RESULT, "a") == "skipped"
    mock_post.assert_not_called()


def _response(status: int) -> httpx.Response:
    return httpx.Response(status, request=httpx.Request("POST", DISCORD_URL))


@patch("httpx.post")
def test_webhook_sent(mock_post, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_URL)
    mock_post.return_value = _response(204)
    assert send_discord(RESULT, "a") == "sent"


@patch("httpx.post")
def test_webhook_http_error_is_reported_not_raised(mock_post, monkeypatch, caplog):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_URL)
    mock_post.return_value = _response(404)          # e.g. webhook deleted
    with caplog.at_level(logging.WARNING):
        assert send_discord(RESULT, "a") == "failed: HTTP 404"
    assert "SECRET-TOKEN" not in caplog.text         # the URL is the secret


@patch("httpx.post", side_effect=httpx.ConnectTimeout("timed out"))
def test_webhook_timeout_is_reported_not_raised(mock_post, monkeypatch):
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T/B/SECRET")
    assert send_slack(RESULT, "a") == "failed: ConnectTimeout"


@patch("httpx.post")
def test_discord_payload_truncated_to_embed_limits(mock_post, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_URL)
    mock_post.return_value = _response(204)
    long = AlertAnalysis(**{**VALID, "summary": "s" * 1000})
    send_discord(long, "x" * 10_000)
    embed = mock_post.call_args.kwargs["json"]["embeds"][0]
    assert len(embed["title"]) <= 256
    assert len(embed["description"]) <= 4096


# --- API ----------------------------------------------------------------------------

client = TestClient(api.app)


def test_endpoints_are_sync():
    # Blocking SDK/httpx calls must not run on the event loop.
    assert not inspect.iscoroutinefunction(api.analyze)
    assert not inspect.iscoroutinefunction(api.health)


@patch("llm.client.messages.create")
def test_api_returns_validated_analysis(mock_create):
    mock_create.return_value = _llm_reply(json.dumps(VALID))
    r = client.post("/analyze", json={"alert": "db pool exhausted"})
    assert r.status_code == 200
    assert r.json() == {**VALID, "notifications": {}}


@patch("llm.client.messages.create")
def test_api_malformed_llm_reply_is_502_without_leaking_raw_output(mock_create):
    mock_create.return_value = _llm_reply(_with(severity="CRITICAL"))
    r = client.post("/analyze", json={"alert": "x"})
    assert r.status_code == 502
    assert "CRITICAL" not in r.text


@pytest.mark.parametrize("body", [{"alert": ""}, {"alert": "   "}, {}, {"alert": "x" * 4001}])
def test_api_rejects_bad_input(body):
    assert client.post("/analyze", json=body).status_code == 422


@patch("httpx.post", side_effect=httpx.ConnectTimeout("timed out"))
@patch("llm.client.messages.create")
def test_api_webhook_failure_still_returns_analysis(mock_create, mock_post, monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", DISCORD_URL)
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    mock_create.return_value = _llm_reply(json.dumps(VALID))
    r = client.post("/analyze", json={"alert": "db down", "notify": True})
    assert r.status_code == 200
    assert r.json()["severity"] == "P1"
    assert r.json()["notifications"] == {"discord": "failed: ConnectTimeout", "slack": "skipped"}


@patch("llm.client.messages.create", side_effect=RuntimeError("db password is hunter2"))
def test_api_unexpected_error_is_logged_and_generic(mock_create, caplog):
    with caplog.at_level(logging.ERROR, logger="api"):
        r = client.post("/analyze", json={"alert": "x"})
    assert r.status_code == 500
    assert r.json() == {"detail": "Internal error analyzing the alert"}
    assert "hunter2" not in r.text
    assert "hunter2" in caplog.text      # the operator still sees the cause
