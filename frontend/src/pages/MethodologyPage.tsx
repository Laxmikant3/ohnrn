import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  CalendarClock,
  Database,
  ExternalLink,
  Filter,
  GitBranch,
  Info,
  Layers,
  Ruler,
  Sigma,
  Terminal,
  Timer,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDateTime, formatDecimal } from "@/lib/format";
import { PageHeader, QueryState, KeyValue } from "@/components/common";
import { Badge, Panel } from "@/components/ui/primitives";

const SECTIONS = [
  { id: "scope", label: "Scope and intent" },
  { id: "sources", label: "Data sources" },
  { id: "pipeline", label: "Pipeline" },
  { id: "time", label: "Time and DST" },
  { id: "cutoff", label: "Decision cutoff" },
  { id: "selection", label: "Selection rules" },
  { id: "metrics", label: "Metric definitions" },
  { id: "quality", label: "Data quality" },
  { id: "limitations", label: "Limitations" },
  { id: "reproduce", label: "Reproduce" },
];

function Section({
  id,
  icon,
  title,
  description,
  children,
}: {
  id: string;
  icon: ReactNode;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-20 rounded-xl border border-white/[0.06] bg-ink-850/80 p-4 shadow-panel">
      <div className="mb-3 flex items-start gap-2.5">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-white/[0.07] bg-white/[0.03] text-accent/80">
          {icon}
        </span>
        <div>
          <h2 className="text-[14px] font-semibold tracking-[-0.01em] text-slate-50">{title}</h2>
          {description ? <p className="mt-0.5 text-[11.5px] leading-5 text-slate-500">{description}</p> : null}
        </div>
      </div>
      <div className="space-y-3 text-[12px] leading-6 text-slate-400">{children}</div>
    </section>
  );
}

function Code({ children }: { children: ReactNode }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-white/[0.07] bg-ink-950/70 px-3 py-2.5 text-[10.5px] leading-5 text-slate-300">
      <code className="num whitespace-pre">{children}</code>
    </pre>
  );
}

