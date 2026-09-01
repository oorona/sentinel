"use client";

import { useEffect, useRef, useState } from "react";
import { Terminal, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { format } from "date-fns";
import type { LogLine } from "@/types";

interface LogTerminalProps {
  logs: LogLine[];
  incidentId: string;
  maxHeight?: string;
}

const LOG_COLORS: Record<string, string> = {
  ERROR: "text-red-400",
  FATAL: "text-red-500 font-bold",
  WARN: "text-yellow-400",
  WARNING: "text-yellow-400",
  INFO: "text-blue-300",
  DEBUG: "text-gray-400",
  "ORA-": "text-red-400 font-bold",
};

function colorizeLog(line: string): string {
  // Highlight Oracle errors, FATAL, etc.
  const upper = line.toUpperCase();
  for (const [key, cls] of Object.entries(LOG_COLORS)) {
    if (upper.includes(key)) return cls;
  }
  return "text-slate-300";
}

export function LogTerminal({ logs, maxHeight = "160px" }: LogTerminalProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [autoScroll, setAutoScroll] = useState(true);

  useEffect(() => {
    if (autoScroll && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const handleScroll = () => {
    const el = containerRef.current;
    if (!el) return;
    const isAtBottom = el.scrollHeight - el.scrollTop <= el.clientHeight + 40;
    setAutoScroll(isAtBottom);
  };

  return (
    <div className="relative flex flex-col rounded-md border border-[#2a2a3e] bg-black/60 overflow-hidden">
      {/* Terminal header */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-[#2a2a3e] bg-[#0d0d14]">
        <div className="flex items-center gap-2">
          <Terminal className="h-3 w-3 text-green-400" />
          <span className="text-xs font-mono text-green-400 font-semibold">LOKI LIVE FEED</span>
        </div>
        <span className="text-xs text-gray-500 font-mono">{logs.length} lines</span>
      </div>

      {/* Log lines */}
      <div
        ref={containerRef}
        onScroll={handleScroll}
        className="terminal-scroll overflow-y-auto font-mono text-xs leading-relaxed"
        style={{ maxHeight }}
      >
        {logs.length === 0 ? (
          <div className="px-3 py-4 text-gray-600 text-center">
            Waiting for logs...
          </div>
        ) : (
          <div className="px-2 py-1">
            {logs.map((log, i) => (
              <div key={i} className="flex gap-2 py-0.5 hover:bg-white/5">
                <span className="text-gray-600 shrink-0">
                  {format(new Date(log.timestamp * 1000), "HH:mm:ss")}
                </span>
                <span className={cn("break-all", colorizeLog(log.log_line))}>
                  {log.log_line}
                </span>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        )}
      </div>

      {/* Auto-scroll indicator */}
      {!autoScroll && (
        <button
          onClick={() => {
            setAutoScroll(true);
            bottomRef.current?.scrollIntoView({ behavior: "smooth" });
          }}
          className="absolute bottom-2 right-2 flex items-center gap-1 rounded bg-blue-600/80 px-2 py-0.5 text-xs text-white hover:bg-blue-600"
        >
          <ChevronDown className="h-3 w-3" />
          Resume
        </button>
      )}
    </div>
  );
}
