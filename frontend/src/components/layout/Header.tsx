"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Activity, History, Settings, FlaskConical, SlidersHorizontal, Wifi, WifiOff } from "lucide-react";
import { statusApi } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { href: "/", label: "Dashboard", icon: Activity },
  { href: "/history", label: "History", icon: History },
  { href: "/targets", label: "Targets", icon: Settings },
  { href: "/prompt-lab", label: "Prompt Lab", icon: FlaskConical },
  { href: "/settings", label: "Settings", icon: SlidersHorizontal },
];

export function Header() {
  const pathname = usePathname();

  const { data: status, isError } = useQuery({
    queryKey: ["status"],
    queryFn: statusApi.get,
    refetchInterval: 30_000,
  });

  const isHealthy = !isError && status?.api === "ok" && status?.redis === "ok";

  return (
    <header className="sticky top-0 z-50 border-b border-[#2a2a3e] bg-[#0a0a0f]/90 backdrop-blur-sm">
      <div className="container mx-auto max-w-screen-2xl px-4">
        <div className="flex h-14 items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-blue-600/20 border border-blue-500/30">
              <Activity className="h-4 w-4 text-blue-400" />
            </div>
            <span className="font-semibold text-slate-100 tracking-tight">
              AIOps <span className="text-blue-400">Sentinel</span>
            </span>
          </div>

          {/* Navigation */}
          <nav className="flex items-center gap-1">
            {NAV_LINKS.map(({ href, label, icon: Icon }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "flex items-center gap-2 px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                  pathname === href
                    ? "bg-blue-600/20 text-blue-300 border border-blue-500/30"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </Link>
            ))}
          </nav>

          {/* System Health */}
          <div className="flex items-center gap-2">
            {isHealthy ? (
              <span className="flex items-center gap-1.5 text-xs text-green-400">
                <Wifi className="h-3.5 w-3.5" />
                System OK
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-xs text-red-400">
                <WifiOff className="h-3.5 w-3.5" />
                Degraded
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
