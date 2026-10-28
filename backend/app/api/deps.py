"""Shared API dependencies."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Literal

from fastapi import Depends, Query, Request

from app.config import Settings
from app.services.service import QueryFilters, WindIQService

CUTOFF_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"
VintageLiteral = Literal["decision_cutoff", "latest_available"]
LeadTimeBucketLiteral = Literal["lt6", "6to12", "12to18", "18to24", "24to36", "36to48", "gte48"]
StatusLiteral = Literal["all", "matched", "missing_actual", "missing_forecast"]


def get_service(request: Request) -> WindIQService:
    return request.app.state.service


def get_app_settings(request: Request) -> Settings:
    return request.app.state.settings


ServiceDep = Annotated[WindIQService, Depends(get_service)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def query_filters(
    settings: SettingsDep,
    start_date: Annotated[dt.date | None, Query()] = None,
    end_date: Annotated[dt.date | None, Query()] = None,
    cutoff: Annotated[
        str | None,
        Query(pattern=CUTOFF_PATTERN, description="Europe/London cutoff clock time, HH:MM"),
    ] = None,
    cutoff_days_before: Annotated[int | None, Query(ge=0, le=7)] = None,
    vintage: Annotated[VintageLiteral, Query(description="decision_cutoff enforces no look-ahead; latest_available is retrospective only")] = "decision_cutoff",
    lead_time_bucket: Annotated[LeadTimeBucketLiteral | None, Query()] = None,
) -> QueryFilters:
    return QueryFilters(
        start_date=start_date or settings.analysis_start,
        end_date=end_date or settings.analysis_end,
        cutoff=cutoff or settings.default_cutoff_time,
        cutoff_days_before=(
            cutoff_days_before
            if cutoff_days_before is not None
            else settings.default_cutoff_days_before
        ),
        vintage=vintage,
        lead_time_bucket=lead_time_bucket,
    )


FiltersDep = Annotated[QueryFilters, Depends(query_filters)]
