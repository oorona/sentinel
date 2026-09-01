"use client";

import { useState, useEffect, useRef } from "react";

/**
 * Countdown hook: computes remaining seconds until `expectedEndTs` (Unix timestamp).
 * Updates every second. Computed locally in browser for pixel-perfect accuracy.
 */
export function useCountdown(expectedEndTs: number | undefined | null): {
  remainingSeconds: number;
  isOverdue: boolean;
  progress: number; // 0-100 progress percentage
  startTs?: number;
} {
  const [remaining, setRemaining] = useState<number>(-1);
  const startTsRef = useRef<number | null>(null);

  useEffect(() => {
    if (!expectedEndTs) {
      setRemaining(-1);
      return;
    }

    const tick = () => {
      const now = Date.now() / 1000;
      const diff = expectedEndTs - now;
      setRemaining(diff);
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [expectedEndTs]);

  if (!expectedEndTs) {
    return { remainingSeconds: -1, isOverdue: false, progress: 0 };
  }

  const now = Date.now() / 1000;
  const totalDuration = expectedEndTs - (startTsRef.current || expectedEndTs - 3600);
  const elapsed = now - (expectedEndTs - totalDuration);
  const progress = Math.min(100, Math.max(0, (elapsed / totalDuration) * 100));

  return {
    remainingSeconds: remaining,
    isOverdue: remaining < 0,
    progress,
  };
}

export function useCountdownFromDates(
  startTs: number,
  expectedEndTs: number | undefined | null
): { remainingSeconds: number; isOverdue: boolean; progress: number } {
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    if (!expectedEndTs) return;
    const id = setInterval(() => forceUpdate((n) => n + 1), 1000);
    return () => clearInterval(id);
  }, [expectedEndTs]);

  if (!expectedEndTs) {
    return { remainingSeconds: -1, isOverdue: false, progress: 0 };
  }

  const now = Date.now() / 1000;
  const remaining = expectedEndTs - now;
  const totalDuration = expectedEndTs - startTs;
  const elapsed = now - startTs;
  const progress = totalDuration > 0
    ? Math.min(100, Math.max(0, (elapsed / totalDuration) * 100))
    : 0;

  return {
    remainingSeconds: remaining,
    isOverdue: remaining < 0,
    progress,
  };
}
