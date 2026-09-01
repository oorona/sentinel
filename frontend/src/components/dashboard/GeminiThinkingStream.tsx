"use client";

import { useEffect, useRef } from "react";
import { Brain, CheckCircle2 } from "lucide-react";
import { cn, severityBg } from "@/lib/utils";
import type { GeminiAnalysis } from "@/types";

interface GeminiThinkingStreamProps {
  thoughts: string[];
  finalAnalysis?: GeminiAnalysis;
  status?: string;
}

export function GeminiThinkingStream({
  thoughts,
  finalAnalysis,
  status,
}: GeminiThinkingStreamProps) {
  const thoughtsRef = useRef<HTMLDivElement>(null);
  const isStreaming = status === "analyzing" && !finalAnalysis;
  const thoughtText = thoughts.join("");

  useEffect(() => {
    if (thoughtsRef.current) {
      thoughtsRef.current.scrollTop = thoughtsRef.current.scrollHeight;
    }
  }, [thoughts]);

  if (thoughts.length === 0 && !finalAnalysis) return null;

  return (
    <div className="flex flex-col gap-3 rounded-md border border-blue-500/20 bg-blue-950/10 p-3">
      {/* Header */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-1.5">
          <Brain className={cn("h-4 w-4", isStreaming ? "text-blue-400 animate-pulse" : "text-blue-500")} />
          <span className="text-sm font-semibold text-blue-300">
            Gemini Intelligence
          </span>
        </div>
        {isStreaming && (
          <span className="text-xs text-blue-400/70 animate-pulse">Thinking...</span>
        )}
        {finalAnalysis && (
          <CheckCircle2 className="h-3.5 w-3.5 text-green-400 ml-auto" />
        )}
      </div>

      {/* Thinking stream */}
      {thoughtText && (
        <div className="flex flex-col gap-1">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Thought Process</span>
          <div
            ref={thoughtsRef}
            className="terminal-scroll overflow-y-auto rounded bg-black/40 p-2 font-mono text-xs text-gray-300 leading-relaxed border border-[#2a2a3e]"
            style={{ maxHeight: "140px" }}
          >
            <span className={cn(isStreaming && "cursor-blink")}>{thoughtText}</span>
          </div>
        </div>
      )}

      {/* Final verdict */}
      {finalAnalysis && (
        <div className="flex flex-col gap-2 mt-1">
          <span className="text-xs text-gray-500 uppercase tracking-wider">Diagnosis</span>

          {/* Severity badge */}
          <div
            className={cn(
              "inline-flex items-center gap-1.5 rounded px-2 py-1 text-xs font-semibold border self-start",
              severityBg(finalAnalysis.severity)
            )}
          >
            {finalAnalysis.severity}
            <span className="font-normal opacity-70">
              · {Math.round(finalAnalysis.confidence_score * 100)}% confidence
            </span>
          </div>

          {/* Root cause */}
          <p className="text-sm text-slate-200 leading-relaxed">
            {finalAnalysis.root_cause_analysis}
          </p>

          {/* Detected errors */}
          {finalAnalysis.detected_errors && finalAnalysis.detected_errors.length > 0 && (
            <div>
              <span className="text-xs text-red-400 font-semibold">Detected Errors:</span>
              <ul className="mt-1 space-y-0.5">
                {finalAnalysis.detected_errors.map((err, i) => (
                  <li key={i} className="text-xs font-mono text-red-300 bg-red-950/20 px-2 py-0.5 rounded">
                    {err}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Remediation steps */}
          {finalAnalysis.remediation_steps && finalAnalysis.remediation_steps.length > 0 && (
            <div>
              <span className="text-xs text-green-400 font-semibold">Remediation Steps:</span>
              <ol className="mt-1 space-y-1 list-decimal list-inside">
                {finalAnalysis.remediation_steps.map((step, i) => (
                  <li key={i} className="text-xs text-slate-300">
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
