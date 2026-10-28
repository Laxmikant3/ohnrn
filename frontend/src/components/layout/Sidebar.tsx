import { NavLink } from "react-router-dom";
import { ChevronLeft, Wind, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { NAV_ITEMS } from "@/components/layout/nav";

export function BrandMark({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-accent/25 bg-gradient-to-br from-accent/15 to-accent-teal/5 text-accent shadow-[0_0_20px_-8px_rgba(34,211,238,0.55)]",
        className,
      )}
    >
      <Wind size={17} strokeWidth={2.1} aria-hidden />
    </div>
  );
}

export function Sidebar({
  collapsed,
  onToggle,
  mobileOpen,
  onCloseMobile,
}: {
  collapsed: boolean;
  onToggle: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}) {
  return (
    <>
      <div
        className={cn(
          "fixed inset-0 z-40 bg-ink-950/70 backdrop-blur-sm transition-opacity lg:hidden",
          mobileOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        onClick={onCloseMobile}
        aria-hidden={!mobileOpen}
      />
      <aside
        aria-label="Primary navigation"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex flex-col border-r border-white/[0.06] bg-ink-900/95 backdrop-blur-xl transition-[width,transform] duration-200 ease-out",
          collapsed ? "lg:w-[76px]" : "lg:w-[244px]",
          "w-[244px]",
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className={cn("flex h-[60px] items-center border-b border-white/[0.06] px-4", collapsed && "lg:justify-center lg:px-0")}>
          <div className="flex min-w-0 items-center gap-2.5">
            <BrandMark />
            <div className={cn("min-w-0", collapsed && "lg:hidden")}>
              <div className="flex items-baseline gap-1.5">
                <span className="text-[15px] font-semibold tracking-[-0.02em] text-slate-50">WindIQ</span>
                <span className="rounded bg-accent/10 px-1 py-px text-[8.5px] font-bold uppercase tracking-wider text-accent">
                  Pilot
                </span>
              </div>
              <p className="truncate text-[10px] text-slate-500">Renewable Forecast Intelligence</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onCloseMobile}
            className="ml-auto flex h-8 w-8 items-center justify-center rounded-md text-slate-500 hover:bg-white/5 hover:text-slate-200 lg:hidden"
            aria-label="Close navigation"
          >
            <X size={16} />
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
          <p className={cn("px-2 pb-1.5 pt-1 label-caps", collapsed && "lg:hidden")}>Workspace</p>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                onClick={onCloseMobile}
                title={collapsed ? `${item.label} — ${item.hint}` : item.hint}
                className={({ isActive }) =>
                  cn(
                    "group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[12.5px] font-medium transition-colors focus-ring",
                    collapsed && "lg:justify-center lg:px-0",
                    isActive
                      ? "bg-white/[0.055] text-slate-50"
                      : "text-slate-400 hover:bg-white/[0.035] hover:text-slate-200",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span
                      className={cn(
                        "absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-r bg-accent transition-opacity",
                        isActive ? "opacity-100" : "opacity-0",
                      )}
                      aria-hidden
                    />
                    <Icon
                      size={15.5}
                      strokeWidth={1.9}
                      className={cn("shrink-0 transition-colors", isActive ? "text-accent" : "text-slate-500 group-hover:text-slate-300")}
                      aria-hidden
                    />
                    <span className={cn("truncate", collapsed && "lg:hidden")}>{item.label}</span>
                  </>
                )}
              </NavLink>
            );
          })}
        </nav>

        <div className={cn("border-t border-white/[0.06] px-3 py-3", collapsed && "lg:px-2")}>
          <div className={cn("rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5", collapsed && "lg:hidden")}>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Analysis mode</p>
            <p className="mt-1 text-[11px] leading-4 text-slate-300">Historical January 2026</p>
            <p className="mt-1 text-[10px] leading-4 text-slate-500">
              Retrospective evaluation — not a live forecast feed.
            </p>
          </div>
          <button
            type="button"
            onClick={onToggle}
            className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md border border-white/[0.06] py-1.5 text-[10.5px] text-slate-500 transition-colors hover:border-white/[0.12] hover:text-slate-300 focus-ring"
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <ChevronLeft size={13} className={cn("transition-transform", collapsed && "rotate-180")} />
            <span className={cn(collapsed && "lg:hidden")}>Collapse</span>
          </button>
        </div>
      </aside>
    </>
  );
}
