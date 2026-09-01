export type IncidentClassification =
  | "detecting"
  | "expected"
  | "unexpected"
  | "overdue"
  | "resolved"
  | "acknowledged";

export type IncidentStatus =
  | "active"
  | "analyzing"
  | "analyzed"
  | "analysis_error"
  | "acknowledged"
  | "resolved"
  | "overdue";

export type Severity = "INFO" | "WARNING" | "CRITICAL";
export type Environment = "dev" | "test" | "prod";

export interface LogLine {
  log_line: string;
  timestamp: number;
}

export interface GeminiAnalysis {
  is_anomaly: boolean;
  severity: Severity;
  root_cause_analysis: string;
  detected_errors?: string[];
  remediation_steps?: string[];
  confidence_score: number;
}

export interface ActiveIncident {
  id: string;
  target_id: string;
  target_name: string;
  target_env: Environment;
  target_priority: number;
  classification: IncidentClassification;
  status: IncidentStatus;
  start_ts: number;
  expected_end_ts?: number;
  current_metric_value?: number;
  profile_name?: string;
  mad_zscore?: number;
  final_severity?: Severity;

  // Client-side accumulated data
  thoughts: string[];
  logs: LogLine[];
  final_analysis?: GeminiAnalysis;
  isNew?: boolean;
  isFadingOut?: boolean;
}

export interface Target {
  id: string;
  label_name: string;
  display_name: string;
  environment: Environment;
  priority: number;
  auto_notify: boolean;
  prom_label: string;
  loki_label?: string;
  db_type?: string;
  created_at: string;
}

export interface MetricProfile {
  id: string;
  target_id: string;
  profile_name: string;
  expected_duration_minutes: number;
  std_duration_minutes: number;
  mean_peak_cpu: number;
  mean_rise_time_seconds: number;
  mean_integral: number;
  sample_count: number;
  expected_hour_start?: number;
  expected_hour_end?: number;
  last_updated: string;
}

export interface IncidentHistory {
  id: string;
  target_id: string;
  start_ts: string;
  end_ts?: string;
  classification: string;
  final_status: string;
  is_anomaly: boolean;
  raw_metrics?: Record<string, unknown>;
  loki_logs_snapshot?: string;
  llm_thought_process?: string;
  llm_structured_output?: GeminiAnalysis;
  final_severity?: Severity;
  created_at: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  version: number;
  system_message: string;
  json_schema: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

// SSE Event payloads
export interface SSEIncidentCreated {
  id: string;
  target_id: string;
  target_name: string;
  target_env: Environment;
  target_priority: number;
  classification: IncidentClassification;
  status: IncidentStatus;
  start_ts: number;
  expected_end_ts?: number;
  profile_name?: string;
  mad_zscore?: number;
}

export interface SSEIncidentUpdate {
  id: string;
  current_cpu?: number;
  countdown_sec?: number;
  status?: IncidentStatus;
  classification?: IncidentClassification;
  severity?: Severity;
  error?: string;
}

export interface SSEGeminiThought {
  id: string;
  chunk: string;
}

export interface SSEGeminiFinal {
  id: string;
  structured_json: GeminiAnalysis;
}

export interface SSELokiLog {
  id: string;
  log_line: string;
  timestamp: number;
}
