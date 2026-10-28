import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { LeadTimeBucket } from "@/lib/types";
import { CHART, ChartTooltip } from "@/components/charts/theme";

export function LeadTimeChart({ data, height = 250 }: { data: LeadTimeBucket[]; height?: number }) {
  const filtered = data.filter((row) => row.n > 0);
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={filtered} layout="vertical" margin={{ top: 6, right: 26, bottom: 0, left: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
        <XAxis
          type="number"
          tickFormatter={(value: number) => `${Math.round(value / 1000)}k`}
          tickLine={false}
          axisLine={{ stroke: CHART.grid }}
          tickMargin={6}
        />
        <YAxis
          type="category"
          dataKey="label"
          width={54}
          tickLine={false}
          axisLine={false}
          tick={{ fontSize: 10 }}
        />
        <Tooltip
          content={<ChartTooltip unit="MW" />}
          cursor={{ fill: "rgba(148,163,184,0.06)" }}
        />
        <Bar dataKey="mae" name="MAE" isAnimationActive={false} maxBarSize={18} radius={[0, 3, 3, 0]}>
          {filtered.map((row, index) => (
            <Cell
              key={`${row.key}-${index}`}
              fill={CHART.forecast}
              fillOpacity={0.32 + 0.55 * (1 - index / Math.max(filtered.length, 1))}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
