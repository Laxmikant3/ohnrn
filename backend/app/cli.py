"""WindIQ command-line utilities.

Examples
--------
    python -m app.cli load --start 2026-01-01 --end 2026-01-31
    python -m app.cli status
    python -m app.cli validate
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys

from app.api.deps import StatusLiteral  # noqa: F401  (keeps typing imports honest)
from app.config import get_settings
from app.logging_config import configure_logging
from app.services.cache import CacheStore
from app.services.dataset import DatasetStore
from app.services.ingestion import ingest_window
from app.services.service import QueryFilters, WindIQService


def _parse_date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def _load(args: argparse.Namespace) -> int:
    settings = get_settings()
    cache = CacheStore(settings)
    result = asyncio.run(
        ingest_window(settings, cache, args.start, args.end)
    )
    print(json.dumps(result.to_dict(), indent=2, default=str))
    if not result.complete:
        print(
            "\nWARNING: ingestion was partial. Cached records from successful requests were "
            "preserved; see errors above and the Data Quality page.",
            file=sys.stderr,
        )
        return 2
    if result.actual_records == 0 or result.forecast_records == 0:
        print("\nWARNING: no records were written for at least one source.", file=sys.stderr)
        return 3
    return 0


def _status(_args: argparse.Namespace) -> int:
    settings = get_settings()
    cache = CacheStore(settings)
    store = DatasetStore(settings, cache)
    dataset = store.get(force_reload=True)
    payload = {
        "data_dir": str(settings.data_dir),
        "cache_dir": str(settings.cache_dir),
        "cache_files": cache.file_metadata(),
        "actual_records": int(len(dataset.actual)),
        "forecast_records": int(len(dataset.forecast)),
        "actual_dates": [d.isoformat() for d in dataset.actual_dates] if dataset.actual_dates else None,
        "forecast_dates": [d.isoformat() for d in dataset.forecast_dates] if dataset.forecast_dates else None,
        "forecast_granularity_minutes": dataset.forecast_granularity_minutes,
        "retrieved_at": dataset.retrieved_at.isoformat() if dataset.retrieved_at else None,
        "is_synthetic": dataset.is_synthetic,
        "load_error": dataset.load_error,
        "manifest": dataset.manifest,
    }
    print(json.dumps(payload, indent=2, default=str))
    return 0 if dataset.loaded else 1


def _validate(_args: argparse.Namespace) -> int:
    settings = get_settings()
    service = WindIQService(settings)
    dataset = service.dataset()
    if not dataset.loaded:
        print("Dataset not loaded. Run `python -m app.cli load`.", file=sys.stderr)
        return 1
    filters = QueryFilters(
        start_date=settings.analysis_start,
        end_date=settings.analysis_end,
        cutoff=settings.default_cutoff_time,
        cutoff_days_before=settings.default_cutoff_days_before,
    )
    frame = service.selection(filters)
    summary = service.summary_analytics(filters)
    latest = service.overview(filters)["kpis"]["latest_eligible_forecast"]
    payload = {
        "period": summary["period"],
        "cutoff": summary["cutoff"],
        "population": summary["population"],
        "metrics": summary["metrics"],
        "latest_eligible_forecast": latest,
        "eligibility_counts": {
            "eligible": int((frame["eligibility"] == "eligible").sum()),
            "missing_forecast": int((frame["eligibility"] == "missing_forecast").sum()),
            "retrospective": int((frame["eligibility"] == "retrospective").sum()),
        },
        "cutoff_violations": int(
            (
                frame["publish_time_utc"].notna()
                & (frame["publish_time_utc"] > frame["cutoff_time_utc"])
                & (frame["eligibility"] == "eligible")
            ).sum()
        ),
    }
    print(json.dumps(payload, indent=2, default=str))
    violations = payload["cutoff_violations"]
    if violations:
        print(f"FAILED: {violations} selected forecasts violate the cutoff.", file=sys.stderr)
        return 4
    return 0


def build_parser() -> argparse.ArgumentParser:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="windiq", description="WindIQ data operations")
    sub = parser.add_subparsers(dest="command", required=True)

    load = sub.add_parser("load", help="Fetch and cache Elexon FUELHH/WINDFOR data")
    load.add_argument("--start", type=_parse_date, default=settings.analysis_start)
    load.add_argument("--end", type=_parse_date, default=settings.analysis_end)
    load.set_defaults(func=_load)

    status = sub.add_parser("status", help="Inspect the local dataset cache")
    status.set_defaults(func=_status)

    validate = sub.add_parser(
        "validate", help="Validate cutoff compliance and print January metrics"
    )
    validate.set_defaults(func=_validate)
    return parser


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    configure_logging(settings.log_level)
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
