import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { HourRow } from "@/lib/types";
import { CHART, ChartTooltip } from "@/components/charts/theme";

export function HourlyProfileChart({ data, height = 250 }: { data: HourRow[]; height?: number }) {
  const max = Math.max(...data.map((row) => row.mae ?? 0), 1);

  return (
    <div>
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tickFormatter={(value: string) => value.slice(0, 2)}
            interval={2}
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
            content={<ChartTooltip unit="MW" formatLabel={(value) => `${value} Europe/London`} />}
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
          />
          <Bar dataKey="mae" name="MAE" isAnimationActive={false} maxBarSize={22}>
            {data.map((row) => {
              const ratio = (row.mae ?? 0) / max;
              return (
                <Cell
                  key={row.hour}
                  fill={ratio > 0.85 ? CHART.over : CHART.forecast}
                  fillOpacity={0.32 + ratio * 0.6}
                />
              );
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="px-2 pt-1 text-[10px] text-slate-600">
        Mean absolute error by local hour of day. Hover a bar for the number of paired observations.
      </p>
    </div>
  );
}
