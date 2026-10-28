import {
  Activity,
  BookOpen,
  Database,
  GitCompareArrows,
  LayoutDashboard,
  Table2,
} from "lucide-react";

export const NAV_ITEMS = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true, hint: "Market KPIs and error trends" },
  { to: "/forecasts", label: "Forecast Explorer", icon: Table2, hint: "Interval-level audit trail" },
  { to: "/accuracy", label: "Accuracy Analysis", icon: Activity, hint: "Error metrics and diagnostics" },
  { to: "/revisions", label: "Forecast Revisions", icon: GitCompareArrows, hint: "Vintage movement to delivery" },
  { to: "/data-quality", label: "Data Quality", icon: Database, hint: "Cache, coverage and retrieval" },
  { to: "/methodology", label: "Methodology", icon: BookOpen, hint: "Sources, cutoff and formulas" },
];
