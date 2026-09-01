"use client";

import { useEffect } from "react";
import { IncidentGrid } from "@/components/dashboard/IncidentGrid";
import { useIncidents } from "@/hooks/useIncidents";
import { useSSE } from "@/hooks/useSSE";
import { incidentsApi } from "@/lib/api";
import type { ActiveIncident } from "@/types";

export default function DashboardPage() {
  const { incidents, setIncidents, incidentList, acknowledgeIncident } = useIncidents();

  // Connect SSE
  useSSE(setIncidents);

  // Hydrate with any already-active incidents on first load
  useEffect(() => {
    incidentsApi.getActive().then((active) => {
      const map: Record<string, ActiveIncident> = {};
      for (const inc of active as ActiveIncident[]) {
        if (inc.id) {
          map[inc.id] = {
            ...inc,
            thoughts: [],
            logs: [],
          };
        }
      }
      setIncidents((prev) => ({ ...map, ...prev }));
    }).catch(() => {
      // API not yet available — SSE will hydrate when ready
    });
  }, [setIncidents]);

  const activeCount = incidentList.filter(
    (i) => !["acknowledged", "resolved"].includes(i.classification)
  ).length;
  const anomalyCount = incidentList.filter(
    (i) => i.classification === "unexpected" || i.classification === "overdue"
  ).length;

  return (
    <div className="flex flex-col gap-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Live Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Real-time anomaly detection across all monitored targets
          </p>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold tabular-nums text-slate-100">{activeCount}</div>
            <div className="text-xs text-gray-500">Active</div>
          </div>
          <div className="h-8 w-px bg-[#2a2a3e]" />
          <div className="text-center">
            <div
              className={`text-2xl font-bold tabular-nums ${
                anomalyCount > 0 ? "text-red-400" : "text-green-400"
              }`}
            >
              {anomalyCount}
            </div>
            <div className="text-xs text-gray-500">Anomalies</div>
          </div>
        </div>
      </div>

      {/* Incident grid */}
      <IncidentGrid incidents={incidentList} onAcknowledge={acknowledgeIncident} />
    </div>
  );
}
