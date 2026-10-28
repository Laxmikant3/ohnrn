"""Version 1 REST endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Path, Query, Response

from app.api.deps import (
    CUTOFF_PATTERN,
    FiltersDep,
    ServiceDep,
    SettingsDep,
    StatusLiteral,
)
from app.schemas import (
    DailyAnalyticsOut,
    DataQualityOut,
    ForecastPageOut,
    HealthOut,
    HourlyAnalyticsOut,
    LeadTimeAnalyticsOut,
    MetadataOut,
    OverviewOut,
    RefreshOut,
    RevisionsOut,
    SummaryOut,
    VintagesOut,
)
from app.services.service import NotFoundError
from app.utils.timeutils import parse_api_timestamp

router = APIRouter()


@router.get("/health", response_model=HealthOut, tags=["system"])
async def health(service: ServiceDep, probe: bool = True) -> dict:
    """Liveness/readiness plus cached dataset and upstream connectivity state."""
    return await service.health(probe=probe)


@router.get("/metadata", response_model=MetadataOut, tags=["system"])
def metadata(service: ServiceDep) -> dict:
    """Product metadata, source contract, cutoff assumption and metric definitions."""
    return service.metadata()


@router.get("/overview", response_model=OverviewOut, tags=["analysis"])
def overview(
    service: ServiceDep,
    filters: FiltersDep,
    resolution: Annotated[str, Query(pattern="^(30m|1h|1d)$")] = "1h",
) -> dict:
    """Dashboard KPIs, time series, daily error and forecast revision curve."""
    return service.overview(filters, resolution=resolution)


@router.get("/forecasts", response_model=ForecastPageOut, tags=["forecasts"])
def forecasts(
    service: ServiceDep,
    filters: FiltersDep,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=500)] = 50,
    sort_by: Annotated[
        str,
        Query(
            pattern="^(delivery_interval|delivery_date|settlement_period|forecast_mw|actual_mw|error_mw|absolute_error_mw|publish_time|lead_time_hours|status)$"
        ),
    ] = "delivery_interval",
    sort_dir: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    search: Annotated[str | None, Query(max_length=100)] = None,
    status: StatusLiteral = "all",
) -> dict:
    """Paginated, sortable forecast explorer rows with cutoff eligibility."""
    return service.forecast_page(
        filters, page, page_size, sort_by, sort_dir, search, status
    )


@router.get(
    "/forecasts/{delivery_interval}/vintages",
    response_model=VintagesOut,
    tags=["forecasts"],
)
def vintages(
    service: ServiceDep,
    settings: SettingsDep,
    delivery_interval: Annotated[str, Path(description="UTC ISO-8601 delivery interval start")],
    cutoff: Annotated[str | None, Query(pattern=CUTOFF_PATTERN)] = None,
    cutoff_days_before: Annotated[int | None, Query(ge=0, le=7)] = None,
) -> dict:
    """All forecast vintages for one interval, flagged by eligibility."""
    parsed = parse_api_timestamp(delivery_interval)
    if parsed is None:
        raise NotFoundError("Invalid delivery interval; expected ISO-8601 UTC")
    return service.vintages(
        parsed,
        cutoff or settings.default_cutoff_time,
        cutoff_days_before if cutoff_days_before is not None else settings.default_cutoff_days_before,
    )


@router.get("/analytics/summary", response_model=SummaryOut, tags=["analytics"])
def analytics_summary(service: ServiceDep, filters: FiltersDep) -> dict:
    """Headline error metrics, population counts, distribution and extremes."""
    return service.summary_analytics(filters)


@router.get("/analytics/daily", response_model=DailyAnalyticsOut, tags=["analytics"])
def analytics_daily(service: ServiceDep, filters: FiltersDep) -> dict:
    """Daily MAE, RMSE, bias, MAPE, WAPE and coverage."""
    return service.daily_analytics(filters)


@router.get("/analytics/hourly", response_model=HourlyAnalyticsOut, tags=["analytics"])
def analytics_hourly(service: ServiceDep, filters: FiltersDep) -> dict:
    """Hour-of-day error profile plus a date x hour error heatmap."""
    return service.hourly_analytics(filters)


@router.get("/analytics/lead-time", response_model=LeadTimeAnalyticsOut, tags=["analytics"])
def analytics_lead_time(service: ServiceDep, filters: FiltersDep) -> dict:
    """Accuracy by publication lead-time bucket and the forecast revision curve."""
    return service.lead_time_analytics(filters)


@router.get("/analytics/revisions", response_model=RevisionsOut, tags=["analytics"])
def analytics_revisions(
    service: ServiceDep,
    filters: FiltersDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> dict:
    """Largest pre-delivery forecast revisions versus the decision vintage."""
    return service.revisions_analytics(filters, limit=limit)


@router.get("/data-quality", response_model=DataQualityOut, tags=["system"])
async def data_quality(service: ServiceDep, probe: bool = True) -> dict:
    """Cache, retrieval, duplicate, invalid and missing-interval diagnostics."""
    result = await service.probe() if probe else None
    return service.data_quality(result)


@router.get("/export", tags=["forecasts"])
def export(
    service: ServiceDep,
    filters: FiltersDep,
    search: Annotated[str | None, Query(max_length=100)] = None,
    status: StatusLiteral = "all",
) -> Response:
    """CSV export of the filtered forecast explorer population."""
    filename, content = service.export_csv(filters, search, status)
    row_count = max(0, content.count("\n") - 1)
    return Response(
        content=("\ufeff" + content).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Row-Count": str(row_count),
            "Cache-Control": "no-store",
        },
    )


@router.post("/data/refresh", response_model=RefreshOut, tags=["system"])
async def refresh(
    service: ServiceDep,
    settings: SettingsDep,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> dict:
    """Fetch January 2026 data from Elexon and rewrite the file cache.

    Disabled unless ALLOW_REFRESH=true. When ADMIN_TOKEN is configured the
    request must supply it in X-Admin-Token.
    """
    if not settings.allow_refresh:
        raise HTTPException(
            status_code=403,
            detail=(
                "Dataset refresh is disabled on this deployment. Set ALLOW_REFRESH=true "
                "or run `python -m app.cli load`."
            ),
        )
    if settings.admin_token and x_admin_token != settings.admin_token:
        raise HTTPException(status_code=403, detail="Invalid or missing admin token")
    return await service.refresh()
