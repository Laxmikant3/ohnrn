import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { RevisionBucket } from "@/lib/types";
import { CHART, ChartTooltip, LegendDot } from "@/components/charts/theme";

export function RevisionCurveChart({
  data,
  height = 260,
}: {
  data: RevisionBucket[];
  height?: number;
}) {
  const filtered = data.filter((row) => row.n > 0);
  return (
    <div>
      <div className="mb-1 flex flex-wrap items-center gap-4 px-2">
        <LegendDot color={CHART.over} label="Mean revision vs decision (MW)" />
        <LegendDot color={CHART.forecast} label="Mean absolute revision (MW)" />
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={filtered} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="label"
            tickLine={false}
            axisLine={{ stroke: CHART.grid }}
            tickMargin={8}
            interval={0}
            tick={{ fontSize: 10 }}
          />
          <YAxis
            tickFormatter={(value: number) => `${value > 0 ? "+" : ""}${Math.round(value / 100) * 100}`}
            width={48}
            tickLine={false}
            axisLine={false}
            tickMargin={4}
          />
          <Tooltip
            content={<ChartTooltip unit="MW" decimals={0} sign labelText={undefined} />}
            cursor={{ fill: "rgba(148,163,184,0.06)" }}
          />
          <ReferenceLine y={0} stroke="rgba(203,213,225,0.45)" strokeDasharray="3 3" />
          <Bar dataKey="mean_delta_vs_decision_mw" name="Mean revision" isAnimationActive={false} maxBarSize={34}>
            {filtered.map((row, index) => (
              <Cell
                key={`${row.key}-${index}`}
                fill={(row.mean_delta_vs_decision_mw ?? 0) >= 0 ? CHART.over : CHART.under}
                fillOpacity={0.6}
              />
            ))}
          </Bar>
          <Line
            type="monotone"
            dataKey="mean_abs_revision_mw"
            name="Mean |revision|"
            stroke={CHART.forecast}
            strokeWidth={1.7}
            dot={{ r: 2.5, fill: CHART.forecast, strokeWidth: 0 }}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
      <p className="px-2 pt-1 text-[10px] text-slate-600">
        Lead-time buckets group publications by hours before delivery. Only pre-delivery vintages are plotted.
      </p>
    </div>
  );
}
