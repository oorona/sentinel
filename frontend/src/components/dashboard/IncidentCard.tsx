"use client";

import { useState } from "react";
import {
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Server,
  ChevronDown,
  ChevronUp,
  Loader2,
} from "lucide-react";
import { formatRelativeTime, classificationColor, cn } from "@/lib/utils";
import { LogTerminal } from "./LogTerminal";
import { GeminiThinkingStream } from "./GeminiThinkingStream";
import { CardCountdown } from "./CardCountdown";
import type { ActiveIncident } from "@/types";

interface IncidentCardProps {
  incident: ActiveIncident;
  onAcknowledge: (id: string) => void;
}

const CLASSIFICATION_LABELS: Record<string, string> = {
  detecting: "Detecting Pattern...",
  expected: "Scheduled Event",
  unexpected: "Anomaly Detected",
  overdue: "Event Overdue",
  resolved: "Resolved",
  acknowledged: "Acknowledged",
};

const STATUS_ICONS: Record<string, React.ReactNode> = {
  analyzing: <Loader2 className="h-3.5 w-3.5 text-blue-400 animate-spin" />,
  analyzed: <CheckCircle2 className="h-3.5 w-3.5 text-green-400" />,
  analysis_error: <XCircle className="h-3.5 w-3.5 text-red-400" />,
  resolved: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
  overdue: <AlertTriangle className="h-3.5 w-3.5 text-red-400 animate-pulse" />,
};

export function IncidentCard({ incident, onAcknowledge }: IncidentCardProps) {
  const [expanded, setExpanded] = useState(true);
  const colors = classificationColor(incident.classification);

  const isActive = !["acknowledged", "resolved"].includes(incident.classification);
  const hasAnalysis = incident.thoughts.length > 0 || !!incident.final_analysis;

  return (
    <div
      className={cn(
        "rounded-lg border-2 transition-all duration-300",
        colors.border,
        colors.bg,
        incident.isNew && "slide-in card-pulse",
        incident.isFadingOut && "fade-out pointer-events-none",
      )}
    >
      {/* Card Header */}
      <div className="flex items-start justify-between gap-3 p-4">
        <div className="flex flex-col gap-1.5 min-w-0">
          {/* Classification badge */}
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={cn(
                "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold",
                colors.badge
              )}
            >
              {CLASSIFICATION_LABELS[incident.classification] ?? incident.classification}
            </span>

            {/* Status icon */}
            {STATUS_ICONS[incident.status]}

            {/* Environment badge */}
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-xs uppercase font-bold",
                incident.target_env === "prod"
                  ? "bg-orange-900/40 text-orange-300"
                  : incident.target_env === "dev"
                  ? "bg-blue-900/30 text-blue-300"
                  : "bg-yellow-900/30 text-yellow-300"
              )}
            >
              {incident.target_env}
            </span>

            <span className="text-xs text-gray-500">P{incident.target_priority}</span>
          </div>

          {/* Target name */}
          <div className="flex items-center gap-2">
            <Server className="h-4 w-4 text-gray-500 shrink-0" />
            <span className="font-semibold text-slate-100 truncate">
              {incident.target_name}
            </span>
          </div>

          {/* Meta: time + CPU */}
          <div className="flex items-center gap-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {formatRelativeTime(incident.start_ts)}
            </span>
            {incident.current_metric_value !== undefined && (
              <span className={colors.text}>
                CPU: {incident.current_metric_value.toFixed(1)}%
              </span>
            )}
            {incident.mad_zscore !== undefined && (
              <span className="text-gray-600">
                Z={incident.mad_zscore.toFixed(1)}σ
              </span>
            )}
            {incident.profile_name && (
              <span className="text-green-400/70">· {incident.profile_name}</span>
            )}
          </div>
        </div>

        {/* Right side: countdown + actions */}
        <div className="flex flex-col items-end gap-2 shrink-0">
          {incident.expected_end_ts && (
            <CardCountdown
              startTs={incident.start_ts}
              expectedEndTs={incident.expected_end_ts}
            />
          )}

          <div className="flex items-center gap-1">
            {isActive && (
              <button
                onClick={() => onAcknowledge(incident.id)}
                className="rounded px-2.5 py-1 text-xs font-medium bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-600 transition-colors"
              >
                Acknowledge
              </button>
            )}
            <button
              onClick={() => setExpanded((v) => !v)}
              className="rounded p-1 text-gray-500 hover:text-gray-300 hover:bg-white/5"
              title={expanded ? "Collapse" : "Expand"}
            >
              {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          </div>
        </div>
      </div>

      {/* Expanded body */}
      {expanded && (
        <div className="flex flex-col gap-3 px-4 pb-4">
          {/* Separator */}
          <div className="h-px bg-[#2a2a3e]" />

          {/* Log terminal + Gemini thinking side-by-side on wide screens */}
          <div
            className={cn(
              "grid gap-3",
              hasAnalysis ? "grid-cols-1 lg:grid-cols-2" : "grid-cols-1"
            )}
          >
            {/* Loki logs */}
            <LogTerminal
              logs={incident.logs}
              incidentId={incident.id}
              maxHeight={hasAnalysis ? "180px" : "200px"}
            />

            {/* Gemini thinking stream (only if analysis triggered) */}
            {hasAnalysis && (
              <GeminiThinkingStream
                thoughts={incident.thoughts}
                finalAnalysis={incident.final_analysis}
                status={incident.status}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
