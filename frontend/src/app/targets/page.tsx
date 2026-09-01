"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Pencil, RefreshCw, Database, CheckCircle2 } from "lucide-react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { targetsApi } from "@/lib/api";
import { cn } from "@/lib/utils";
import type { Target } from "@/types";

const targetSchema = z.object({
  label_name: z.string().min(1),
  display_name: z.string().min(1),
  environment: z.enum(["dev", "test", "prod"]),
  priority: z.number().min(1).max(10),
  auto_notify: z.boolean(),
  prom_label: z.string().min(1),
  loki_label: z.string().optional(),
  db_type: z.string().optional(),
});

type TargetForm = z.infer<typeof targetSchema>;

function TargetDialog({
  target,
  onClose,
}: {
  target?: Target;
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<TargetForm>({
    resolver: zodResolver(targetSchema),
    defaultValues: target
      ? { ...target, priority: target.priority }
      : { priority: 5, environment: "prod", auto_notify: true },
  });

  const createMutation = useMutation({
    mutationFn: targetsApi.create,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["targets"] }); onClose(); },
  });

  const updateMutation = useMutation({
    mutationFn: (data: TargetForm) => targetsApi.update(target!.id, data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["targets"] }); onClose(); },
  });

  const onSubmit = (data: TargetForm) => {
    if (target) {
      updateMutation.mutate(data);
    } else {
      createMutation.mutate(data as Parameters<typeof targetsApi.create>[0]);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="w-full max-w-lg rounded-lg border border-[#2a2a3e] bg-[#12121a] p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-slate-100">
          {target ? "Edit Target" : "Add Target"}
        </h2>

        <form onSubmit={handleSubmit(onSubmit)} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">Label Name (Prometheus instance)</span>
              <input
                {...register("label_name")}
                className="input-field"
                placeholder="db-prod-01"
              />
              {errors.label_name && <span className="text-xs text-red-400">Required</span>}
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">Display Name</span>
              <input
                {...register("display_name")}
                className="input-field"
                placeholder="Oracle DB Prod"
              />
            </label>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">Environment</span>
              <select {...register("environment")} className="input-field">
                <option value="prod">prod</option>
                <option value="test">test</option>
                <option value="dev">dev</option>
              </select>
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">Priority (1-10)</span>
              <input
                {...register("priority", { valueAsNumber: true })}
                type="number"
                min={1}
                max={10}
                className="input-field"
              />
            </label>
            <label className="flex flex-col gap-1">
              <span className="text-xs text-gray-400">DB Type</span>
              <select {...register("db_type")} className="input-field">
                <option value="">—</option>
                <option value="oracle">Oracle</option>
                <option value="postgres">PostgreSQL</option>
                <option value="mysql">MySQL</option>
                <option value="linux">Linux Host</option>
              </select>
            </label>
          </div>

          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Prometheus Label Selector</span>
            <input
              {...register("prom_label")}
              className="input-field font-mono text-xs"
              placeholder='instance="db-prod-01:9100"'
            />
            {errors.prom_label && <span className="text-xs text-red-400">Required</span>}
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs text-gray-400">Loki Label (optional)</span>
            <input
              {...register("loki_label")}
              className="input-field font-mono text-xs"
              placeholder='app="oracle", host="db-prod-01"'
            />
          </label>

          <label className="flex items-center gap-2">
            <input {...register("auto_notify")} type="checkbox" className="h-4 w-4" />
            <span className="text-sm text-slate-300">Auto-notify on anomaly</span>
          </label>

          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md px-4 py-2 text-sm text-slate-400 hover:text-slate-200 hover:bg-white/5"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500 disabled:opacity-50"
            >
              {target ? "Save Changes" : "Create Target"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function TargetsPage() {
  const qc = useQueryClient();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Target | undefined>();
  const [learningId, setLearningId] = useState<string | null>(null);

  const { data: targets = [] } = useQuery({
    queryKey: ["targets"],
    queryFn: targetsApi.list,
  });

  const deleteMutation = useMutation({
    mutationFn: targetsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["targets"] }),
  });

  const handleLearn = async (id: string) => {
    setLearningId(id);
    try {
      await targetsApi.triggerLearning(id);
    } finally {
      setTimeout(() => setLearningId(null), 3000);
    }
  };

  return (
    <>
      {(dialogOpen || editTarget) && (
        <TargetDialog
          target={editTarget}
          onClose={() => { setDialogOpen(false); setEditTarget(undefined); }}
        />
      )}

      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-100">Target Configuration</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              Map Prometheus instance labels to display names and environments
            </p>
          </div>
          <button
            onClick={() => { setEditTarget(undefined); setDialogOpen(true); }}
            className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
          >
            <Plus className="h-4 w-4" />
            Add Target
          </button>
        </div>

        <div className="rounded-lg border border-[#2a2a3e] bg-[#12121a] overflow-hidden">
          {(targets as Target[]).length === 0 ? (
            <div className="flex flex-col items-center py-16 gap-2 text-gray-500">
              <Database className="h-8 w-8" />
              <span>No targets configured yet.</span>
              <span className="text-xs">Add your first target to start monitoring.</span>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#2a2a3e] text-xs text-gray-500 uppercase tracking-wider">
                  <th className="px-4 py-3 text-left">Target</th>
                  <th className="px-4 py-3 text-left">Environment</th>
                  <th className="px-4 py-3 text-left">Priority</th>
                  <th className="px-4 py-3 text-left">DB Type</th>
                  <th className="px-4 py-3 text-left">Prom Label</th>
                  <th className="px-4 py-3 text-left">Auto Notify</th>
                  <th className="px-4 py-3 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(targets as Target[]).map((target) => (
                  <tr
                    key={target.id}
                    className="border-b border-[#1a1a26] hover:bg-white/5"
                  >
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-200">{target.display_name}</div>
                      <div className="text-xs text-gray-500 font-mono">{target.label_name}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={cn(
                        "rounded px-2 py-0.5 text-xs font-bold uppercase",
                        target.environment === "prod"
                          ? "bg-orange-900/40 text-orange-300"
                          : target.environment === "dev"
                          ? "bg-blue-900/30 text-blue-300"
                          : "bg-yellow-900/30 text-yellow-300"
                      )}>
                        {target.environment}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-400">{target.priority}</td>
                    <td className="px-4 py-3 text-sm text-slate-400">{target.db_type ?? "—"}</td>
                    <td className="px-4 py-3 text-xs font-mono text-gray-500 max-w-48 truncate">
                      {target.prom_label}
                    </td>
                    <td className="px-4 py-3">
                      {target.auto_notify
                        ? <CheckCircle2 className="h-4 w-4 text-green-400" />
                        : <span className="text-gray-600">—</span>}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleLearn(target.id)}
                          title="Trigger learning phase"
                          className="rounded p-1 text-blue-400 hover:bg-blue-900/30"
                        >
                          <RefreshCw className={cn("h-3.5 w-3.5", learningId === target.id && "animate-spin")} />
                        </button>
                        <button
                          onClick={() => setEditTarget(target)}
                          className="rounded p-1 text-gray-400 hover:bg-white/5"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                        <button
                          onClick={() => {
                            if (confirm(`Delete "${target.display_name}"?`)) {
                              deleteMutation.mutate(target.id);
                            }
                          }}
                          className="rounded p-1 text-red-400 hover:bg-red-900/20"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <style jsx global>{`
        .input-field {
          width: 100%;
          border-radius: 0.375rem;
          border: 1px solid #2a2a3e;
          background: #0a0a0f;
          padding: 0.375rem 0.75rem;
          font-size: 0.875rem;
          color: #e2e8f0;
          outline: none;
        }
        .input-field:focus {
          border-color: #3b82f6;
        }
        select.input-field option {
          background: #12121a;
        }
      `}</style>
    </>
  );
}
