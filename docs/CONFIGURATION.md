# Configuration

All non-sensitive configuration lives in `.env` at the project root. Sensitive credentials (database password, Gemini API key) are injected exclusively via Docker secrets mounted at `/run/secrets/`.

Copy the example file to get started:

```bash
cp .env.example .env
```

---

## Environment Variables

### PostgreSQL

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_HOST` | `postgres` | Hostname of your PostgreSQL container/service |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `sentinel` | Database name |
| `POSTGRES_USER` | `sentinel` | Database user |
| `POSTGRES_PASSWORD` | _(secret)_ | **Set via Docker secret only** — see below |

### Gemini AI Models

| Variable | Default | Description |
|---|---|---|
| `GEMINI_PRO_MODEL` | `gemini-3-pro-preview` | Model used for deep root cause analysis with extended thinking |
| `GEMINI_FLASH_MODEL` | `gemini-3-flash-preview` | Model used for fast initial triage classification |
| `GEMINI_API_KEY` | _(secret)_ | **Set via Docker secret only** — see below |
| `GEMINI_THINKING_BUDGET` | `15000` | Maximum thinking tokens for deep analysis (Gemini 3 Pro) |
| `GEMINI_THINKING_BUDGET_MEDIUM` | `8000` | Thinking token budget for overrun escalation analysis |

Higher thinking budgets produce more thorough root cause reasoning at the cost of increased latency and token usage.

### External Service URLs

These are the container hostnames of your existing infrastructure services on the `dbnet` Docker network. Set them to match the container names in your stack.

| Variable | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus HTTP API base URL |
| `LOKI_URL` | `http://loki:3100` | Loki HTTP API base URL |

### Monitoring Behaviour

| Variable | Default | Description |
|---|---|---|
| `PROMETHEUS_POLL_INTERVAL_SECONDS` | `30` | How often the worker queries Prometheus and runs anomaly detection |
| `PROMETHEUS_LOOKBACK_MINUTES` | `60` | Time window of metric history fed into MAD/CUSUM analysis |
| `LOKI_LOG_LINES` | `100` | Number of log lines fetched as LLM context per analysis |
| `LOKI_POLL_INTERVAL_SECONDS` | `5` | How often new Loki log lines are streamed for active incidents |
| `LEARNING_WINDOW_DAYS` | `30` | Days of historical data used during the baseline learning phase |

### Anomaly Detection Thresholds (MAD/CUSUM)

| Variable | Default | Description |
|---|---|---|
| `MAD_ZSCORE_THRESHOLD` | `3.5` | Modified Z-score above which a data point is flagged as anomalous. Higher values are less sensitive. |
| `CUSUM_SLACK_MULTIPLIER` | `0.5` | CUSUM allowable slack `k = multiplier × σ`. Controls sensitivity to gradual mean shifts. |
| `CUSUM_ALARM_THRESHOLD` | `4.0` | CUSUM alarm threshold `H = multiplier × σ`. Higher values require a larger sustained shift to trigger. |
| `EXPECTED_OVERRUN_MULTIPLIER` | `1.2` | An expected event is considered overdue when `elapsed > expected_duration × this_value`. Triggers Gemini escalation. |

### Debug

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `false` | Enable FastAPI debug mode and verbose logging |

---

## Docker Secrets

Sensitive credentials are never stored in environment files. They are written as plain-text files on the host and mounted into the container at `/run/secrets/`.

### Setup

```bash
export SENTINEL_SECRETS_DIR=/path/to/your/secrets

echo "your_db_password"    > "$SENTINEL_SECRETS_DIR/postgres_password.txt"
echo "your_gemini_api_key" > "$SENTINEL_SECRETS_DIR/gemini_api_key.txt"

chmod 600 "$SENTINEL_SECRETS_DIR/postgres_password.txt"
chmod 600 "$SENTINEL_SECRETS_DIR/gemini_api_key.txt"
```

The `SENTINEL_SECRETS_DIR` environment variable must be set in the shell that runs `docker compose up`.

### How secrets are resolved

At startup, `app/config.py` checks `/run/secrets/gemini_api_key` and `/run/secrets/postgres_password`. If the files exist, their values override the (empty) defaults. If they do not exist (local development), the application falls back to `GEMINI_API_KEY` and `POSTGRES_PASSWORD` in `.env`.

---

## Gemini AI Configuration

### Changing the AI models

To use a different Gemini model, update the model name variables in `.env`:

```bash
GEMINI_PRO_MODEL=gemini-3-pro-preview
GEMINI_FLASH_MODEL=gemini-3-flash-preview
```

Only models that support `response_mime_type: application/json` and `ThinkingConfig` are compatible with the Pro analysis path.

### Customising the system prompt

The LLM system prompt is loaded from `specs/gemini_thinking_system_prompt.txt` at runtime. You can edit this file to change how the AI reasons about incidents without redeploying.

Changes take effect on the next analysis triggered by the monitoring worker.

### Customising the response schema

The structured output JSON schema is loaded from `specs/gemini_response_schema.json`. You can add or remove fields as long as the schema remains valid JSON Schema (draft-07).

The following fields are required and must remain in the schema:
- `is_anomaly` (boolean)
- `severity` (string enum: `INFO`, `WARNING`, `CRITICAL`)
- `root_cause_analysis` (string)
- `confidence_score` (number 0–1)

### Prompt Lab

Both the system prompt and the response schema can be edited live through the **Prompt Lab** page in the dashboard (`/prompt-lab`). Changes made there are persisted in the database and take precedence over the file-based defaults for subsequent analyses.

---

## Traefik / Domain

| Variable | Example | Description |
|---|---|---|
| `SENTINEL_DOMAIN` | `sentinel.example.com` | The public hostname Traefik will route to the dashboard |

Set this in `.env`:

```bash
SENTINEL_DOMAIN=sentinel.example.com
```

`docker-compose.yml` reads it via `${SENTINEL_DOMAIN}` in the Traefik router label. Traefik handles TLS certificate provisioning automatically via Let's Encrypt.

### Multi-network routing

`sentinel-ui` is attached to two networks (`internet` and `intranet`). Without explicit network routing, Traefik may resolve the wrong container IP and fail to serve requests. The following label in `docker-compose.yml` is required and must not be removed:

```yaml
- "traefik.docker.network=internet"
```

This tells Traefik to always reach `sentinel-ui` via the `internet` network interface, where its entry points are configured.
