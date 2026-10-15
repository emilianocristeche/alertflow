# AlertFlow

AI-powered on-call assistant. Paste an alert → get severity, root cause, and a remediation runbook in seconds.

Built on Claude Haiku for cost efficiency. Runs as a CLI or an HTTP API. Optionally posts to Discord or Slack.

---

## Features

- **Severity classification** — P1 / P2 / P3 based on incident description
- **Root cause categorization** — infra, app, network, data, external
- **Remediation runbook** — 3–5 actionable steps, ordered by priority
- **Webhook notifications** — Discord and Slack out of the box
- **Validated output** — the model's JSON must match a strict Pydantic schema, or it's rejected
- **CLI + API** — same engine, two interfaces
- **Docker-ready** — `docker-compose up` and you're live

---

## Quick Start

```bash
git clone https://github.com/emilianocristeche/alertflow
cd alertflow
cp .env.example .env   # add your ANTHROPIC_API_KEY
pip install -r requirements.txt
```

### CLI

```bash
python alertflow.py "database connection pool exhausted, 503s spiking"
```

_TODO: paste the output of a real run here (requires `ANTHROPIC_API_KEY`)._

Output as JSON:

```bash
python alertflow.py "redis OOM, cache eviction rate at 100%" --json
```

_TODO: paste the output of a real run here (requires `ANTHROPIC_API_KEY`)._

Send to Discord/Slack after analyzing:

```bash
python alertflow.py "k8s nodes NotReady in us-east-1" --notify
```

The status of each webhook (`sent`, `skipped` or `failed: <reason>`) is printed
to stderr.

---

### API

Start the server:

```bash
uvicorn api:app --reload
```

**POST /analyze**

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"alert": "payment service throwing NullPointerException, checkout broken"}'
```

_TODO: paste the response of a real run here (requires `ANTHROPIC_API_KEY`)._

The response has the four analysis fields plus `notifications`, which is `{}`
unless `notify` is true.

**POST /analyze** with notification:

```json
{ "alert": "...", "notify": true }
```

**GET /health** (real output)

```json
{"status": "ok"}
```

**Errors**

| Status | When |
|---|---|
| `422` | `alert` missing, blank, or longer than 4000 characters |
| `502` | The model's reply is not valid JSON or does not match the schema, or the Anthropic API call fails. The raw reply is logged, not returned. |

A failed Discord/Slack webhook does **not** fail the request: the analysis is
returned and `notifications` says what happened, e.g.
`{"discord": "failed: HTTP 404", "slack": "skipped"}`. Failure reasons never
include the webhook URL, since the URL is the secret.

Real response for a blank alert (`{"alert": "   "}`):

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": [
        "body",
        "alert"
      ],
      "msg": "String should have at least 1 character",
      "input": "   ",
      "ctx": {
        "min_length": 1
      }
    }
  ]
}
```

Interactive docs at `http://localhost:8000/docs`.

---

### Docker

```bash
cp .env.example .env  # fill in your keys
docker-compose up
```

API available at `http://localhost:8000`.

---

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Your Anthropic API key |
| `DISCORD_WEBHOOK_URL` | No | Discord webhook — omit to disable |
| `SLACK_WEBHOOK_URL` | No | Slack incoming webhook — omit to disable |

---

## Output validation

`llm.py` defines the contract as a Pydantic model (`AlertAnalysis`):

- `severity`: exactly `P1`, `P2` or `P3`
- `root_cause_category`: one of `infra`, `app`, `network`, `data`, `external`
- `runbook`: 3 to 5 non-blank steps
- `summary`: non-blank

The reply is parsed with `AlertAnalysis.model_validate_json`. Markdown fences,
prose around the JSON, truncated replies, wrong labels or a wrong runbook
length raise `LLMResponseError` instead of reaching the CLI, the API response
or a webhook. Extra keys from the model are dropped.

The API handlers are plain `def`, not `async def`: the Anthropic client and the
webhook calls block, so FastAPI runs them in its threadpool instead of on the
event loop.

## Running Tests

```bash
pytest -q    # 31 tests
```

Only the network edges are faked (`client.messages.create` and `httpx.post`);
the parsing and validation code runs for real. The suite feeds malformed model
replies (invalid or truncated JSON, fenced JSON, wrong labels, wrong runbook
length, missing fields) and checks they are rejected, plus webhook failures
and the API's error codes. No API key needed.

---

## Project Structure

```
alertflow/
├── alertflow.py      # CLI entry point
├── api.py            # FastAPI app
├── llm.py            # Anthropic SDK wrapper
├── webhook.py        # Discord + Slack senders
├── tests/
│   └── test_alertflow.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── pytest.ini
```

---

## What I Learned

_TODO: section to be written by the author._

---

## Stack

- Python 3.11+
- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) — claude-haiku-4-5-20251001
- [FastAPI](https://fastapi.tiangolo.com/)
- [httpx](https://www.python-httpx.org/)
- [pytest](https://pytest.org/)

---

## License

MIT
