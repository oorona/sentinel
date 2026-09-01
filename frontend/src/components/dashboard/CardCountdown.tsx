"use client";

import { Clock, AlertTriangle } from "lucide-react";
import { useCountdownFromDates } from "@/hooks/useCountdown";
import { formatDuration } from "@/lib/utils";

interface CardCountdownProps {
  startTs: number;
  expectedEndTs: number;
}

export function CardCountdown({ startTs, expectedEndTs }: CardCountdownProps) {
  const { remainingSeconds, isOverdue, progress } = useCountdownFromDates(
    startTs,
    expectedEndTs
  );

  return (
    <div className="flex flex-col gap-1.5">
      {/* Timer display */}
      <div className="flex items-center gap-2">
        {isOverdue ? (
          <AlertTriangle className="h-3.5 w-3.5 text-red-400 animate-pulse" />
        ) : (
          <Clock className="h-3.5 w-3.5 text-green-400" />
        )}
        <span
          className={`font-mono text-sm font-bold tabular-nums ${
            isOverdue ? "text-red-400" : "text-green-300"
          }`}
        >
          {isOverdue
            ? `+${formatDuration(Math.abs(remainingSeconds))}`
            : formatDuration(remainingSeconds)}
        </span>
        {isOverdue && (
          <span className="text-xs text-red-400/70">overdue</span>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-1.5 w-full rounded-full bg-white/10 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-1000 ${
            isOverdue
              ? "bg-red-500"
              : progress > 80
              ? "bg-yellow-500"
              : "bg-green-500"
          }`}
          style={{ width: `${Math.min(100, progress)}%` }}
        />
      </div>
    </div>
  );
}
