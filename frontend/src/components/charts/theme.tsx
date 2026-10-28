import type { ReactNode } from "react";

export const CHART = {
  forecast: "#22d3ee",
  forecastSoft: "rgba(34,211,238,0.16)",
  actual: "#b9c6d8",
  actualSoft: "rgba(185,198,216,0.10)",
  over: "#f59e0b",
  overSoft: "rgba(245,158,11,0.65)",
  under: "#2dd4bf",
  underSoft: "rgba(45,212,191,0.65)",
  neutral: "#64748b",
  positive: "#34d399",
  negative: "#f87171",
  grid: "rgba(148,163,184,0.09)",
  axis: "#64748b",
} as const;

export type TooltipEntry = {
  name?: string | number;
  value?: number | string | null;
  color?: string;
  dataKey?: string | number;
  payload?: Record<string, unknown>;
};

export type TooltipProps = {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string | number;
  labelText?: string;
  formatLabel?: (label: string | number) => string;
  unit?: string;
  decimals?: number;
  sign?: boolean;
  footer?: (entry: TooltipEntry) => ReactNode;
};

const numberFormat = (value: number, decimals: number) =>
  value.toLocaleString("en-GB", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

export function ChartTooltip({
  active,
  payload,
  label,
  labelText,
  formatLabel,
  unit,
  decimals = 0,
  sign = false,
  footer,
}: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  return (
    <div className="min-w-[168px] rounded-lg border border-white/[0.1] bg-ink-800/95 px-3 py-2 text-[11px] shadow-xl backdrop-blur">
      <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wider text-slate-500">
        {labelText ?? (formatLabel && label !== undefined ? formatLabel(label) : label)}
      </p>
      <div className="space-y-1">
        {payload.map((entry, index) => {
          const numeric = typeof entry.value === "number" ? entry.value : Number(entry.value);
          const hasValue = Number.isFinite(numeric);
          return (
            <div key={`${entry.dataKey ?? entry.name ?? index}`} className="flex items-baseline justify-between gap-4">
              <span className="flex items-center gap-1.5 text-slate-400">
                <span className="h-1.5 w-1.5 rounded-sm" style={{ backgroundColor: entry.color ?? CHART.neutral }} />
                {entry.name}
              </span>
              <span className="num font-medium text-slate-100">
                {hasValue ? `${sign && numeric > 0 ? "+" : ""}${numberFormat(numeric, decimals)}` : "—"}
                {hasValue && unit ? <span className="ml-0.5 text-[10px] font-normal text-slate-500">{unit}</span> : null}
              </span>
              {footer ? footer(entry) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[10.5px] text-slate-400">
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
