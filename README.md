# SRE On-call Agent

Monitors Snitch services, detects threshold breaches, runs an LLM-based root-cause analysis, and notifies the on-call engineer.

## How it works

1. A cron job calls `POST /webhook/check` with a service name.
2. Metrics are fetched from New Relic, Postgres (Aurora), Redis, CloudWatch and Elasticsearch, depending on the service's YAML config.
3. Metrics are compared against the thresholds in `configs/services/<service>.yaml`.
4. On a breach, the agent (`agent/`) produces an RCA, and the incident is saved under `storage/incidents/`.
5. Notifications go out through Slack, Twilio SMS, Twilio voice and AWS SNS. The dispatch call in `server.py` is currently commented out.

## Layout

| Path | Purpose |
|---|---|
| `server.py` | FastAPI API (port 8000) |
| `app.py` | Streamlit dashboard (port 8501) |
| `agent/` | RCA agent, prompts, LLM providers (Ollama) |
| `configs/` | Per-service YAML config and shared infrastructure |
| `metrics/`, `tools/` | Metric fetchers and source clients |
| `thresholds/` | Threshold evaluation |
| `oncall/`, `storage/` | Rotation schedule and incident storage |
| `notifications/` | Slack, Twilio and SNS notifiers |
| `auth/` | Login and JWT handling |

## Run locally

Create `.env.dev` with your keys, then:

```bash
docker-compose -f docker-compose.dev.yaml up --build
```

- Dashboard: http://localhost:8501
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

For production use `docker-compose.yaml` with a `.env` file. See [DOCKER_DEV.md](DOCKER_DEV.md) and [QUICKSTART.md](QUICKSTART.md).

## Configuration

Secrets are read from environment variables and never stored in the YAML files. Variables used by the code:

- `JWT_SECRET_KEY`, `INTERNAL_SECRET`
- `NEW_RELIC_API_KEY`, `NEW_RELIC_ACCOUNT_ID`
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USERNAME`, `POSTGRES_PASSWORD`, `POSTGRES_DATABASE`
- `SLACK_BOT_TOKEN`, `SLACK_CHANNEL_ID`
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- `SNS_TOPIC_ARN`, `AWS_REGION`
- `OLLAMA_HOST`

## Adding a service

Add `configs/services/<name>.yaml` with the metric sources to use, thresholds, severity rules and notification channels. Use `configs/services/aurora-primary.yaml` as a template.
