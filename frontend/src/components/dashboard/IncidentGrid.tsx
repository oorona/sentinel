"use client";

import { Activity } from "lucide-react";
import { IncidentCard } from "./IncidentCard";
import type { ActiveIncident } from "@/types";

interface IncidentGridProps {
  incidents: ActiveIncident[];
  onAcknowledge: (id: string) => void;
}

export function IncidentGrid({ incidents, onAcknowledge }: IncidentGridProps) {
  if (incidents.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-center">
        <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-900/20 border border-green-700/30">
          <Activity className="h-8 w-8 text-green-400" />
        </div>
        <h3 className="text-lg font-semibold text-slate-300">All Systems Nominal</h3>
        <p className="mt-1 text-sm text-gray-500">
          No active incidents detected. The monitoring worker is polling every 30 seconds.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 grid-cols-1 xl:grid-cols-2">
      {incidents.map((incident) => (
        <IncidentCard
          key={incident.id}
          incident={incident}
          onAcknowledge={onAcknowledge}
        />
      ))}
    </div>
  );
}
