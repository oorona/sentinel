# Architecture

## System Overview

AIOps Sentinel is a self-contained observability platform built around a hybrid AI pipeline. A background worker continuously polls infrastructure metrics, applies statistical anomaly detection, and conditionally invokes a large language model for root cause analysis. All state and analysis results are streamed in real-time to a browser dashboard via Server-Sent Events.

```
Browser (Next.js)
        ↑
        │  SSE stream (incidents, logs, Gemini thoughts)
        │
  FastAPI  ─────────────────────────────────────────────────────────┐
        │                                                            │
  Monitoring Worker (30s poll)                               Gemini API
        │                                                     (Gemini 3 Pro / 3 Flash)
        ├── Prometheus ──► MAD/CUSUM Engine ──► Incident Manager ──► run_gemini_analysis()
        │                                              │
        ├── Loki (logs) ───────────────────────────────┤
        │                                              │
        └── PostgreSQL (profiles/history) ─────────────┘
                                                       │
                                                  Redis (active state / SSE buffers)
```

---

## Components

### Monitoring Worker (`backend/app/workers/monitoring_worker.py`)

The central polling loop. Runs as a background asyncio task inside the FastAPI process.

**Cycle (every `PROMETHEUS_POLL_INTERVAL_SECONDS`, default 30s):**

1. Load all configured targets from PostgreSQL.
2. For each target, fetch the last `PROMETHEUS_LOOKBACK_MINUTES` of CPU time series from Prometheus.
3. Run the MAD/CUSUM math engine against the time series.
4. Based on the result, manage the incident lifecycle (create, update, escalate, resolve).
5. On a separate ticker (`LOKI_POLL_INTERVAL_SECONDS`), tail new Loki log lines for all active incidents and stream them to the UI.

All targets are processed concurrently via `asyncio.gather()`.

---

### Math Engine (`backend/app/services/math_engine.py`)

Pure NumPy/SciPy statistical processing. No I/O — receives arrays, returns dataclasses.

**Modified Z-Score (MAD)**

```
modified_z_score = 0.6745 × (xᵢ − median) / MAD
```

Uses the median absolute deviation instead of the standard deviation, making it robust to outliers that would inflate a classical Z-score. A point is flagged as anomalous when `|modified_z_score| > MAD_ZSCORE_THRESHOLD` (default 3.5).

**CUSUM Change-Point Detection**

Two one-sided CUSUM statistics track upward and downward mean shifts:

```
C⁺ᵢ = max(0, C⁺ᵢ₋₁ + (xᵢ − μ₀ − k))
C⁻ᵢ = max(0, C⁻ᵢ₋₁ − (xᵢ − μ₀ + k))
```

An alarm fires when either statistic exceeds the threshold `H = alarm_threshold × σ`. The algorithm back-tracks to find the true start of the shift, producing precise `spike_start_idx` and `spike_end_idx` values.

**Feature Extraction**

For each detected spike:
- **Rise time** — seconds from 10% to 90% of peak amplitude (distinguishes sharp batch signatures from gradual degradation)
- **Integral** — area under the curve above baseline (proxy for total CPU load injected)
- **Kurtosis** — shape of the spike (peakedness vs. flat-top)

**Profile Matching**

A live anomaly signal is compared against stored `MetricProfile` records. A match is declared when the peak CPU and integral fall within configurable relative tolerances. A match classifies the incident as `expected`; no match classifies it as `unexpected`.

