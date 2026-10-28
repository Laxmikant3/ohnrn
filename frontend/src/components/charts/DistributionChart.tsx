import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DistributionBin } from "@/lib/types";
import { CHART, ChartTooltip, LegendDot } from "@/components/charts/theme";

export function DistributionChart({ data, height = 240 }: { data: DistributionBin[]; height?: number }) {
  const tick = (value: string) => {
    const bin = data.find((entry) => entry.label === String(value));
    if (!bin) return "";
    const numeric = bin.bin_start;
    return Number.isFinite(numeric) ? `${numeric > 0 ? "+" : ""}${Math.round(numeric / 1000)}k` : "";
  };

  return (
    <div>
      <div className="mb-1 flex items-center gap-4 px-2">
        <LegendDot color={CHART.under} label="Underforecast" />
        <LegendDot color={CHART.over} label="Overforecast" />
        <span className="ml-auto hidden text-[10px] text-slate-600 sm:block">Bins of forecast error (MW)</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tickFormatter={tick}
            minTickGap={22}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
            tickMargin={8}
          />
          <YAxis width={34} tickLine={false} axisLine={false} tickMargin={4} allowDecimals={false} />
          <Tooltip
            content={<ChartTooltip unit="intervals" formatLabel={(value) => `${value} MW`} />}
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
          />
          <ReferenceLine x={data.find((bin) => bin.bin_start <= 0 && bin.bin_end >= 0)?.label} stroke="rgba(203,213,225,0.3)" strokeDasharray="3 3" />
          <Bar dataKey="count" name="Intervals" isAnimationActive={false} maxBarSize={26}>
            {data.map((bin, index) => (
              <Cell
                key={`${bin.label}-${index}`}
                fill={bin.direction === "over" ? CHART.over : bin.direction === "under" ? CHART.under : CHART.neutral}
                fillOpacity={0.68}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
