import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { AlertTriangle, Clock3, DatabaseZap, Menu, Radio } from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime, relativeAge } from "@/lib/format";
import { Badge } from "@/components/ui/primitives";
import { NAV_ITEMS } from "@/components/layout/nav";
import { cn } from "@/lib/utils";

function StatusSignal({
  label,
  tone,
  detail,
}: {
  label: string;
  tone: "ok" | "warn" | "error" | "idle";
  detail: string;
}) {
  const color =
    tone === "ok" ? "bg-positive" : tone === "warn" ? "bg-warning" : tone === "error" ? "bg-negative" : "bg-slate-600";
  return (
    <div className="flex items-center gap-1.5" title={detail}>
      <span className="relative flex h-1.5 w-1.5">
        {tone === "ok" ? (
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-positive opacity-40" />
        ) : null}
        <span className={cn("relative inline-flex h-1.5 w-1.5 rounded-full", color)} />
      </span>
      <span className="text-[10.5px] font-medium text-slate-400">{label}</span>
    </div>
  );
}

export function TopBar({
  onOpenMobile,
  periodLabel,
  vintageLabel,
}: {
  onOpenMobile: () => void;
  periodLabel: string;
  vintageLabel: string;
}) {
  const location = useLocation();
  const current = NAV_ITEMS.find((item) =>
    item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
  );

  const health = useQuery({
    queryKey: ["health"],
    queryFn: ({ signal }) => api.health(signal),
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: 1,
  });

  const online = health.data?.elexon.reachable;
  const data = health.data?.data;
  const lastRetrieval = data?.last_retrieval ?? null;

  return (
    <header className="sticky top-0 z-30 flex h-[60px] items-center gap-3 border-b border-white/[0.06] bg-ink-950/80 px-4 backdrop-blur-xl sm:px-6">
      <button
        type="button"
        onClick={onOpenMobile}
        className="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-white/[0.05] hover:text-slate-100 lg:hidden"
        aria-label="Open navigation"
      >
        <Menu size={17} />
      </button>

      <div className="hidden min-w-0 items-center gap-2.5 sm:flex">
        <span className="label-caps text-accent/80">UK National Wind</span>
        <span className="h-3 w-px bg-white/10" aria-hidden />
        <span className="text-[11.5px] text-slate-500">{current?.label ?? "Workspace"}</span>
      </div>

      <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
        <Badge tone="violet" className="hidden md:inline-flex">
          Historical analysis
        </Badge>
        <div className="hidden items-center gap-1.5 rounded-md border border-white/[0.07] bg-white/[0.025] px-2 py-1 lg:flex">
          <Clock3 size={11.5} className="text-slate-500" />
          <span className="text-[10.5px] font-medium text-slate-300">{periodLabel}</span>
        </div>
        <div
          className="hidden items-center gap-1.5 rounded-md border border-white/[0.07] bg-white/[0.025] px-2 py-1 xl:flex"
          title={`${vintageLabel}. Default decision cutoff: 11:00 Europe/London on the preceding calendar day (pilot assumption).`}
        >
          <DatabaseZap size={11.5} className="text-slate-500" />
          <span className="text-[10.5px] text-slate-400">Cutoff 11:00 Europe/London · D-1</span>
        </div>

        <span className="hidden h-5 w-px bg-white/[0.08] sm:block" aria-hidden />

        <div className="flex items-center gap-2.5">
          <StatusSignal
            label={health.isLoading ? "API checking" : health.isError ? "API unreachable" : "API online"}
            tone={health.isLoading ? "idle" : health.isError ? "error" : "ok"}
            detail={health.isError ? "Backend health endpoint could not be reached." : "Backend API responded to /api/v1/health."}
          />
          <span className="hidden text-slate-700 sm:block" aria-hidden>
            /
          </span>
          <StatusSignal
            label={
              data?.stale ? "Cache stale" : data?.cached ? "Elexon cached" : data ? "No dataset" : "Data unknown"
            }
            tone={data?.stale ? "warn" : data?.cached ? "ok" : health.isError ? "error" : "idle"}
            detail={
              data
                ? `Source: ${data.source}. Last retrieval ${formatDateTime(lastRetrieval)} (${relativeAge(lastRetrieval)}). ${data.actual_records} actual and ${data.forecast_records} forecast records.`
                : "Dataset status unavailable."
            }
          />
        </div>

        {health.isError ? (
          <AlertTriangle size={14} className="text-negative" aria-label="API unreachable" />
        ) : (
          <Radio size={14} className={online === false ? "text-warning" : "text-slate-600"} aria-hidden />
        )}
      </div>
    </header>
  );
}
