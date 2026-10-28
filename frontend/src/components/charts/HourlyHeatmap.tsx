import { useMemo } from "react";
import type { HourlyAnalytics } from "@/lib/types";
import { formatDate, formatShortDay } from "@/lib/format";

function cellColor(value: number | null, max: number): string {
  if (value === null || max <= 0) return "rgba(148,163,184,0.05)";
  const ratio = Math.min(1, Math.max(0, value / max));
  // Deep navy -> teal -> cyan, with amber reserved for the hottest cells.
  if (ratio > 0.86) return `rgba(251,191,36,${0.35 + ratio * 0.55})`;
  if (ratio > 0.6) return `rgba(45,212,191,${0.28 + ratio * 0.6})`;
  return `rgba(34,211,238,${0.12 + ratio * 0.62})`;
}

export function HourlyHeatmap({ data }: { data: HourlyAnalytics["heatmap"] }) {
  const lookup = useMemo(() => {
    const map = new Map<string, { mae: number | null; n: number }>();
    for (const cell of data.cells) {
      map.set(`${cell.date}:${cell.hour}`, { mae: cell.mae, n: cell.n });
    }
    return map;
  }, [data.cells]);

  return (
    <div className="overflow-x-auto px-2 pb-1">
      <div className="min-w-[620px]">
        <div className="mb-1 flex pl-[58px]">
          {Array.from({ length: 24 }).map((_, hour) => (
            <div key={hour} className="flex-1 text-center text-[8.5px] text-slate-600">
              {hour % 3 === 0 ? `${hour}` : ""}
            </div>
          ))}
        </div>
        <div className="space-y-[3px]">
          {data.dates.map((date) => (
            <div key={date} className="flex items-center gap-[3px]">
              <div className="w-[55px] shrink-0 text-[9.5px] text-slate-500" title={formatDate(date)}>
                {formatShortDay(date)}
              </div>
              {Array.from({ length: 24 }).map((_, hour) => {
                const cell = lookup.get(`${date}:${hour}`);
                const value = cell?.mae ?? null;
                return (
                  <div
                    key={hour}
                    className="group relative h-[13px] flex-1 rounded-[2px] ring-inset ring-white/[0.04] transition-transform hover:z-10 hover:scale-[1.35] hover:ring-1 hover:ring-white/40"
                    style={{ backgroundColor: cellColor(value, data.max_mae) }}
                    title={
                      value === null
                        ? `${formatDate(date)} ${String(hour).padStart(2, "0")}:00 — no matched observations`
                        : `${formatDate(date)} ${String(hour).padStart(2, "0")}:00 — MAE ${value.toLocaleString("en-GB")} MW (${cell?.n ?? 0} obs)`
                    }
                  >
                    <span className="sr-only">
                      {formatDate(date)} {hour}:00 MAE {value ?? "unavailable"} MW
                    </span>
                  </div>
                );
              })}
            </div>
          ))}
        </div>
        <div className="mt-2 flex items-center justify-between pl-[58px] text-[9px] text-slate-600">
          <span>Local hour (Europe/London)</span>
          <span className="flex items-center gap-1">
            Lower
            <span className="flex">
              {[0.1, 0.3, 0.5, 0.7, 0.9].map((ratio) => (
                <span
                  key={ratio}
                  className="h-2 w-4"
                  style={{ backgroundColor: cellColor(ratio * data.max_mae, data.max_mae) }}
                />
              ))}
            </span>
            Higher MAE
          </span>
        </div>
      </div>
    </div>
  );
}
