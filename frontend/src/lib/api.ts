import type { Target, IncidentHistory, PromptTemplate, MetricProfile, ActiveIncident } from "@/types";

// The API lives at the same domain as the UI (/api/v1).
// All calls use relative paths — no NEXT_PUBLIC_API_URL needed.
const API_BASE = "/api/v1";

async function fetchJSON<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API ${res.status}: ${err}`);
  }
  return res.json() as Promise<T>;
}

// --- Targets ---
export const targetsApi = {
  list: () => fetchJSON<Target[]>("/targets"),
  create: (body: Omit<Target, "id" | "created_at">) =>
    fetchJSON<Target>("/targets", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: Partial<Target>) =>
    fetchJSON<Target>(`/targets/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  delete: (id: string) =>
    fetchJSON<void>(`/targets/${id}`, { method: "DELETE" }),
  getProfiles: (id: string) =>
    fetchJSON<MetricProfile[]>(`/targets/${id}/profiles`),
  triggerLearning: (id: string) =>
    fetchJSON<{ status: string }>(`/targets/${id}/learn`, { method: "POST" }),
};

// --- Incidents ---
export const incidentsApi = {
  getActive: () => fetchJSON<ActiveIncident[]>("/incidents/active"),
  acknowledge: (id: string, notes?: string) =>
    fetchJSON<{ status: string }>(`/incidents/${id}/ack`, {
      method: "POST",
      body: JSON.stringify({ incident_id: id, notes }),
    }),
  getLogs: (id: string) =>
    fetchJSON<{ logs: string[] }>(`/incidents/${id}/logs`),
};

// --- History ---
export const historyApi = {
  list: (params?: {
    target_id?: string;
    classification?: string;
    severity?: string;
    is_anomaly?: boolean;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null) qs.append(k, String(v));
      });
    }
    return fetchJSON<IncidentHistory[]>(`/history?${qs}`);
  },
  get: (id: string) => fetchJSON<IncidentHistory>(`/history/${id}`),
};

// --- Prompts ---
export const promptsApi = {
  list: () => fetchJSON<PromptTemplate[]>("/prompts"),
  create: (body: { name: string; system_message: string; json_schema: object }) =>
    fetchJSON<PromptTemplate>("/prompts", { method: "POST", body: JSON.stringify(body) }),
  update: (id: string, body: Partial<PromptTemplate>) =>
    fetchJSON<PromptTemplate>(`/prompts/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  delete: (id: string) =>
    fetchJSON<void>(`/prompts/${id}`, { method: "DELETE" }),
  test: (id: string) =>
    fetchJSON<{
      thought_process: string;
      structured_output: Record<string, unknown> | null;
      raw_json: string;
    }>(`/prompts/${id}/test`, { method: "POST" }),
};

// --- Status ---
export const statusApi = {
  get: () => fetchJSON<{ api: string; redis: string }>("/status"),
};

// --- Settings ---
export interface SettingsConfig {
  database: { host: string; port: number; name: string; user: string };
  services: { redis_url: string; prometheus_url: string; loki_url: string };
  ai: {
    pro_model: string;
    flash_model: string;
    thinking_budget: number;
    thinking_budget_medium: number;
    api_key_configured: boolean;
  };
  monitoring: {
    poll_interval_seconds: number;
    lookback_minutes: number;
    loki_log_lines: number;
    loki_poll_interval_seconds: number;
    mad_zscore_threshold: number;
    cusum_slack_multiplier: number;
    cusum_alarm_threshold: number;
    expected_overrun_multiplier: number;
    learning_window_days: number;
  };
}

export interface DbTestResult {
  connected: boolean;
  schema_ok: boolean;
  tables?: Record<string, boolean>;
  alembic_version?: string;
  error?: string;
}

export const settingsApi = {
  getConfig: () => fetchJSON<SettingsConfig>("/settings"),
  testDb: () => fetchJSON<DbTestResult>("/settings/test-db", { method: "POST" }),
};
