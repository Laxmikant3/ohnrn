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
import type { SeriesPoint } from "@/lib/types";
import { formatDateTime, formatShortDay, formatTime } from "@/lib/format";
import { CHART, ChartTooltip, LegendDot } from "@/components/charts/theme";

export function ForecastErrorChart({
  data,
  height = 220,
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
        <LegendDot color={CHART.over} label="Overforecast" />
        <LegendDot color={CHART.under} label="Underforecast" />
        <span className="ml-auto hidden text-[10px] text-slate-600 sm:block">
          Error = forecast − actual · {resolution === "30m" ? "30-minute" : resolution === "1h" ? "hourly mean" : "daily mean"}
        </span>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
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
            tickFormatter={(value: number) => `${value > 0 ? "+" : ""}${Math.round(value / 1000)}k`}
            width={46}
            tickLine={false}
            axisLine={false}
            tickMargin={4}
          />
          <Tooltip
            content={<ChartTooltip unit="MW" formatLabel={(value) => formatDateTime(String(value))} />}
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
          />
          <ReferenceLine y={0} stroke="rgba(203,213,225,0.45)" strokeDasharray="3 3" />
          <Bar dataKey="error_mw" name="Forecast error" isAnimationActive={false} maxBarSize={18}>
            {data.map((point, index) => (
              <Cell
                key={`${point.timestamp}-${index}`}
                fill={(point.error_mw ?? 0) >= 0 ? CHART.over : CHART.under}
                fillOpacity={0.72}
              />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
