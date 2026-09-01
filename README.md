# AIOps Sentinel

An AI-powered infrastructure observability platform that combines statistical anomaly detection with large language model reasoning to autonomously detect, classify, and diagnose infrastructure incidents in real time.

---

## AI Capabilities

### Extended Thinking with Gemini 3 Pro

The core intelligence layer uses **Gemini 3 Pro** (`gemini-3-pro-preview`) in extended thinking mode (`ThinkingConfig`). When an anomaly is detected, the model is given a configurable token budget (up to 15,000 thinking tokens) to reason through the problem before producing a diagnosis. The internal reasoning process streams token-by-token to the dashboard, giving operators full visibility into how the AI reached its conclusion.

The thinking follows a structured multi-step reasoning protocol engineered into the system prompt:

1. **Temporal Analysis** — Compare current event duration against the historical expected duration stored in the knowledge base.
2. **Slope Validation** — Determine whether the CPU rise profile is consistent with a batch job signature (sharp, predictable) or genuine degradation (gradual, jittery).
3. **Log Correlation** — Scan the most recent Loki log lines for database-specific error patterns (`ORA-`, `FATAL`, `Deadlock`, `Connection Refused`).
4. **Hypothesis Generation** — Formulate and rank at least two competing causal hypotheses before committing to a conclusion.
5. **Verification** — Cross-validate metric signals against log evidence. Flags as `Ambiguous/Unknown` when metrics indicate a problem but logs are clean — avoiding hallucinated root causes.

### Dual-Model Inference Pipeline

The platform implements a two-stage LLM inference pipeline:

- **Stage 1 — Fast Triage (Gemini 3 Flash):** Instant, non-streaming classification of a new incident (`gemini-3-flash-preview`). Returns `is_anomaly`, `severity`, and a `confidence_score` (0.0–1.0) within seconds. Used to provide immediate visual feedback before the deeper analysis completes.

- **Stage 2 — Deep Analysis (Gemini 3 Pro + Thinking):** Full extended-thinking analysis with a structured output guarantee (`gemini-3-pro-preview`). Only triggered for genuinely unexpected anomalies or expected events that have exceeded their historical duration, conserving token budget.

### Structured Output with JSON Schema Enforcement

All LLM responses are constrained by a strict JSON schema passed via `response_mime_type: "application/json"` and `response_schema`. The final output from every analysis is a validated JSON object containing:

- `is_anomaly` — Boolean classification
- `severity` — Enum: `INFO`, `WARNING`, `CRITICAL`
- `root_cause_analysis` — 2–3 sentence narrative diagnosis
- `detected_errors` — Specific error codes or log snippets the model identified
- `remediation_steps` — Ordered, actionable steps for the on-call engineer
- `confidence_score` — Model's self-assessed certainty (0.0–1.0)

The schema is configurable at runtime without redeployment, allowing prompt engineers to iterate on the output contract live.

### Multi-Modal Context Assembly for RAG-Style Grounding

The LLM is never given raw infrastructure access. Instead, the backend assembles a structured context window from multiple data sources before each inference call:

- **Quantitative signal** — Peak CPU, MAD Z-score, rise time (seconds), integral (area under curve), kurtosis of spike shape, and the last 20 raw metric samples
- **Historical profile** — Expected duration, duration standard deviation, mean peak CPU, mean rise time, sample count, and current overrun delta from the knowledge base
- **Log evidence** — Last 100 lines from Loki for the specific target, fetched at analysis time
- **Target metadata** — Environment (prod/dev/test), priority level, database type

This grounding strategy anchors the LLM to verifiable, structured facts rather than relying solely on pre-trained knowledge, dramatically improving diagnostic accuracy.

### Hybrid AI/Statistical Detection

The LLM is not invoked for every metric fluctuation. A lightweight statistical pre-processing layer acts as the detection gate:

- **Modified Z-Score (MAD):** Computes `0.6745 × (xᵢ − median) / MAD` for each sample. Inherently robust to outliers, unlike standard Z-score which is distorted by the very spikes it is trying to detect.
- **CUSUM Change-Point Detection:** Two one-sided cumulative sum statistics track sustained upward and downward mean shifts. Catches gradual memory leaks or connection pool exhaustion that a threshold-based alert would miss entirely. Provides precise spike start/end timestamps used in feature extraction.
- **Feature Engineering:** Rise time (10%→90% amplitude), integral (total load injected above baseline), and kurtosis (spike shape) are extracted from each detected event and passed to the LLM as quantitative context.

The LLM is only invoked when the statistical layer declares a genuine anomaly or a known event exceeds its expected duration — eliminating noise-driven inference calls.

### Self-Learning Behavioral Profiles

The platform maintains a statistical knowledge base of expected infrastructure events (batch jobs, backups, maintenance windows) per monitored target. Each time a known event completes normally, the profile is updated using **Welford's online algorithm** for incremental mean and variance estimation — no batch reprocessing, no historical data storage required.

Profile matching uses relative tolerance comparisons on peak CPU and integral (energy), classifying incidents as `expected` or `unexpected` before the LLM sees them. This suppresses alert fatigue for routine events and focuses the LLM on genuinely novel situations.

### Configurable Prompt Engineering Lab

A built-in prompt engineering interface (`/prompt-lab`) allows the system prompt and response schema to be edited live and tested against real incident data without redeployment. Changes are persisted to the database and take effect immediately on the next analysis cycle.

This enables iterative refinement of:
- The model's reasoning framework (the five-step thinking protocol)
- The structured output contract (adding fields, changing enums)
- Environment-specific behaviour (e.g., increased urgency for PROD targets)

### Real-Time AI Transparency via SSE

The Gemini thinking process streams directly to the dashboard via Server-Sent Events. Operators can watch the model reason through an incident in real time — observing which hypotheses it considered, which log patterns it correlated, and why it reached its conclusion. The full thought process and structured verdict are persisted to PostgreSQL with every incident, forming an auditable AI decision log.

---

## Technology

| Layer | Technology |
|---|---|
| AI / LLM | Google Gemini 3 Pro (thinking), Gemini 3 Flash (`google-genai` SDK 1.x) |
| Statistical Engine | NumPy, SciPy — MAD, CUSUM, kurtosis, Welford's algorithm |
| Backend | Python 3.12, FastAPI 0.115, asyncio, SSE |
| Frontend | Next.js 15, React 19, Tailwind CSS v4 |
| Database | PostgreSQL 16, SQLAlchemy 2 (async), Alembic |
| Cache / State | Redis 7 (pub/sub SSE broadcast) |
| Metrics Source | Prometheus v3 |
| Log Source | Loki 3.x |
| Proxy / TLS | Traefik v3 + Let's Encrypt |

---

## Documentation

- [Installation](docs/INSTALLATION.md) — Prerequisites, setup steps, first target configuration
- [Configuration](docs/CONFIGURATION.md) — Environment variables, Docker secrets, Gemini model tuning, threshold reference
- [Architecture](docs/ARCHITECTURE.md) — System design, data flow, component breakdown, database schema

## License

See [LICENSE](LICENSE).
