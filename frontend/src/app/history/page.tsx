"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format } from "date-fns";
import { historyApi, targetsApi } from "@/lib/api";
import { cn, severityBg } from "@/lib/utils";
import { ChevronDown, ChevronRight, FileText, AlertCircle } from "lucide-react";
import type { IncidentHistory, Target } from "@/types";

export default function HistoryPage() {
  const [selectedTarget, setSelectedTarget] = useState<string>("");
  const [classification, setClassification] = useState<string>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: targets = [] } = useQuery({
    queryKey: ["targets"],
    queryFn: targetsApi.list,
  });

  const { data: incidents = [], isLoading } = useQuery({
    queryKey: ["history", selectedTarget, classification],
    queryFn: () =>
      historyApi.list({
        target_id: selectedTarget || undefined,
        classification: classification || undefined,
        limit: 100,
      }),
  });

  const targetMap = Object.fromEntries((targets as Target[]).map((t) => [t.id, t]));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-100">Incident History</h1>
        <p className="text-sm text-gray-500 mt-0.5">
          Searchable log of all acknowledged and resolved incidents
        </p>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-wrap">
        <select
          value={selectedTarget}
          onChange={(e) => setSelectedTarget(e.target.value)}
          className="rounded-md border border-[#2a2a3e] bg-[#12121a] px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="">All Targets</option>
          {(targets as Target[]).map((t) => (
            <option key={t.id} value={t.id}>
              {t.display_name}
            </option>
          ))}
        </select>

        <select
          value={classification}
          onChange={(e) => setClassification(e.target.value)}
          className="rounded-md border border-[#2a2a3e] bg-[#12121a] px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-blue-500"
        >
          <option value="">All Classifications</option>
          <option value="expected">Expected</option>
          <option value="unexpected">Unexpected</option>
          <option value="overdue">Overdue</option>
        </select>

        <span className="text-sm text-gray-500">
          {incidents.length} incidents
        </span>
      </div>

      {/* Table */}
      <div className="rounded-lg border border-[#2a2a3e] bg-[#12121a] overflow-hidden">
        {isLoading ? (
          <div className="py-16 text-center text-gray-500">Loading history...</div>
        ) : incidents.length === 0 ? (
          <div className="flex flex-col items-center py-16 gap-2 text-gray-500">
            <FileText className="h-8 w-8" />
            <span>No incidents found</span>
          </div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#2a2a3e] text-xs text-gray-500 uppercase tracking-wider">
                <th className="px-4 py-3 text-left w-6" />
                <th className="px-4 py-3 text-left">Target</th>
                <th className="px-4 py-3 text-left">Classification</th>
                <th className="px-4 py-3 text-left">Severity</th>
                <th className="px-4 py-3 text-left">Start</th>
                <th className="px-4 py-3 text-left">Duration</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody>
              {(incidents as IncidentHistory[]).map((inc) => {
                const isExpanded = expandedId === inc.id;
                const target = targetMap[inc.target_id];
                const duration =
                  inc.end_ts
                    ? Math.round(
                        (new Date(inc.end_ts).getTime() -
                          new Date(inc.start_ts).getTime()) /
                          60000
                      )
                    : null;

                return (
                  <>
                    <tr
                      key={inc.id}
                      className="border-b border-[#1a1a26] hover:bg-white/5 cursor-pointer"
                      onClick={() => setExpandedId(isExpanded ? null : inc.id)}
                    >
                      <td className="px-4 py-3">
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5 text-gray-500" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 text-gray-500" />
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium text-slate-200">
                        {target?.display_name ?? inc.target_id.slice(0, 8)}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            "rounded px-2 py-0.5 text-xs font-semibold",
                            inc.classification === "unexpected" || inc.classification === "overdue"
                              ? "bg-red-900/40 text-red-300"
                              : "bg-green-900/30 text-green-300"
                          )}
                        >
                          {inc.classification}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        {inc.final_severity && (
                          <span
                            className={cn(
                              "rounded px-2 py-0.5 text-xs font-semibold border",
                              severityBg(inc.final_severity)
                            )}
                          >
                            {inc.final_severity}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-400 tabular-nums">
                        {format(new Date(inc.start_ts), "MMM d, HH:mm")}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-400 tabular-nums">
                        {duration != null ? `${duration}m` : "—"}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-xs text-gray-500">{inc.final_status}</span>
                      </td>
                    </tr>

                    {isExpanded && inc.llm_structured_output && (
                      <tr key={`${inc.id}-detail`} className="bg-[#0d0d14]">
                        <td colSpan={7} className="px-6 py-4">
                          <div className="flex flex-col gap-3">
                            {/* Root cause */}
                            <div>
                              <span className="text-xs text-blue-400 font-semibold uppercase">Root Cause Analysis</span>
                              <p className="mt-1 text-sm text-slate-300">
                                {inc.llm_structured_output.root_cause_analysis}
                              </p>
                            </div>

                            {/* Remediation */}
                            {inc.llm_structured_output.remediation_steps && (
                              <div>
                                <span className="text-xs text-green-400 font-semibold uppercase">Remediation Steps</span>
                                <ol className="mt-1 space-y-1 list-decimal list-inside">
                                  {(inc.llm_structured_output.remediation_steps as string[]).map(
                                    (step, i) => (
                                      <li key={i} className="text-xs text-slate-400">{step}</li>
                                    )
                                  )}
                                </ol>
                              </div>
                            )}

                            {/* Logs snapshot */}
                            {inc.loki_logs_snapshot && (
                              <div>
                                <span className="text-xs text-gray-500 font-semibold uppercase">Logs Snapshot</span>
                                <pre className="mt-1 rounded bg-black/40 p-2 text-xs font-mono text-gray-400 overflow-auto max-h-32">
                                  {inc.loki_logs_snapshot}
                                </pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
