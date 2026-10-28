"""Dedicated Elexon BMRS client.

Verified contract (OpenAPI 3.0.4, https://data.elexon.co.uk/swagger/v1/swagger.json):

FUELHH stream — GET /datasets/FUELHH/stream
  Query: publishDateTimeFrom, publishDateTimeTo, settlementDateFrom,
         settlementDateTo, settlementPeriod[], fuelType[], format
  Constraint: publish* and settlementDate* filters are mutually exclusive;
              a ``To`` date requires its matching ``From`` date.
  Response: JSON array of {dataset, publishTime, startTime, settlementDate,
            settlementPeriod, fuelType, generation}. generation is int64 MW,
            averaged over 30 minutes.

WINDFOR stream — GET /datasets/WINDFOR/stream
  Query: publishDateTimeFrom, publishDateTimeTo
  Response: JSON array of {dataset, publishTime, startTime, generation}.
            generation is int64 MW; startTime is the forecast delivery time and
            is hourly in the observed feed. Without publish filters the endpoint
            returns only the latest published forecast, so historical vintage
            analysis always sends an explicit publication window.

No authentication is required. There is no pagination; both stream endpoints
return one JSON array and are documented as optimised for frequent requests.
HTTP 429 is documented for rate limiting (no numeric quota published), so the
client enforces a conservative single-flight request cadence and retries with
backoff while honouring Retry-After.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import random
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings

logger = logging.getLogger("windiq.elexon")


class ElexonError(RuntimeError):
    """Base class for upstream failures."""


class ElexonUnavailable(ElexonError):
    """Network/timeout failure after retries."""


class ElexonHTTPError(ElexonError):
    def __init__(self, status_code: int, message: str, body: str | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class ElexonRateLimited(ElexonHTTPError):
    pass


class ElexonValidationError(ElexonError):
    pass


@dataclass
class FetchResult:
    records: list[dict[str, Any]]
    url: str
    params: dict[str, Any]
    attempts: int
    duration_seconds: float
    fingerprint: str


class ElexonClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.settings = settings
        self._lock = asyncio.Lock()
        self._last_request_at = 0.0
        self._transport = transport

    # ------------------------------------------------------------------
    def _timeout(self) -> httpx.Timeout:
        return httpx.Timeout(
            self.settings.elexon_timeout_seconds,
            connect=self.settings.elexon_connect_timeout_seconds,
        )

    async def _throttle(self) -> None:
        async with self._lock:
            elapsed_ms = (time.monotonic() - self._last_request_at) * 1000
            wait_ms = self.settings.elexon_min_interval_ms - elapsed_ms
            if wait_ms > 0:
                await asyncio.sleep(wait_ms / 1000)
            self._last_request_at = time.monotonic()

    async def _get(self, path: str, params: dict[str, Any]) -> FetchResult:
        url = f"{self.settings.elexon_base_url.rstrip('/')}{path}"
        attempts = 0
        started = time.monotonic()
        last_error: Exception | None = None

        for attempt in range(1, self.settings.elexon_max_retries + 1):
            attempts = attempt
            await self._throttle()
            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout(),
                    transport=self._transport,
                    headers={"Accept": "application/json", "User-Agent": "WindIQ/1.0"},
                ) as client:
                    response = await client.get(url, params=params)
                if response.status_code == 200:
                    try:
                        payload = response.json()
                    except ValueError as exc:
                        raise ElexonError("Elexon returned a non-JSON response") from exc
                    if not isinstance(payload, list):
                        raise ElexonError("Elexon stream response was not a JSON array")
                    duration = time.monotonic() - started
                    logger.info(
                        "elexon_fetch_ok",
                        extra={
                            "path": path,
                            "params": params,
                            "records": len(payload),
                            "attempts": attempt,
                            "duration_s": round(duration, 3),
                            "status_code": 200,
                        },
                    )
                    return FetchResult(
                        records=payload,
                        url=url,
                        params=params,
                        attempts=attempt,
                        duration_seconds=round(duration, 3),
                        fingerprint=f"{path}|{sorted(params.items())}",
                    )
                body = response.text[:800]
                if response.status_code == 429:
                    retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                    if retry_after:
                        raise _RateLimitWithDelay(
                            429, "Elexon rate limit reached", body, retry_after
                        )
                    raise ElexonRateLimited(429, "Elexon rate limit reached", body)
                if 400 <= response.status_code < 500:
                    raise ElexonValidationError(
                        f"Elexon rejected the request ({response.status_code}): {body}"
                    )
                last_error = ElexonHTTPError(
                    response.status_code, f"Elexon upstream error {response.status_code}", body
                )
            except (httpx.TimeoutException, httpx.NetworkError, httpx.TransportError) as exc:
                last_error = ElexonUnavailable(f"Elexon request failed: {exc}")
            except _RateLimitWithDelay as exc:
                last_error = exc

            if attempt < self.settings.elexon_max_retries:
                base = self.settings.elexon_backoff_base_seconds * (2 ** (attempt - 1))
                delay = getattr(last_error, "retry_after", None) or base
                delay += random.uniform(0, 0.25)
                logger.warning(
                    "elexon_fetch_retry",
                    extra={
                        "path": path,
                        "attempt": attempt,
                        "delay_s": round(delay, 2),
                        "error": str(last_error),
                    },
                )
                await asyncio.sleep(min(delay, 30))

        logger.error(
            "elexon_fetch_failed",
            extra={"path": path, "params": params, "attempts": attempts, "error": str(last_error)},
        )
        if isinstance(last_error, ElexonError):
            raise last_error
        raise ElexonUnavailable(str(last_error) if last_error else "Elexon request failed")

    # ------------------------------------------------------------------
    async def fetch_actual_wind(
        self, settlement_date_from: dt.date, settlement_date_to: dt.date
    ) -> FetchResult:
        """Fetch FUELHH WIND outturn for an inclusive settlement-date range.

        Settlement dates are used (rather than publication dates) because they
        identify the delivery day unambiguously and keep the requested window
        aligned with the analysis grid.
        """
        return await self._get(
            "/datasets/FUELHH/stream",
            {
                "fuelType": "WIND",
                "settlementDateFrom": settlement_date_from.isoformat(),
                "settlementDateTo": settlement_date_to.isoformat(),
            },
        )

    async def fetch_forecast_wind(
        self, publish_from: dt.datetime, publish_to: dt.datetime
    ) -> FetchResult:
        """Fetch WINDFOR vintages published within an inclusive UTC window."""
        return await self._get(
            "/datasets/WINDFOR/stream",
            {
                "publishDateTimeFrom": publish_from.astimezone(dt.UTC)
                .isoformat()
                .replace("+00:00", "Z"),
                "publishDateTimeTo": publish_to.astimezone(dt.UTC)
                .isoformat()
                .replace("+00:00", "Z"),
            },
        )

    async def probe(self) -> dict[str, Any]:
        """Lightweight connectivity probe using a short, non-retrying request.

        Deliberately bounded to ~8 seconds so health checks stay responsive even
        when Elexon is unreachable.
        """
        now = dt.datetime.now(dt.UTC)
        started = time.monotonic()
        url = f"{self.settings.elexon_base_url.rstrip('/')}/datasets/WINDFOR/stream"
        params = {
            "publishDateTimeFrom": (now - dt.timedelta(hours=3))
            .isoformat()
            .replace("+00:00", "Z"),
            "publishDateTimeTo": (now - dt.timedelta(hours=2))
            .isoformat()
            .replace("+00:00", "Z"),
        }
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(8.0, connect=5.0),
                transport=self._transport,
                headers={"Accept": "application/json", "User-Agent": "WindIQ/1.0"},
            ) as client:
                response = await client.get(url, params=params)
            reachable = response.status_code == 200
            payload = response.json() if reachable else None
            count = len(payload) if isinstance(payload, list) else 0
            if reachable and count == 0:
                detail = (
                    "API reachable — probe window returned 0 WINDFOR records "
                    "(historical analysis does not depend on live publication)"
                )
            elif reachable:
                detail = f"API reachable — {count} WINDFOR records in probe window"
            else:
                detail = f"HTTP {response.status_code}"
            return {
                "checked": True,
                "reachable": reachable,
                "status_code": response.status_code,
                "latency_ms": round((time.monotonic() - started) * 1000),
                "checked_at": now,
                "detail": detail,
            }
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI, never raised
            return {
                "checked": True,
                "reachable": False,
                "status_code": getattr(exc, "status_code", None),
                "latency_ms": round((time.monotonic() - started) * 1000),
                "checked_at": now,
                "detail": str(exc)[:400],
            }


class _RateLimitWithDelay(ElexonRateLimited):
    def __init__(self, status_code: int, message: str, body: str | None, retry_after: float):
        super().__init__(status_code, message, body)
        self.retry_after = retry_after


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
