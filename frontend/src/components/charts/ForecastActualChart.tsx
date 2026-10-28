import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SeriesPoint } from "@/lib/types";
import { formatDateTime, formatShortDay, formatTime } from "@/lib/format";
import { CHART, ChartTooltip, LegendDot } from "@/components/charts/theme";

export function ForecastActualChart({
  data,
  height = 300,
  resolution,
}: {
  data: SeriesPoint[];
  height?: number;
  resolution: string;
}) {
  const longRange = data.length > 120;
  const tick = (value: string) => (longRange ? formatShortDay(value) : formatTime(value));

  return (
    <div>
      <div className="mb-1 flex items-center gap-4 px-2">
        <LegendDot color={CHART.forecast} label="Decision-cutoff forecast" />
        <LegendDot color={CHART.actual} label="Actual outturn" />
        <span className="ml-auto hidden text-[10px] text-slate-600 sm:block">
          {resolution === "30m" ? "30-minute" : resolution === "1h" ? "Hourly mean" : "Daily mean"} · Europe/London
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="forecastFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={CHART.forecast} stopOpacity={0.22} />
              <stop offset="100%" stopColor={CHART.forecast} stopOpacity={0.01} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="timestamp"
            tickFormatter={tick}
            minTickGap={44}
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
            domain={["auto", "auto"]}
          />
          <Tooltip
            content={<ChartTooltip unit="MW" formatLabel={(value) => formatDateTime(String(value))} />}
            cursor={{ stroke: "rgba(148,163,184,0.25)", strokeWidth: 1 }}
          />
          <Area
            type="monotone"
            dataKey="forecast_mw"
            name="Forecast"
            stroke={CHART.forecast}
            strokeWidth={1.7}
            fill="url(#forecastFill)"
            dot={false}
            activeDot={{ r: 3, fill: CHART.forecast, stroke: "#0a0f1a", strokeWidth: 2 }}
            connectNulls
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="actual_mw"
            name="Actual"
            stroke={CHART.actual}
            strokeWidth={1.5}
            strokeOpacity={0.9}
            dot={false}
            activeDot={{ r: 3, fill: CHART.actual, stroke: "#0a0f1a", strokeWidth: 2 }}
            connectNulls
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
