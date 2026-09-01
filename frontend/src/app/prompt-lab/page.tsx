"use client";

import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import { Plus, Trash2, Play, Loader2, CheckCircle2 } from "lucide-react";
import { promptsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { PromptTemplate } from "@/types";

// Lazy load Monaco editor to avoid SSR issues
const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((m) => m.default),
  { ssr: false, loading: () => <div className="h-full animate-pulse bg-[#0a0a0f] rounded" /> }
);

const DEFAULT_SCHEMA = JSON.stringify(
  {
    type: "object",
    properties: {
      is_anomaly: { type: "boolean" },
      severity: { type: "string", enum: ["INFO", "WARNING", "CRITICAL"] },
      root_cause_analysis: { type: "string" },
      detected_errors: { type: "array", items: { type: "string" } },
      remediation_steps: { type: "array", items: { type: "string" } },
      confidence_score: { type: "number", minimum: 0, maximum: 1 },
    },
    required: ["is_anomaly", "severity", "root_cause_analysis", "confidence_score"],
  },
  null,
  2
);

export default function PromptLabPage() {
  const qc = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [schema, setSchema] = useState(DEFAULT_SCHEMA);
  const [testResult, setTestResult] = useState<{
    thought_process: string;
    structured_output: Record<string, unknown> | null;
    raw_json: string;
  } | null>(null);
  const [testing, setTesting] = useState(false);
  const [isNew, setIsNew] = useState(false);
  const [newName, setNewName] = useState("");

  const { data: templates = [] } = useQuery({
    queryKey: ["prompts"],
    queryFn: promptsApi.list,
  });

  // Auto-select first template when data loads (React Query v5 pattern)
  useEffect(() => {
    const data = templates as PromptTemplate[];
    if (data.length > 0 && !selectedId) {
      const first = data[0];
      setSelectedId(first.id);
      setSystemPrompt(first.system_message);
      setSchema(JSON.stringify(first.json_schema, null, 2));
    }
  }, [templates]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveMutation = useMutation({
    mutationFn: (data: { system_message: string; json_schema: Record<string, unknown> }) =>
      promptsApi.update(selectedId!, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prompts"] }),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      promptsApi.create({
        name: newName,
        system_message: systemPrompt,
        json_schema: JSON.parse(schema),
      }),
    onSuccess: (data: PromptTemplate) => {
      qc.invalidateQueries({ queryKey: ["prompts"] });
      setSelectedId(data.id);
      setIsNew(false);
      setNewName("");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: promptsApi.delete,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["prompts"] });
      setSelectedId(null);
      setSystemPrompt("");
    },
  });

  const handleSelectTemplate = (template: PromptTemplate) => {
    setSelectedId(template.id);
    setSystemPrompt(template.system_message);
    setSchema(JSON.stringify(template.json_schema, null, 2));
    setTestResult(null);
  };

  const handleTest = async () => {
    if (!selectedId) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await promptsApi.test(selectedId);
      setTestResult(result);
    } catch (err) {
      console.error(err);
    } finally {
      setTesting(false);
    }
  };

  const handleSave = () => {
    if (isNew) {
      createMutation.mutate();
    } else if (selectedId) {
      try {
        saveMutation.mutate({
          system_message: systemPrompt,
          json_schema: JSON.parse(schema),
        });
      } catch {
        alert("Invalid JSON schema.");
      }
    }
  };

  return (
    <div className="flex flex-col gap-6 h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between shrink-0">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Prompt Lab</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Edit system prompts and JSON schemas. Test against sample incident data.
          </p>
        </div>
        <button
          onClick={() => { setIsNew(true); setSelectedId(null); setSystemPrompt(""); setSchema(DEFAULT_SCHEMA); }}
          className="flex items-center gap-2 rounded-md border border-[#2a2a3e] bg-[#12121a] px-3 py-1.5 text-sm text-slate-300 hover:bg-white/5"
        >
          <Plus className="h-4 w-4" />
          New Template
        </button>
      </div>

      <div className="flex gap-4 flex-1 min-h-0">
        {/* Template list */}
        <div className="w-52 shrink-0 flex flex-col gap-1 overflow-y-auto">
          {(templates as PromptTemplate[]).map((t) => (
            <button
              key={t.id}
              onClick={() => handleSelectTemplate(t)}
              className={cn(
                "flex flex-col items-start gap-0.5 rounded-md px-3 py-2.5 text-left transition-colors",
                selectedId === t.id
                  ? "bg-blue-600/20 border border-blue-500/30 text-blue-300"
                  : "text-slate-400 hover:bg-white/5 border border-transparent"
              )}
            >
              <span className="text-sm font-medium truncate w-full">{t.name}</span>
              <span className="text-xs text-gray-600">v{t.version}</span>
            </button>
          ))}
        </div>

        {/* Editor area */}
        <div className="flex-1 flex flex-col gap-3 min-w-0">
          {isNew && (
            <div className="flex items-center gap-2">
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Template name..."
                className="rounded-md border border-[#2a2a3e] bg-[#0a0a0f] px-3 py-1.5 text-sm text-slate-300 focus:outline-none focus:border-blue-500"
              />
            </div>
          )}

          {(selectedId || isNew) && (
            <>
              <div className="flex gap-3 flex-1 min-h-0">
                {/* System prompt editor */}
                <div className="flex-1 flex flex-col min-w-0">
                  <label className="text-xs text-gray-500 mb-1.5 uppercase tracking-wider">
                    System Prompt
                  </label>
                  <div className="flex-1 rounded-md border border-[#2a2a3e] overflow-hidden">
                    <MonacoEditor
                      value={systemPrompt}
                      onChange={(v) => setSystemPrompt(v ?? "")}
                      language="markdown"
                      theme="vs-dark"
                      options={{
                        minimap: { enabled: false },
                        wordWrap: "on",
                        fontSize: 13,
                        lineNumbers: "off",
                        scrollBeyondLastLine: false,
                      }}
                    />
                  </div>
                </div>

                {/* JSON schema editor */}
                <div className="w-80 shrink-0 flex flex-col">
                  <label className="text-xs text-gray-500 mb-1.5 uppercase tracking-wider">
                    Response Schema (JSON)
                  </label>
                  <div className="flex-1 rounded-md border border-[#2a2a3e] overflow-hidden">
                    <MonacoEditor
                      value={schema}
                      onChange={(v) => setSchema(v ?? "")}
                      language="json"
                      theme="vs-dark"
                      options={{
                        minimap: { enabled: false },
                        fontSize: 12,
                        scrollBeyondLastLine: false,
                      }}
                    />
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-2 shrink-0">
                <button
                  onClick={handleSave}
                  disabled={saveMutation.isPending || createMutation.isPending}
                  className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
                >
                  {(saveMutation.isPending || createMutation.isPending) ? "Saving..." : "Save"}
                </button>

                {selectedId && (
                  <>
                    <button
                      onClick={handleTest}
                      disabled={testing}
                      className="flex items-center gap-2 rounded-md border border-[#2a2a3e] px-4 py-2 text-sm text-slate-300 hover:bg-white/5 disabled:opacity-50"
                    >
                      {testing
                        ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        : <Play className="h-3.5 w-3.5 text-green-400" />}
                      {testing ? "Testing..." : "Test Prompt"}
                    </button>

                    <button
                      onClick={() => {
                        if (confirm("Delete this template?")) {
                          deleteMutation.mutate(selectedId);
                        }
                      }}
                      className="ml-auto flex items-center gap-1.5 rounded-md px-3 py-2 text-sm text-red-400 hover:bg-red-900/20"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                      Delete
                    </button>
                  </>
                )}
              </div>

              {/* Test results */}
              {testResult && (
                <div className="shrink-0 rounded-lg border border-[#2a2a3e] bg-[#0d0d14] p-4 max-h-80 overflow-y-auto">
                  <h3 className="text-sm font-semibold text-slate-300 mb-3">Test Results</h3>
                  <div className="flex flex-col gap-4">
                    {testResult.thought_process && (
                      <div>
                        <span className="text-xs text-blue-400 uppercase font-semibold">Thinking</span>
                        <pre className="mt-1 text-xs font-mono text-gray-400 whitespace-pre-wrap max-h-32 overflow-y-auto">
                          {testResult.thought_process}
                        </pre>
                      </div>
                    )}
                    {testResult.structured_output && (
                      <div>
                        <span className="text-xs text-green-400 uppercase font-semibold flex items-center gap-1">
                          <CheckCircle2 className="h-3 w-3" /> Structured Output
                        </span>
                        <pre className="mt-1 text-xs font-mono text-slate-300">
                          {JSON.stringify(testResult.structured_output, null, 2)}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </>
          )}

          {!selectedId && !isNew && (
            <div className="flex flex-col items-center justify-center h-full text-gray-600">
              Select a template or create a new one.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
