import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { DailyRow } from "@/lib/types";
import { formatDate } from "@/lib/format";
import { CHART, ChartTooltip, LegendDot } from "@/components/charts/theme";

export function DailyMaeChart({ data, height = 240 }: { data: DailyRow[]; height?: number }) {
  const tick = (value: string) => {
    const date = new Date(`${value}T12:00:00Z`);
    return new Intl.DateTimeFormat("en-GB", { day: "numeric", timeZone: "UTC" }).format(date);
  };

  return (
    <div>
      <div className="mb-1 flex items-center gap-4 px-2">
        <LegendDot color={CHART.forecast} label="Daily MAE" />
        <LegendDot color={CHART.actual} label="Daily RMSE" />
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={tick}
            minTickGap={18}
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
            tickMargin={8}
          />
          <YAxis
            tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
            width={42}
            tickLine={false}
            axisLine={false}
            tickMargin={4}
          />
          <Tooltip
            content={<ChartTooltip unit="MW" formatLabel={(value) => formatDate(String(value))} />}
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
          />
          <Bar dataKey="mae" name="MAE" fill={CHART.forecast} fillOpacity={0.55} maxBarSize={16} isAnimationActive={false} />
          <Line
            type="monotone"
            dataKey="rmse"
            name="RMSE"
            stroke={CHART.actual}
            strokeWidth={1.6}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
