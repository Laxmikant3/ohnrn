import { CalendarRange, RotateCcw, SlidersHorizontal } from "lucide-react";
import { useFilters, type VintageMode } from "@/features/filters/filters";
import { Button, Input, Segmented, Select } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const LEAD_TIME_OPTIONS = [
  { value: "", label: "All lead times" },
  { value: "lt6", label: "< 6 h" },
  { value: "6to12", label: "6–12 h" },
  { value: "12to18", label: "12–18 h" },
  { value: "18to24", label: "18–24 h" },
  { value: "24to36", label: "24–36 h" },
  { value: "36to48", label: "36–48 h" },
  { value: "gte48", label: "48 h +" },
];

const PRESETS = [
  { label: "Full month", start: "2026-01-01", end: "2026-01-31" },
  { label: "First half", start: "2026-01-01", end: "2026-01-15" },
  { label: "Second half", start: "2026-01-16", end: "2026-01-31" },
];

export function FilterBar({ compact = false }: { compact?: boolean }) {
  const { filters, setFilters, reset } = useFilters();
  const activePreset = PRESETS.find(
    (preset) => preset.start === filters.startDate && preset.end === filters.endDate,
  );

  return (
    <div
      className={cn(
        "mb-4 flex flex-wrap items-end gap-x-3 gap-y-2.5 rounded-xl border border-white/[0.06] bg-ink-850/70 px-3 py-2.5",
        compact && "mb-3",
      )}
    >
      <div className="flex items-center gap-1.5 self-center pr-1 text-slate-500">
        <SlidersHorizontal size={13} />
        <span className="label-caps">Filters</span>
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="filter-start" className="label-caps flex items-center gap-1">
          <CalendarRange size={10} /> From
        </label>
        <Input
          id="filter-start"
          type="date"
          value={filters.startDate}
          min="2026-01-01"
          max="2026-01-31"
          onChange={(event) => setFilters({ startDate: event.target.value })}
          className="w-[138px]"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="filter-end" className="label-caps">
          To
        </label>
        <Input
          id="filter-end"
          type="date"
          value={filters.endDate}
          min="2026-01-01"
          max="2026-01-31"
          onChange={(event) => setFilters({ endDate: event.target.value })}
          className="w-[138px]"
        />
      </div>

      <div className="hidden items-center gap-1 self-end pb-1 sm:flex">
        {PRESETS.map((preset) => (
          <button
            key={preset.label}
            type="button"
            onClick={() => setFilters({ startDate: preset.start, endDate: preset.end, leadTimeBucket: null })}
            className={cn(
              "rounded border px-2 py-1 text-[10.5px] transition-colors focus-ring",
              activePreset?.label === preset.label
                ? "border-accent/30 bg-accent/10 text-accent-soft"
                : "border-white/[0.07] text-slate-500 hover:border-white/[0.15] hover:text-slate-300",
            )}
          >
            {preset.label}
          </button>
        ))}
      </div>

      <div className="flex flex-col gap-1">
        <span className="label-caps">Forecast vintage</span>
        <Segmented<VintageMode>
          ariaLabel="Forecast vintage mode"
          value={filters.vintage}
          onChange={(value) => setFilters({ vintage: value })}
          options={[
            { value: "decision_cutoff", label: "Decision cutoff" },
            { value: "latest_available", label: "Latest available" },
          ]}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="filter-lead" className="label-caps">
          Lead time
        </label>
        <Select
          id="filter-lead"
          value={filters.leadTimeBucket ?? ""}
          onChange={(event) => setFilters({ leadTimeBucket: event.target.value || null })}
          className="w-[132px]"
        >
          {LEAD_TIME_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </Select>
      </div>

      <div className="ml-auto flex items-center gap-2 self-end">
        {filters.vintage === "latest_available" ? (
          <span className="hidden max-w-[210px] text-[10px] leading-3.5 text-warning/80 xl:block">
            Latest-available mode can include post-cutoff information. Use for retrospective only.
          </span>
        ) : null}
        <Button variant="ghost" size="sm" onClick={reset} title="Reset filters">
          <RotateCcw size={11.5} /> Reset
        </Button>
      </div>
    </div>
  );
}
