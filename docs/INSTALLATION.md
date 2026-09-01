# Installation

## Prerequisites

Before deploying AIOps Sentinel, the following infrastructure must already be running and accessible:

### Required External Services

| Service | Purpose | Notes |
|---|---|---|
| **PostgreSQL 16+** | Incident history, target config, metric profiles | Must be reachable on `dbnet` |
| **Prometheus v3** | Metrics source for anomaly detection | Must expose the HTTP API |
| **Loki 3.x** | Log aggregation source | Must expose the HTTP API |
| **Traefik v3** | Reverse proxy with TLS termination | `internet`, `intranet`, `dbnet` networks must exist |
| **Docker Engine 24+** | Container runtime | With Compose v2 (`docker compose`) |

### Required Docker Networks

The stack uses three pre-existing external Docker networks. Create them if they do not exist:

```bash
docker network create internet
docker network create intranet
docker network create dbnet
```

### Google Gemini API Key

Obtain an API key from [Google AI Studio](https://aistudio.google.com/). The key requires access to:
- `gemini-3-pro-preview` (extended thinking, deep analysis)
- `gemini-3-flash-preview` (fast triage classification)

---

## Installation Steps

### 1. Clone the repository

```bash
git clone <repository-url>
cd sentinel
```

### 2. Create Docker secrets

Sensitive credentials are injected via Docker secrets — never stored in environment files.

```bash
# Set the directory where your secret files will live
export SENTINEL_SECRETS_DIR=/path/to/your/secrets

mkdir -p "$SENTINEL_SECRETS_DIR"

# Write your credentials
echo "your_strong_db_password"  > "$SENTINEL_SECRETS_DIR/postgres_password.txt"
echo "your_gemini_api_key"      > "$SENTINEL_SECRETS_DIR/gemini_api_key.txt"

chmod 600 "$SENTINEL_SECRETS_DIR/postgres_password.txt"
chmod 600 "$SENTINEL_SECRETS_DIR/gemini_api_key.txt"
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set the correct service URLs for your infrastructure. See [CONFIGURATION.md](CONFIGURATION.md) for a full reference of every variable.

### 4. Initialise the database

Run the init script **once** on the host to create the `sentinel` PostgreSQL role and database. The password is read from the secret file you created in step 2 — nothing is hardcoded.

```bash
export SENTINEL_SECRETS_DIR=/path/to/your/secrets   # same path as step 2
export PGPASSWORD=<your_postgres_superuser_password>
./scripts/initdb.sh
```

Table creation (Alembic migrations) runs automatically every time the `sentinel-api` container starts — no manual step required.

### 5. Build and start

```bash
docker compose up -d --build
```

This starts three services:

| Service | Description |
|---|---|
| `sentinel-ui` | Next.js 15 dashboard, served via Traefik |
| `sentinel-api` | FastAPI backend + background monitoring worker |
| `sentinel-redis` | Redis 7 for real-time incident state and SSE buffers |

### 6. Verify the deployment

```bash
docker compose ps
docker compose logs sentinel-api --tail 50
```

The API should log `Monitoring worker started.` on startup.

Open `https://<SENTINEL_DOMAIN>` (the value you set in `.env`) to access the dashboard.

### 7. Add your first monitoring target

Navigate to `/targets` in the dashboard and create a target:

- **Display Name** — Human-readable label (e.g., `db-prod-01`)
- **Environment** — `prod`, `dev`, or `test`
- **Priority** — Numeric priority (1 = highest); affects Gemini urgency scoring
- **Prom Label** — Full PromQL instance selector (e.g., `instance="db-prod-01:9100"`)
- **Loki Label** — Loki stream selector (e.g., `{app="oracle",host="db-prod-01"}`)
- **DB Type** — Optional: `oracle`, `postgres`, `mysql`, etc.

### 8. Run the baseline learning phase

Click the sync icon next to a target to initiate a 30-day lookback. This queries Prometheus historical data to build the initial MAD/CUSUM statistical fingerprint for that target.

---

## Upgrading

```bash
git pull
docker compose up -d --build
docker compose run --rm sentinel-api alembic upgrade head
```

## Stopping

```bash
docker compose down
```

Data persists in your external PostgreSQL and Redis instances.
