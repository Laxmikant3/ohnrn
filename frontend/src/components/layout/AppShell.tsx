import { Component, useEffect, useState, type ErrorInfo, type ReactNode } from "react";
import { Outlet } from "react-router-dom";
import { AlertOctagon } from "lucide-react";
import { Sidebar } from "@/components/layout/Sidebar";
import { TopBar } from "@/components/layout/TopBar";
import { useFilters } from "@/features/filters/filters";
import { Button, Panel, StateBlock } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const COLLAPSE_KEY = "windiq.sidebar.collapsed";

function periodLabel(startDate: string, endDate: string): string {
  const start = new Date(`${startDate}T12:00:00Z`);
  const end = new Date(`${endDate}T12:00:00Z`);
  const startDay = new Intl.DateTimeFormat("en-GB", { day: "numeric", timeZone: "UTC" }).format(start);
  const endDay = new Intl.DateTimeFormat("en-GB", { day: "numeric", timeZone: "UTC" }).format(end);
  const monthYear = new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" }).format(end);
  return `${startDay}–${endDay} ${monthYear}`;
}

class AppErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("WindIQ render error", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center p-6">
          <Panel className="max-w-lg">
            <StateBlock
              tone="negative"
              icon={<AlertOctagon size={18} />}
              title="The workspace could not be rendered"
              description={this.state.error.message}
              action={
                <Button variant="outline" onClick={() => window.location.reload()}>
                  Reload application
                </Button>
              }
            />
          </Panel>
        </div>
      );
    }
    return this.props.children;
  }
}

export function AppShell() {
  const { filters } = useFilters();
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(COLLAPSE_KEY) === "true";
    } catch {
      return false;
    }
  });
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, String(collapsed));
    } catch {
      // ignore
    }
  }, [collapsed]);

  useEffect(() => {
    setMobileOpen(false);
  }, [filters.startDate, filters.endDate]);

  return (
    <AppErrorBoundary>
      <div className="min-h-screen">
        <Sidebar
          collapsed={collapsed}
          onToggle={() => setCollapsed((value) => !value)}
          mobileOpen={mobileOpen}
          onCloseMobile={() => setMobileOpen(false)}
        />
        <div className={cn("min-h-screen transition-[padding] duration-200 ease-out", collapsed ? "lg:pl-[76px]" : "lg:pl-[244px]")}>
          <TopBar
            onOpenMobile={() => setMobileOpen(true)}
            periodLabel={periodLabel(filters.startDate, filters.endDate)}
            vintageLabel={
              filters.vintage === "decision_cutoff"
                ? "Decision-cutoff mode (no look-ahead)"
                : "Latest-available mode (retrospective)"
            }
          />
          <main className="mx-auto w-full max-w-[1680px] px-4 pb-16 pt-5 sm:px-6 lg:px-7">
            <Outlet />
          </main>
          <footer className="mx-auto flex w-full max-w-[1680px] flex-wrap items-center justify-between gap-2 border-t border-white/[0.05] px-4 py-4 text-[10.5px] text-slate-600 sm:px-6 lg:px-7">
            <span>WindIQ · Elexon BMRS FUELHH + WINDFOR · Historical January 2026 analysis</span>
            <span>Not a trading recommendation. Forecast error is not an accuracy percentage.</span>
          </footer>
        </div>
      </div>
    </AppErrorBoundary>
  );
}
