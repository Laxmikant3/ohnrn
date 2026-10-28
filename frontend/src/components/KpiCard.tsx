import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "accent" | "neutral" | "positive" | "warning" | "negative";

const accentBar: Record<Tone, string> = {
  accent: "from-accent/70 via-accent/30 to-transparent",
  neutral: "from-slate-500/50 via-slate-500/20 to-transparent",
  positive: "from-positive/70 via-positive/25 to-transparent",
  warning: "from-warning/70 via-warning/25 to-transparent",
  negative: "from-negative/70 via-negative/25 to-transparent",
};

const valueTone: Record<Tone, string> = {
  accent: "text-slate-50",
  neutral: "text-slate-100",
  positive: "text-positive",
  warning: "text-warning",
  negative: "text-negative",
};

export function KpiCard({
  label,
  value,
  unit,
  hint,
  footer,
  tone = "neutral",
  icon,
  className,
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  hint?: ReactNode;
  footer?: ReactNode;
  tone?: Tone;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "group relative overflow-hidden rounded-xl border border-white/[0.07] bg-ink-850/90 px-3.5 pb-3 pt-3 shadow-panel transition-colors hover:border-white/[0.11]",
        className,
      )}
    >
      <div className={cn("absolute inset-x-0 top-0 h-px bg-gradient-to-r", accentBar[tone])} aria-hidden />
      <div className="flex items-start justify-between gap-2">
        <p className="label-caps">{label}</p>
        {icon ? <span className={cn("text-slate-600 transition-colors group-hover:text-slate-400", tone === "accent" && "text-accent/60")}>{icon}</span> : null}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1.5">
        <span className={cn("num text-[25px] font-semibold leading-none tracking-[-0.03em]", valueTone[tone])}>
          {value}
        </span>
        {unit ? <span className="text-[11px] font-medium text-slate-500">{unit}</span> : null}
      </div>
      {hint ? <div className="mt-1.5 truncate text-[10.5px] text-slate-500">{hint}</div> : null}
      {footer ? <div className="mt-2.5 border-t border-white/[0.05] pt-2 text-[10.5px] text-slate-400">{footer}</div> : null}
    </div>
  );
}
