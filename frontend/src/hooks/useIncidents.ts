"use client";

import { useState, useCallback } from "react";
import type { ActiveIncident } from "@/types";
import { incidentsApi } from "@/lib/api";

type IncidentMap = Record<string, ActiveIncident>;

export function useIncidents(initialIncidents: IncidentMap = {}) {
  const [incidents, setIncidents] = useState<IncidentMap>(initialIncidents);

  const acknowledgeIncident = useCallback(
    async (id: string, notes?: string) => {
      // Optimistic: fade out immediately
      setIncidents((prev) => ({
        ...prev,
        [id]: { ...prev[id], isFadingOut: true, status: "acknowledged" },
      }));

      try {
        await incidentsApi.acknowledge(id, notes);
      } catch (err) {
        console.error("Failed to acknowledge incident:", err);
        // Revert
        setIncidents((prev) => ({
          ...prev,
          [id]: { ...prev[id], isFadingOut: false, status: "active" },
        }));
        return;
      }

      // Remove from map after animation
      setTimeout(() => {
        setIncidents((prev) => {
          const updated = { ...prev };
          delete updated[id];
          return updated;
        });
      }, 600);
    },
    []
  );

  const incidentList = Object.values(incidents).sort((a, b) => {
    // Active anomalies first, then expected, then resolved
    const priority = (inc: ActiveIncident) => {
      if (inc.classification === "unexpected" || inc.classification === "overdue") return 0;
      if (inc.classification === "expected") return 1;
      return 2;
    };
    const pa = priority(a);
    const pb = priority(b);
    if (pa !== pb) return pa - pb;
    return b.start_ts - a.start_ts;
  });

  return { incidents, setIncidents, incidentList, acknowledgeIncident };
}
