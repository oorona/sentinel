import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { IncidentClassification, Severity } from "@/types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDuration(seconds: number): string {
  if (seconds < 0) return "00:00:00";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return [h, m, s].map((v) => String(v).padStart(2, "0")).join(":");
}

export function formatRelativeTime(ts: number): string {
  const diff = Date.now() / 1000 - ts;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function classificationColor(cls: IncidentClassification): {
  border: string;
  bg: string;
  badge: string;
  text: string;
} {
  switch (cls) {
    case "expected":
      return {
        border: "border-green-600",
        bg: "bg-[#0d1f14]",
        badge: "bg-green-900/60 text-green-300 border-green-700",
        text: "text-green-400",
      };
    case "unexpected":
    case "overdue":
      return {
        border: "border-red-600",
        bg: "bg-[#1f0d0d]",
        badge: "bg-red-900/60 text-red-300 border-red-700",
        text: "text-red-400",
      };
    case "resolved":
    case "acknowledged":
      return {
        border: "border-gray-600",
        bg: "bg-[#141420] opacity-60",
        badge: "bg-gray-800 text-gray-400 border-gray-600",
        text: "text-gray-400",
      };
    default: // detecting
      return {
        border: "border-gray-500",
        bg: "bg-[#141420]",
        badge: "bg-gray-800/60 text-gray-300 border-gray-600",
        text: "text-gray-400",
      };
  }
}

export function severityColor(severity: Severity | undefined): string {
  switch (severity) {
    case "CRITICAL": return "text-red-400";
    case "WARNING": return "text-yellow-400";
    case "INFO": return "text-blue-400";
    default: return "text-gray-400";
  }
}

export function severityBg(severity: Severity | undefined): string {
  switch (severity) {
    case "CRITICAL": return "bg-red-900/40 border-red-700 text-red-300";
    case "WARNING": return "bg-yellow-900/40 border-yellow-700 text-yellow-300";
    case "INFO": return "bg-blue-900/40 border-blue-700 text-blue-300";
    default: return "bg-gray-800 border-gray-600 text-gray-300";
  }
}

export function truncateLogs(logs: string[], maxLines = 200): string[] {
  return logs.slice(-maxLines);
}
