"use client";

import { useEffect, useRef, useCallback } from "react";
import type {
  ActiveIncident,
  SSEIncidentCreated,
  SSEIncidentUpdate,
  SSEGeminiThought,
  SSEGeminiFinal,
  SSELokiLog,
} from "@/types";

type IncidentMap = Record<string, ActiveIncident>;
type SetIncidents = React.Dispatch<React.SetStateAction<IncidentMap>>;

export function useSSE(setIncidents: SetIncidents) {
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(() => {
    if (esRef.current) {
      esRef.current.close();
    }

    const es = new EventSource("/api/v1/incidents/stream");
    esRef.current = es;

    es.addEventListener("connected", () => {
      console.log("[SSE] Connected to Sentinel stream.");
    });

    es.addEventListener("incident_created", (e: MessageEvent) => {
      const data: SSEIncidentCreated = JSON.parse(e.data);
      setIncidents((prev) => ({
        ...prev,
        [data.id]: {
          ...data,
          thoughts: [],
          logs: [],
          isNew: true,
        },
      }));
      // Clear the "new" flag after animation
      setTimeout(() => {
        setIncidents((prev) => {
          if (!prev[data.id]) return prev;
          return { ...prev, [data.id]: { ...prev[data.id], isNew: false } };
        });
      }, 1500);
    });

    es.addEventListener("incident_update", (e: MessageEvent) => {
      const data: SSEIncidentUpdate = JSON.parse(e.data);
      setIncidents((prev) => {
        if (!prev[data.id]) return prev;
        return {
          ...prev,
          [data.id]: { ...prev[data.id], ...data },
        };
      });
    });

    es.addEventListener("gemini_thought", (e: MessageEvent) => {
      const data: SSEGeminiThought = JSON.parse(e.data);
      setIncidents((prev) => {
        if (!prev[data.id]) return prev;
        return {
          ...prev,
          [data.id]: {
            ...prev[data.id],
            thoughts: [...(prev[data.id].thoughts || []), data.chunk],
          },
        };
      });
    });

    es.addEventListener("gemini_final", (e: MessageEvent) => {
      const data: SSEGeminiFinal = JSON.parse(e.data);
      setIncidents((prev) => {
        if (!prev[data.id]) return prev;
        return {
          ...prev,
          [data.id]: {
            ...prev[data.id],
            final_analysis: data.structured_json,
            status: "analyzed",
          },
        };
      });
    });

    es.addEventListener("loki_logs", (e: MessageEvent) => {
      const data: SSELokiLog = JSON.parse(e.data);
      setIncidents((prev) => {
        if (!prev[data.id]) return prev;
        const existing = prev[data.id].logs || [];
        // Cap at 500 lines client-side
        const updated = [...existing, { log_line: data.log_line, timestamp: data.timestamp }].slice(-500);
        return {
          ...prev,
          [data.id]: { ...prev[data.id], logs: updated },
        };
      });
    });

    es.onerror = () => {
      console.warn("[SSE] Connection lost. Reconnecting in 3s...");
      es.close();
      esRef.current = null;
      reconnectTimerRef.current = setTimeout(connect, 3000);
    };
  }, [setIncidents]);

  useEffect(() => {
    connect();
    return () => {
      esRef.current?.close();
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
      }
    };
  }, [connect]);
}
