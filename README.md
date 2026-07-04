# AlertFlow

AI-powered on-call assistant. Paste an alert → get severity, root cause, and a remediation runbook in seconds.

Built on Claude Haiku for cost efficiency. Runs as a CLI or an HTTP API. Optionally posts to Discord or Slack.

---

## Features

- **Severity classification** — P1 / P2 / P3 based on incident description
- **Root cause categorization** — infra, app, network, data, external
- **Remediation runbook** — 3–5 actionable steps, ordered by priority
- **Webhook notifications** — Discord and Slack out of the box
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

```
🔴  Severity:   P1
    Category:  data
    Summary:   Database connection pool exhausted causing service unavailability

    Runbook:
      1. Check current active connections vs max_connections in PostgreSQL
      2. Kill long-running idle connections with pg_terminate_backend()
      3. Identify and fix the query causing connection leaks in app logs
      4. Increase connection pool size in application config (e.g. pgbouncer)
      5. Deploy the fix and monitor error rate on the dashboard
```

Output as JSON:

```bash
python alertflow.py "redis OOM, cache eviction rate at 100%" --json
```

```json
{
  "severity": "P2",
  "root_cause_category": "data",
  "runbook": ["...", "..."],
  "summary": "Redis out-of-memory, evicting all keys"
}
```

Send to Discord/Slack after analyzing:

```bash
python alertflow.py "k8s nodes NotReady in us-east-1" --notify
```

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

```json
{
  "severity": "P1",
  "root_cause_category": "app",
  "runbook": [
    "Check payment-service logs for the full stack trace",
    "Identify the null object — likely a missing env var or failed upstream call",
    "Roll back to the last stable deployment if introduced by a recent push",
    "Add a null guard and redeploy"
  ],
  "summary": "NullPointerException in payment service breaking checkout flow"
}
```

**POST /analyze** with notification:

```json
{ "alert": "...", "notify": true }
```

**GET /health**

```json
{ "status": "ok" }
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

## Running Tests

```bash
pytest
```

Tests mock the LLM call — no API key needed to run them.

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

## Stack

- Python 3.11+
- [Anthropic SDK](https://github.com/anthropics/anthropic-sdk-python) — claude-haiku-4-5-20251001
- [FastAPI](https://fastapi.tiangolo.com/)
- [httpx](https://www.python-httpx.org/)
- [pytest](https://pytest.org/)

---

## License

MIT
