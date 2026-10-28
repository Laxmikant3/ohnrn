import type { ReactNode } from "react";
import { AlertTriangle, Inbox, RefreshCw } from "lucide-react";
import { ApiError } from "@/lib/api";
import { Button, Panel, Skeleton, StateBlock } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: string;
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <div className="mb-5 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        {eyebrow ? <p className="label-caps mb-1 text-accent/70">{eyebrow}</p> : null}
        <h1 className="text-[21px] font-semibold tracking-[-0.025em] text-slate-50">{title}</h1>
        {description ? <p className="mt-1 max-w-3xl text-[12px] leading-5 text-slate-500">{description}</p> : null}
        {meta ? <div className="mt-2.5 flex flex-wrap items-center gap-2">{meta}</div> : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function ChartPanel({
  title,
  subtitle,
  right,
  children,
  className,
  bodyClassName,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}) {
  return (
    <Panel className={cn("flex flex-col", className)}>
      <div className="flex flex-wrap items-start justify-between gap-2 border-b border-white/[0.06] px-4 py-3">
        <div className="min-w-0">
          <h2 className="panel-title">{title}</h2>
          {subtitle ? <p className="panel-subtitle">{subtitle}</p> : null}
        </div>
        {right ? <div className="flex items-center gap-2">{right}</div> : null}
      </div>
      <div className={cn("min-h-0 flex-1 px-2 pb-3 pt-3", bodyClassName)}>{children}</div>
    </Panel>
  );
}

export function ChartSkeleton({ height = 260 }: { height?: number }) {
  return (
    <div className="space-y-3 px-2 py-2">
      <div className="flex items-end gap-1.5" style={{ height }}>
        {Array.from({ length: 24 }).map((_, index) => (
          <Skeleton
            key={index}
            className="flex-1"
            // deterministic pseudo-random shape for a calm skeleton
          />
        ))}
      </div>
      <Skeleton className="h-3 w-40" />
    </div>
  );
}

export function QueryState({
  isLoading,
  error,
  isEmpty,
  onRetry,
  loadingLabel = "Loading data",
  emptyTitle = "No observations in this selection",
  emptyDescription,
  children,
}: {
  isLoading: boolean;
  error: unknown;
  isEmpty?: boolean;
  onRetry?: () => void;
  loadingLabel?: string;
  emptyTitle?: string;
  emptyDescription?: ReactNode;
  children: ReactNode;
}) {
  if (isLoading) {
    return (
      <div className="flex min-h-[240px] flex-col justify-center gap-3 px-4 py-6" aria-busy="true" aria-label={loadingLabel}>
        <Skeleton className="h-4 w-48" />
        <Skeleton className="h-[180px] w-full" />
        <div className="flex gap-3">
          <Skeleton className="h-3 w-28" />
          <Skeleton className="h-3 w-20" />
        </div>
      </div>
    );
  }
  if (error) {
    const message =
      error instanceof ApiError
        ? error.message
        : error instanceof Error
          ? error.message
          : "The request to the WindIQ API failed.";
    return (
      <StateBlock
        tone="negative"
        icon={<AlertTriangle size={17} />}
        title="Unable to load this analysis"
        description={message}
        action={
          onRetry ? (
            <Button variant="outline" size="sm" onClick={onRetry}>
              <RefreshCw size={12} /> Retry request
            </Button>
          ) : null
        }
      />
    );
  }
  if (isEmpty) {
    return (
      <StateBlock
        icon={<Inbox size={17} />}
        title={emptyTitle}
        description={emptyDescription ?? "Adjust the date range, forecast vintage or lead-time filter."}
      />
    );
  }
  return <>{children}</>;
}

export function KeyValue({
  label,
  value,
  mono = true,
  tone,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
  tone?: "default" | "positive" | "warning" | "negative";
}) {
  const toneClass =
    tone === "positive"
      ? "text-positive"
      : tone === "warning"
        ? "text-warning"
        : tone === "negative"
          ? "text-negative"
          : "text-slate-200";
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-white/[0.04] py-1.5 last:border-0">
      <dt className="text-[11px] text-slate-500">{label}</dt>
      <dd className={cn("text-[11.5px] font-medium", mono && "num", toneClass)}>{value}</dd>
    </div>
  );
}