**Online Profile Updates (Welford's Algorithm)**

When an expected event resolves normally, the profile is updated incrementally without storing all historical observations:

```
n ← n + 1
δ ← new_value − old_mean
new_mean ← old_mean + δ/n
```

---

### Incident Manager (`backend/app/services/incident_manager.py`)

Orchestrates the incident lifecycle. Decoupled from both the worker and the Gemini service.

**Incident States**

```
detected → expected  ─────────────────────────────► resolved (auto, metric normalised)
         → unexpected ──► analyzing ──► analyzed ──► acknowledged (manual)
                         (Gemini)
         → overdue ──────► analyzing ──► analyzed    (expected event exceeded duration)
```

**Trigger Logic**

| Event type | Gemini triggered? | Model used |
|---|---|---|
| Unexpected anomaly | Immediately | Gemini 3 Pro (full thinking) |
| Expected event overdue | After `duration × EXPECTED_OVERRUN_MULTIPLIER` | Gemini 3 Pro (medium thinking budget) |
| Expected event resolved normally | No | — |

---

### Gemini Service (`backend/app/services/gemini_service.py`)

Wraps the `google-genai` Python SDK. Two inference paths:

**Deep Analysis — `stream_analysis()` (Gemini 3 Pro)**

Uses `ThinkingConfig(include_thoughts=True, thinking_budget=N)`. The model streams two types of parts:
- `thought=True` parts → forwarded to the UI as `GEMINI_THOUGHT` SSE events (the live reasoning stream)
- Response text parts → accumulated into a JSON buffer

The call uses `response_mime_type="application/json"` with a strict `response_schema`, guaranteeing the final output conforms to the defined structure regardless of model verbosity.

**Fast Triage — `quick_classify()` (Gemini 3 Flash)**

Single non-streaming call with a minimal schema (`is_anomaly`, `severity`, `confidence_score`, `root_cause_analysis`). Used for low-latency initial classification before the Pro model completes its analysis.

**Context Assembly**

The prompt fed to Gemini contains four structured sections:

```
<TARGET_INFO>  — name, environment, priority, DB type
<METRICS>      — peak CPU, MAD Z-score, rise time, integral, kurtosis, recent value array
<HISTORY>      — matched profile stats (expected duration, std, sample count, overrun delta)
<LOGS>         — last N lines from Loki for the target
```

This multi-modal context assembly enables the model to correlate quantitative anomaly features with qualitative log evidence.

**Prompt Lab — `test_prompt()`**

Exposes the full inference pipeline (thinking + structured output) to the `/prompt-lab` UI endpoint, allowing live editing of the system prompt and response schema against real incident data.

---

### SSE Manager (`backend/app/services/sse_manager.py`)

All real-time communication from the backend to the browser uses Server-Sent Events over a single `/api/v1/events` endpoint. Redis pub/sub is used as the broadcast layer so that multiple API worker processes can all publish to the same event stream.

**Event types:**

| Event | Payload |
|---|---|
| `incident_created` | Full incident card data |
| `incident_update` | Partial update (status, severity, countdown) |
| `gemini_thought` | Streaming thought chunk (text) |
| `gemini_final` | Complete structured JSON verdict |
| `loki_logs` | New log line with timestamp |

---

### FastAPI Application (`backend/app/main.py`)

Async FastAPI application. Routers:

| Router | Path | Responsibilities |
|---|---|---|
| `targets` | `/api/v1/targets` | CRUD for monitoring targets and metric profiles |
| `incidents` | `/api/v1/incidents` | List active/historical incidents, acknowledge, run manual Gemini analysis |
| `prompts` | `/api/v1/prompts` | CRUD for prompt templates (Prompt Lab) |
| `history` | `/api/v1/history` | Searchable incident history with LLM output |

The monitoring worker is started as a background task on application startup via `lifespan`.

---

### Database Schema (PostgreSQL)

**`targets`** — monitoring targets
**`metric_profiles`** — learned spike fingerprints per target (MAD/CUSUM statistical profiles)
**`incident_history`** — full incident record including raw metrics, Loki log snapshot, LLM thought process, and structured JSON verdict
**`prompt_templates`** — user-editable system prompts and response schemas

Database access is fully async using SQLAlchemy 2 with `asyncpg`. Schema migrations are managed by Alembic.

---

### Frontend (`frontend/`)

Next.js 15 App Router application with React 19 and Tailwind CSS v4.

**Key components:**

| Component | Purpose |
|---|---|
| `IncidentGrid` | Live grid of incident cards, updated via SSE |
| `IncidentCard` | Single card: classification badge, countdown timer, severity indicator |
| `GeminiThinkingStream` | Real-time display of Gemini's reasoning process as it streams |
| `LogTerminal` | Live log viewer receiving Loki lines via SSE |
| `CardCountdown` | Countdown timer showing remaining expected duration |

**Data flow:**
API queries use React Query (`@tanstack/react-query`) for caching and refetching. The SSE connection is managed by a custom `useSSE` hook that merges server-pushed updates into the React Query cache, avoiding full re-fetches for incremental updates.

---

## Docker Network Topology

```
┌──────────────┐     internet     ┌─────────────────────────────────┐
│   Traefik    │◄────────────────►│  sentinel-ui  (Next.js :3000)   │
└──────────────┘                  └────────────┬────────────────────┘
                                               │ intranet (/api/* proxy)
                                  ┌────────────▼────────────────────┐
                                  │  sentinel-api (FastAPI :8000)   │
                                  └────────────┬────────────────────┘
                                               │ dbnet
                         ┌─────────────────────┼──────────────────────┐
                         ▼                     ▼                      ▼
                    PostgreSQL              Redis              Prometheus / Loki
```

- `internet` — Traefik ↔ sentinel-ui (public HTTPS traffic)
- `intranet` — sentinel-ui ↔ sentinel-api (internal proxy, API never internet-exposed)
- `dbnet` — sentinel-api ↔ all data stores and observability backends

Credentials are injected via Docker secrets (`/run/secrets/`). The API container has no internet-facing ports.