export function MethodologyPage() {
  const metadataQuery = useQuery({
    queryKey: ["metadata"],
    queryFn: ({ signal }) => api.metadata(signal),
    staleTime: 10 * 60_000,
  });

  const metadata = metadataQuery.data;

  return (
    <div>
      <PageHeader
        eyebrow="Transparent by construction"
        title="Methodology"
        description="Exactly what WindIQ measures, which Elexon fields it uses, how the decision cutoff is enforced, how metrics are calculated and where the analysis stops. This page is the audit reference for every figure in the application."
        meta={
          metadata ? (
            <>
              <Badge tone="violet">Historical analysis</Badge>
              <Badge tone="accent" dot>
                Cutoff {metadata.cutoff.time} {metadata.cutoff.timezone} · D−{metadata.cutoff.days_before}
              </Badge>
              <Badge tone="neutral">{metadata.analysis_period.label}</Badge>
              <Badge tone={metadata.cutoff.assumption ? "warning" : "positive"}>
                {metadata.cutoff.assumption ? "Pilot assumption" : "Contractual deadline"}
              </Badge>
            </>
          ) : null
        }
      />

      {metadataQuery.isError ? (
        <Panel>
          <QueryState isLoading={false} error={metadataQuery.error} onRetry={() => metadataQuery.refetch()}>
            <span />
          </QueryState>
        </Panel>
      ) : metadataQuery.isLoading ? (
        <Panel>
          <QueryState isLoading error={null}>
            <span />
          </QueryState>
        </Panel>
      ) : metadata ? (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[210px_minmax(0,1fr)]">
          <aside className="hidden xl:block">
            <nav aria-label="Methodology contents" className="sticky top-[84px] space-y-0.5">
              <p className="label-caps px-2 pb-1.5">On this page</p>
              {SECTIONS.map((section) => (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-[11.5px] text-slate-500 transition-colors hover:bg-white/[0.04] hover:text-slate-200 focus-ring"
                >
                  <span className="h-1 w-1 rounded-full bg-slate-700" aria-hidden />
                  {section.label}
                </a>
              ))}
              <div className="mt-3 rounded-lg border border-white/[0.06] bg-white/[0.02] p-2.5">
                <p className="label-caps">Version</p>
                <p className="num mt-1 text-[11px] text-slate-300">{metadata.product.version}</p>
                <p className="mt-1 text-[10px] leading-4 text-slate-500">{metadata.product.mode.replaceAll("_", " ")}</p>
              </div>
            </nav>
          </aside>

          <div className="space-y-3">
            <div className="rounded-xl border border-accent/20 bg-accent/[0.05] p-4">
              <div className="flex items-start gap-2.5">
                <CalendarClock size={16} className="mt-0.5 shrink-0 text-accent" />
                <div>
                  <p className="text-[12.5px] font-semibold text-slate-100">The cutoff is the core integrity control</p>
                  <p className="mt-1 text-[11.5px] leading-5 text-slate-400">{metadata.cutoff.description}</p>
                  <p className="mt-1.5 text-[10.5px] leading-4 text-warning/80">
                    This is a labelled pilot assumption, not a statement of the client's actual trading deadline. It is
                    configurable per request and must be confirmed before production use.
                  </p>
                </div>
              </div>
            </div>

            <Section
              id="scope"
              icon={<BookOpen size={14} />}
              title="Scope and intent"
              description="What this product does — and deliberately does not do"
            >
              <p>
                WindIQ evaluates how Elexon's published national wind generation forecast performed against Elexon's
                half-hourly wind outturn for January 2026, using only information that would have been available at a
                day-ahead procurement cutoff.
              </p>
              <ul className="space-y-1.5">
                {[
                  "Inputs are limited to Elexon BMRS FUELHH (WIND) actuals and WINDFOR forecasts. No solar, prices, demand, interconnector, weather or other fuel data is used.",
                  "Forecast vintages are never backfilled with later publications. If no eligible publication exists for an interval, the interval is reported as missing.",
                  "The output is descriptive forecast-error intelligence. It is not a trading recommendation and does not size hedge or trade volumes.",
                ].map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-accent/60" aria-hidden />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Section>

            <Section
              id="sources"
              icon={<Database size={14} />}
              title="Data sources and field mapping"
              description="Verified against the live Elexon BMRS OpenAPI description"
            >
              <div className="space-y-2.5">
                {metadata.sources.map((source) => (
                  <div key={source.dataset} className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div>
                        <p className="text-[12px] font-semibold text-slate-100">
                          {source.dataset} · {source.name}
                        </p>
                        <p className="mt-0.5 text-[10.5px] text-slate-500">
                          {source.granularity_minutes}-minute granularity · {source.unit} · {source.authentication}
                        </p>
                      </div>
                      <a
                        href={source.documentation_url}
                        target="_blank"
                        rel="noreferrer noopener"
                        className="inline-flex items-center gap-1 rounded border border-white/[0.09] px-2 py-1 text-[10px] text-slate-400 transition-colors hover:border-accent/40 hover:text-accent focus-ring"
                      >
                        Elexon docs <ExternalLink size={10} />
                      </a>
                    </div>
                    <p className="num mt-2 break-all text-[10px] text-slate-500">{source.endpoint}</p>
                    <div className="mt-2 grid grid-cols-1 gap-x-4 sm:grid-cols-2">
                      <div>
                        <p className="label-caps mb-1">Request parameters</p>
                        <ul className="space-y-0.5 text-[10.5px] text-slate-400">
                          {source.parameters.map((parameter) => (
                            <li key={parameter} className="num">
                              {parameter}
                            </li>
                          ))}
                        </ul>
                      </div>
                      <div>
                        <p className="label-caps mb-1">Fields used</p>
                        <dl className="space-y-0.5">
                          {Object.entries(source.fields_used).map(([field, meaning]) => (
                            <div key={field} className="flex gap-2 text-[10.5px]">
                              <dt className="num shrink-0 text-accent/80">{field}</dt>
                              <dd className="text-slate-500">{meaning}</dd>
                            </div>
                          ))}
                        </dl>
                      </div>
                    </div>
                    <p className="mt-2 text-[10px] leading-4 text-slate-600">
                      Pagination: {source.pagination}. Rate limit: {source.rate_limit}.
                    </p>
                  </div>
                ))}
              </div>
              <p className="text-[10.5px] leading-4 text-slate-500">
                FUELHH is queried by settlement date; WINDFOR is queried by publication window because the endpoint does
                not expose delivery-date filtering. The API treats settlement-date and publish-time filters as mutually
                exclusive, so each dataset is fetched separately.
              </p>
            </Section>

            <Section
              id="pipeline"
              icon={<GitBranch size={14} />}
              title="Processing pipeline"
              description="From Elexon response to analysable settlement grid"
            >
              <ol className="space-y-2">
                {[
                  {
                    title: "Retrieve",
                    text: "HTTPX fetches FUELHH for each settlement date and WINDFOR in two-day publication windows covering the analysis window. Transient failures are retried with backoff; no data is replaced or invented.",
                  },
                  {
                    title: "Normalise",
                    text: "Timestamps are parsed as UTC, values are validated as finite non-negative MW, duplicate keys are resolved deterministically and post-delivery publications are excluded and counted separately.",
                  },
                  {
                    title: "Expand",
                    text: "Each hourly WINDFOR value is applied to both 30-minute settlement periods it covers. The raw hourly start is retained alongside the expanded delivery interval.",
                  },
                  {
                    title: "Persist",
                    text: "Normalised records plus a SHA-256 manifest and retrieval audit events are written atomically to the JSON cache. Analytics read the cache, never the network, at request time.",
                  },
                  {
                    title: "Select",
                    text: "For every 30-minute delivery interval in the London date range, choose the latest forecast publication at or before the cutoff, then join the latest actual outturn.",
                  },
                  {
                    title: "Measure",
                    text: "Compute MAE, RMSE, bias, MAPE, WAPE, coverage, distributions, daily/hourly/lead-time breakdowns and revision curves from paired observations only.",
                  },
                ].map((step, index) => (
                  <li key={step.title} className="flex gap-3 rounded-lg border border-white/[0.05] bg-white/[0.015] px-3 py-2.5">
                    <span className="num mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-accent/20 bg-accent/10 text-[10px] font-semibold text-accent">
                      {index + 1}
                    </span>
                    <div>
                      <p className="text-[11.5px] font-medium text-slate-200">{step.title}</p>
                      <p className="mt-0.5 text-[11px] leading-5 text-slate-500">{step.text}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Section>

            <Section
              id="time"
              icon={<Timer size={14} />}
              title="Time zones and daylight saving"
              description="Market time is Europe/London; all stored timestamps are UTC"
            >
              <p>
                Delivery dates, settlement periods and hourly profiles use the Europe/London market calendar. Internally
                every timestamp is timezone-aware UTC. The expected interval grid is generated with a DST-aware local-day
                walk, so a spring-forward day yields 46 half-hours and an autumn-back day yields 50 rather than a flat 48.
              </p>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                  <p className="label-caps text-accent/70">Cutoff instant</p>
                  <p className="mt-1 text-[11px] leading-5 text-slate-400">
                    Local wall-clock cutoff on the preceding calendar day is localised to Europe/London, then converted
                    to UTC. The comparison against <span className="num text-slate-300">publishTime</span> is inclusive
                    of the cutoff instant itself.
                  </p>
                </div>
                <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                  <p className="label-caps text-accent/70">Grid length</p>
                  <p className="mt-1 text-[11px] leading-5 text-slate-400">
                    Expected intervals are counted from the local-day grid, not assumed to be 48 per day. Coverage
                    denominators therefore stay correct across DST boundaries.
                  </p>
                </div>
              </div>
              <p className="text-[10.5px] leading-4 text-slate-500">
                January 2026 has no DST transition, so the default view contains 31 × 48 = 1,488 expected settlement
                periods. The DST logic is exercised by the backend test suite.
              </p>
            </Section>

            <Section
              id="cutoff"
              icon={<Filter size={14} />}
              title="Decision cutoff and no-look-ahead rule"
              description="Latest eligible publication wins; later publications are excluded, never backfilled"
            >
              <Code>
{`cutoff_utc = localise(
    (delivery_date - cutoff_days_before) at cutoff_time,
    Europe/London
)

eligible = forecasts where publish_time_utc <= cutoff_utc
selected = eligible, max(publish_time_utc) per delivery interval
actual   = latest FUELHH record for that interval`}
              </Code>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <dl className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                  <KeyValue label="Cutoff time" value={`${metadata.cutoff.time} ${metadata.cutoff.timezone}`} />
                  <KeyValue label="Days before delivery" value={metadata.cutoff.days_before} />
                  <KeyValue label="Inclusive boundary" value="publish_time ≤ cutoff" />
                </dl>
                <dl className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2">
                  <KeyValue label="Vintage modes" value="Decision cutoff / latest available" />
                  <KeyValue label="Analysis period" value={metadata.analysis_period.label} />
                  <KeyValue label="Available range" value={`${metadata.analysis_period.available_start ?? "—"} → ${metadata.analysis_period.available_end ?? "—"}`} />
                </dl>
              </div>
              <p>
                The <span className="text-slate-200">Latest available</span> vintage mode exists solely for retrospective
                comparison. It can include post-cutoff information and is flagged in the interface. Every headline KPI
                uses decision-cutoff mode by default.
              </p>
            </Section>

            <Section
              id="selection"
              icon={<Layers size={14} />}
              title="Selection, duplicates and population accounting"
              description="How ties, repeated publications and missing legs are handled"
            >
              <ul className="space-y-2">
                {[
                  "Forecast key: (delivery interval, publication time). Exact-key duplicates with identical values are collapsed. Conflicting exact-key duplicates are averaged and counted as duplicate conflicts.",
                  "Actual key: delivery interval. If Elexon returns more than one publication for the same interval, the latest publication wins.",
                  "Post-delivery publications — anything published at or after the delivery interval start — are excluded and reported separately as excluded_post_delivery_records. They are not counted as invalid.",
                  "The population always retains expected intervals. An interval with no eligible forecast is labelled missing_forecast; an interval with no actual is labelled missing_actual. Neither is dropped from coverage.",
                  "The lead-time filter is applied after selection and its removals are reported as excluded_by_lead_time, so metric counts never change silently.",
                ].map((item) => (
                  <li key={item} className="flex gap-2">
                    <ArrowRight size={12} className="mt-1.5 shrink-0 text-accent/50" aria-hidden />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Section>

            <Section
              id="metrics"
              icon={<Sigma size={14} />}
              title="Metric definitions"
              description="Every metric reports its observation count; none is presented as an accuracy score"
            >
              <div className="overflow-x-auto rounded-lg border border-white/[0.06]">
                <table className="table-shell">
                  <thead>
                    <tr>
                      <th>Metric</th>
                      <th>Unit</th>
                      <th>Formula</th>
                      <th>Interpretation</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metadata.metrics.definitions.map((definition) => (
                      <tr key={definition.key} className="align-top">
                        <td className="whitespace-nowrap font-medium text-slate-200">{definition.label}</td>
                        <td className="num text-slate-500">{definition.unit}</td>
                        <td className="num whitespace-normal text-[10.5px] leading-4 text-accent/80">{definition.formula}</td>
                        <td className="whitespace-normal text-[10.5px] leading-4 text-slate-500">{definition.description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                <div className="rounded-lg border border-warning/15 bg-warning/[0.04] px-3 py-2.5">
                  <p className="label-caps text-warning/80">MAPE denominator policy</p>
                  <p className="mt-1 text-[11px] leading-5 text-slate-400">
                    MAPE is only computed where the absolute actual generation is at least{" "}
                    <span className="num text-slate-200">{formatDecimal(metadata.metrics.mape_min_actual_mw, 1)} MW</span>.
                    Intervals below the threshold are excluded from MAPE and the excluded count is reported. MAPE is
                    unstable near zero generation, which is why WAPE is reported alongside it.
                  </p>
                </div>
                <div className="rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2.5">
                  <p className="label-caps text-accent/70">Coverage policy</p>
                  <p className="mt-1 text-[11px] leading-5 text-slate-400">{metadata.metrics.coverage_definition}</p>
                </div>
              </div>
              <p className="text-[11px] text-slate-500">
                Error is defined as <span className="num text-slate-300">forecast_mw − actual_mw</span>. Positive bias
                therefore means the forecast ran above outturn (overforecast), negative means below (underforecast).
              </p>
            </Section>

            <Section
              id="quality"
              icon={<Ruler size={14} />}
              title="Data quality controls"
              description="What the Data Quality page proves"
            >
              <ul className="space-y-1.5">
                {[
                  "Cache files are content-hashed with SHA-256 in a manifest, together with the retrieval timestamp, endpoint, parameters, record count, attempts and duration.",
                  "Record accounting exposes raw, valid, invalid, duplicate, conflicting, naive-timestamp and post-delivery-excluded counts for both datasets.",
                  "Coverage is recomputed per London delivery day so a partially ingested day is visible rather than averaged away.",
                  "Post-delivery exclusion is counted separately from invalid records, so normal filtering is never conflated with data corruption.",
                ].map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-accent/60" aria-hidden />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Section>

            <Section
              id="limitations"
              icon={<AlertTriangle size={14} />}
              title="Limitations and non-goals"
              description="Read these before drawing procurement conclusions"
            >
              <ul className="space-y-2">
                {metadata.limitations.map((limitation) => (
                  <li key={limitation} className="flex gap-2 rounded-lg border border-white/[0.05] bg-white/[0.015] px-2.5 py-2">
                    <Info size={12} className="mt-1 shrink-0 text-warning/70" aria-hidden />
                    <span className="text-[11px] leading-5 text-slate-400">{limitation}</span>
                  </li>
                ))}
              </ul>
              <div className="rounded-lg border border-negative/20 bg-negative/[0.04] px-3 py-2.5">
                <p className="text-[11px] font-medium text-negative/90">Not a trading system</p>
                <p className="mt-1 text-[10.5px] leading-5 text-slate-400">
                  WindIQ contains no price, demand, interconnector or balancing data. It cannot determine an optimal
                  traded volume, hedge ratio or bid strategy, and must not be used as though it could.
                </p>
              </div>
            </Section>

            <Section
              id="reproduce"
              icon={<Terminal size={14} />}
              title="Reproduction"
              description="Local commands that regenerate the cache and re-run the verification suite"
            >
              <Code>
{`# Backend
cd backend
python -m venv .venv
.venv/Scripts/activate        # Windows
pip install -r requirements.txt
python -m app.cli load --start 2026-01-01 --end 2026-01-31
pytest -q
uvicorn app.main:app --host 127.0.0.1 --port 8000

# Frontend
cd frontend
npm install
npm run dev                    # http://localhost:5173`}
              </Code>
              <div className="flex flex-wrap items-center gap-2 text-[10.5px] text-slate-500">
                <Badge tone="neutral">Python 3.12+</Badge>
                <Badge tone="neutral">Node 20+</Badge>
                <Badge tone="neutral">API prefix /api/v1</Badge>
                <Badge tone="neutral">OpenAPI at /docs</Badge>
                <span>Dataset retrieval is explicit; the API never silently refreshes in the background.</span>
              </div>
              <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {metadata.sources.map((source) => (
                  <a
                    key={source.dataset}
                    href={source.documentation_url}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="flex items-center justify-between gap-2 rounded-lg border border-white/[0.07] bg-white/[0.02] px-3 py-2 text-[11px] text-slate-300 transition-colors hover:border-accent/35 hover:text-accent focus-ring"
                  >
                    <span>{source.dataset} API documentation</span>
                    <ExternalLink size={12} />
                  </a>
                ))}
              </div>
              <p className="text-[10px] leading-4 text-slate-600">
                Product version {metadata.product.version} · analysis timezone {metadata.product.timezone} · metadata
                generated by the running backend at request time.
              </p>
            </Section>

            <p className="pb-4 text-center text-[10px] text-slate-600">
              Last metadata response rendered {formatDateTime(new Date())}. All figures in this application are derived
              from the cached Elexon response files described above.
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
