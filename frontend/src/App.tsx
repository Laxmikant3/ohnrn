import { useEffect } from "react";
import { Link, Route, Routes, useLocation } from "react-router-dom";
import { Compass } from "lucide-react";
import { AppShell } from "@/components/layout/AppShell";
import { OverviewPage } from "@/pages/OverviewPage";
import { ForecastExplorerPage } from "@/pages/ForecastExplorerPage";
import { AccuracyAnalysisPage } from "@/pages/AccuracyAnalysisPage";
import { ForecastRevisionsPage } from "@/pages/ForecastRevisionsPage";
import { DataQualityPage } from "@/pages/DataQualityPage";
import { MethodologyPage } from "@/pages/MethodologyPage";
import { Panel, StateBlock } from "@/components/ui/primitives";

const TITLES: Record<string, string> = {
  "/": "Overview",
  "/forecasts": "Forecast Explorer",
  "/accuracy": "Accuracy Analysis",
  "/revisions": "Forecast Revisions",
  "/data-quality": "Data Quality",
  "/methodology": "Methodology",
};

function RouteEffects() {
  const location = useLocation();

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [location.pathname]);

  useEffect(() => {
    const label = TITLES[location.pathname] ?? "Workspace";
    document.title = `${label} · WindIQ`;
  }, [location.pathname]);

  return null;
}

function NotFoundPage() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center">
      <Panel className="w-full max-w-md">
        <StateBlock
          icon={<Compass size={18} />}
          title="This workspace view does not exist"
          description="The page you requested is not part of the WindIQ pilot. Use the navigation to return to a supported analysis view."
          action={
            <Link
              to="/"
              className="inline-flex h-[34px] items-center gap-1.5 rounded-md border border-white/[0.12] px-3.5 text-[12.5px] text-slate-300 transition-colors hover:border-accent/40 hover:text-slate-100 focus-ring"
            >
              Back to overview
            </Link>
          }
        />
      </Panel>
    </div>
  );
}

export function App() {
  return (
    <>
      <RouteEffects />
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="forecasts" element={<ForecastExplorerPage />} />
          <Route path="accuracy" element={<AccuracyAnalysisPage />} />
          <Route path="revisions" element={<ForecastRevisionsPage />} />
          <Route path="data-quality" element={<DataQualityPage />} />
          <Route path="methodology" element={<MethodologyPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </>
  );
}
