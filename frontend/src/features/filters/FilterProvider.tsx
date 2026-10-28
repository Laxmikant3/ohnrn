import { useCallback, useMemo, useState, type ReactNode } from "react";
import type { SearchFilters } from "@/lib/api";
import { DEFAULT_FILTERS, FilterContext, type FilterState } from "@/features/filters/filters";

const STORAGE_KEY = "windiq.filters.v1";

function loadInitial(): FilterState {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_FILTERS;
    const parsed = JSON.parse(raw) as Partial<FilterState>;
    return {
      ...DEFAULT_FILTERS,
      ...parsed,
      // Analysis scope is fixed to January 2026 for this pilot.
      startDate: DEFAULT_FILTERS.startDate,
      endDate: DEFAULT_FILTERS.endDate,
    };
  } catch {
    return DEFAULT_FILTERS;
  }
}

export function FilterProvider({ children }: { children: ReactNode }) {
  const [filters, setState] = useState<FilterState>(loadInitial);

  const setFilters = useCallback((patch: Partial<FilterState>) => {
    setState((current) => {
      const next = { ...current, ...patch };
      if (next.endDate < next.startDate) next.endDate = next.startDate;
      try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      } catch {
        // Storage may be unavailable (private mode); filters still work in memory.
      }
      return next;
    });
  }, []);

  const reset = useCallback(() => {
    setState(DEFAULT_FILTERS);
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore
    }
  }, []);

  const value = useMemo(() => {
    const apiFilters: SearchFilters = {
      start_date: filters.startDate,
      end_date: filters.endDate,
      cutoff: filters.cutoff,
      cutoff_days_before: filters.cutoffDaysBefore,
      vintage: filters.vintage,
      lead_time_bucket: filters.leadTimeBucket,
    };
    return { filters, apiFilters, setFilters, reset };
  }, [filters, setFilters, reset]);

  return <FilterContext.Provider value={value}>{children}</FilterContext.Provider>;
}
