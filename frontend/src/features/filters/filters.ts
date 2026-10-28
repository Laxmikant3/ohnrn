import { createContext, useContext } from "react";
import type { SearchFilters } from "@/lib/api";

export type VintageMode = "decision_cutoff" | "latest_available";

export type FilterState = {
  startDate: string;
  endDate: string;
  cutoff: string;
  cutoffDaysBefore: number;
  vintage: VintageMode;
  leadTimeBucket: string | null;
};

export const DEFAULT_FILTERS: FilterState = {
  startDate: "2026-01-01",
  endDate: "2026-01-31",
  cutoff: "11:00",
  cutoffDaysBefore: 1,
  vintage: "decision_cutoff",
  leadTimeBucket: null,
};

export type FilterContextValue = {
  filters: FilterState;
  apiFilters: SearchFilters;
  setFilters: (patch: Partial<FilterState>) => void;
  reset: () => void;
};

export const FilterContext = createContext<FilterContextValue | null>(null);

export function useFilters(): FilterContextValue {
  const context = useContext(FilterContext);
  if (!context) throw new Error("useFilters must be used inside FilterProvider");
  return context;
}
