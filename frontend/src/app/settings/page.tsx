"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";
import {
  Database,
  Server,
  BrainCircuit,
  SlidersHorizontal,
  CheckCircle2,
  XCircle,
  Loader2,
  ShieldCheck,
  ShieldX,
} from "lucide-react";
import { settingsApi, type DbTestResult } from "@/lib/api";
import { cn } from "@/lib/utils";

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ElementType;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-[#2a2a3e] bg-[#12121a] overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b border-[#2a2a3e] bg-[#0e0e16]">
        <Icon className="h-4 w-4 text-blue-400" />
        <span className="text-sm font-semibold text-slate-200">{title}</span>
      </div>
      <div className="p-5">{children}</div>
    </div>
  );
}

function Row({ label, value, mono = false }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-2 border-b border-[#1a1a26] last:border-0">
      <span className="text-sm text-slate-400">{label}</span>
      <span className={cn("text-sm text-slate-200", mono && "font-mono text-xs text-slate-300")}>
        {value}
      </span>
    </div>
  );
}

function StatusBadge({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-xs font-medium",
        ok ? "bg-green-900/40 text-green-300" : "bg-red-900/40 text-red-300"
      )}
    >
      {ok ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
      {label}
    </span>
  );
}

function DbTestPanel({ result }: { result: DbTestResult }) {
  return (
    <div
      className={cn(
        "mt-4 rounded-lg border p-4",
        result.connected && result.schema_ok
          ? "border-green-500/30 bg-green-900/10"
          : "border-red-500/30 bg-red-900/10"
      )}
    >
      <div className="flex items-center gap-2 mb-3">
        {result.connected ? (
          <ShieldCheck className="h-4 w-4 text-green-400" />
        ) : (
          <ShieldX className="h-4 w-4 text-red-400" />
        )}
        <span className="text-sm font-semibold text-slate-200">
          {result.connected ? "Connection successful" : "Connection failed"}
        </span>
        {result.connected && (
          <StatusBadge ok={result.schema_ok} label={result.schema_ok ? "Schema OK" : "Schema mismatch"} />
        )}
      </div>

      {result.error && (
        <p className="text-xs text-red-400 font-mono mb-3">{result.error}</p>
      )}

      {result.tables && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(result.tables).map(([table, present]) => (
            <StatusBadge key={table} ok={present} label={table} />
          ))}
        </div>
      )}

      {result.alembic_version && (
        <p className="mt-3 text-xs text-slate-500 font-mono">
          Alembic revision: {result.alembic_version}
        </p>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const [dbResult, setDbResult] = useState<DbTestResult | null>(null);

  const { data: config, isLoading } = useQuery({
    queryKey: ["settings"],
    queryFn: settingsApi.getConfig,
  });

  const testMutation = useMutation({
    mutationFn: settingsApi.testDb,
    onSuccess: (data) => setDbResult(data),
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin mr-2" />
        Loading configuration…
      </div>
    );
  }

  if (!config) return null;

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">System Settings</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Runtime configuration loaded from environment variables and Docker secrets.
          All values are read-only — edit <code className="text-xs text-blue-400">.env</code> and redeploy to change.
        </p>
      </div>

      {/* Database */}
      <Section icon={Database} title="Database">
        <Row label="Host" value={config.database.host} mono />
        <Row label="Port" value={config.database.port} mono />
        <Row label="Database" value={config.database.name} mono />
        <Row label="User" value={config.database.user} mono />
        <Row label="Password" value={<span className="text-slate-500 text-xs">managed via Docker secret</span>} />

        <div className="mt-4">
          <button
            onClick={() => testMutation.mutate()}
            disabled={testMutation.isPending}
            className="flex items-center gap-2 rounded-md border border-blue-500/40 bg-blue-600/10 px-4 py-2 text-sm font-medium text-blue-300 hover:bg-blue-600/20 disabled:opacity-50"
          >
            {testMutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Database className="h-3.5 w-3.5" />
            )}
            {testMutation.isPending ? "Testing…" : "Test Connection & Verify Schema"}
          </button>
        </div>

        {dbResult && <DbTestPanel result={dbResult} />}
      </Section>

      {/* External Services */}
      <Section icon={Server} title="External Services">
        <Row label="Redis" value={config.services.redis_url} mono />
        <Row label="Prometheus" value={config.services.prometheus_url} mono />
        <Row label="Loki" value={config.services.loki_url} mono />
      </Section>

      {/* AI Models */}
      <Section icon={BrainCircuit} title="AI Models">
        <Row label="Pro model (thinking)" value={config.ai.pro_model} mono />
        <Row label="Flash model (fast triage)" value={config.ai.flash_model} mono />
        <Row label="Thinking budget (deep)" value={`${config.ai.thinking_budget.toLocaleString()} tokens`} />
        <Row label="Thinking budget (medium)" value={`${config.ai.thinking_budget_medium.toLocaleString()} tokens`} />
        <Row
          label="API key"
          value={
            <StatusBadge
              ok={config.ai.api_key_configured}
              label={config.ai.api_key_configured ? "Configured" : "Not configured"}
            />
          }
        />
      </Section>

      {/* Monitoring */}
      <Section icon={SlidersHorizontal} title="Monitoring & Detection Thresholds">
        <Row label="Prometheus poll interval" value={`${config.monitoring.poll_interval_seconds}s`} />
        <Row label="Lookback window" value={`${config.monitoring.lookback_minutes} min`} />
        <Row label="Loki log lines per analysis" value={config.monitoring.loki_log_lines} />
        <Row label="Loki poll interval" value={`${config.monitoring.loki_poll_interval_seconds}s`} />
        <Row label="MAD Z-score threshold" value={config.monitoring.mad_zscore_threshold} />
        <Row label="CUSUM slack multiplier" value={config.monitoring.cusum_slack_multiplier} />
        <Row label="CUSUM alarm threshold" value={config.monitoring.cusum_alarm_threshold} />
        <Row label="Overrun multiplier" value={`× ${config.monitoring.expected_overrun_multiplier}`} />
        <Row label="Learning window" value={`${config.monitoring.learning_window_days} days`} />
      </Section>
    </div>
  );
}
