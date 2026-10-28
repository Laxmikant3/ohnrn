"""API integration tests using synthetic cache fixtures."""

from __future__ import annotations

import datetime as dt

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import build_settings

API = "/api/v1"


def test_health_without_probe(api_client):
    response = api_client.get(f"{API}/health?probe=false")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_loaded"] is True
    assert payload["data"]["mode"] == "historical_analysis"
    assert payload["data"]["is_synthetic"] is True


def test_health_degrades_without_dataset(tmp_path):
    settings = build_settings(tmp_path, dt.date(2026, 1, 10), dt.date(2026, 1, 12))
    app = create_app(settings)
    with TestClient(app) as client:
        response = client.get(f"{API}/health?probe=false")
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert response.json()["dataset_loaded"] is False

        overview = client.get(f"{API}/overview")
        assert overview.status_code == 503
        assert overview.json()["error"]["code"] == "DATA_UNAVAILABLE"


def test_metadata(api_client):
    payload = api_client.get(f"{API}/metadata").json()
    assert payload["product"]["name"].startswith("WindIQ")
    assert payload["cutoff"]["assumption"] is True
    assert {source["dataset"] for source in payload["sources"]} == {"FUELHH", "WINDFOR"}
    assert payload["metrics"]["mape_min_actual_mw"] == 1.0
    assert len(payload["metrics"]["definitions"]) == 6


def test_overview_matches_summary_metrics(api_client):
    overview = api_client.get(f"{API}/overview?resolution=30m").json()
    summary = api_client.get(f"{API}/analytics/summary").json()
    assert overview["kpis"]["mae"]["value"] == summary["metrics"]["mae"]["value"]
    assert overview["kpis"]["rmse"]["value"] == summary["metrics"]["rmse"]["value"]
    assert overview["kpis"]["coverage"]["value"] == 100.0
    assert overview["period"]["expected_intervals"] == 144
    assert overview["cutoff"]["time"] == "11:00"
    assert len(overview["series"]) == 144
    assert overview["series"][0]["forecast_mw"] is not None
    assert overview["mode"] == "historical_analysis"


def test_forecasts_never_include_post_cutoff_selection(api_client):
    response = api_client.get(f"{API}/forecasts?page_size=500")
    assert response.status_code == 200
    payload = response.json()
    assert payload["pagination"]["total_items"] == 144
    assert payload["population"]["matched_intervals"] == 144
    for item in payload["items"]:
        assert item["eligibility"] == "eligible"
        assert item["is_cutoff_compliant"] is True
        assert item["publish_time"] <= item["cutoff_time"]


def test_latest_available_mode_is_explicitly_retrospective(api_client):
    payload = api_client.get(
        f"{API}/forecasts?page_size=10&vintage=latest_available"
    ).json()
    assert payload["filters"]["vintage"] == "latest_available"
    assert any(item["eligibility"] == "retrospective" for item in payload["items"])


def test_vintages_distinguish_eligible_and_post_cutoff(api_client):
    listing = api_client.get(f"{API}/forecasts?page_size=1").json()
    interval = listing["items"][0]["delivery_interval"]
    response = api_client.get(f"{API}/forecasts/{interval}/vintages")
    assert response.status_code == 200
    payload = response.json()
    assert payload["vintages"]
    assert payload["decision_forecast"]["eligible"] is True
    assert sum(1 for item in payload["vintages"] if item["eligible"]) == 1
    assert sum(1 for item in payload["vintages"] if not item["eligible"]) == 3
    assert sum(1 for item in payload["vintages"] if item["selected"]) == 1
    selected = [item for item in payload["vintages"] if item["selected"]][0]
    assert selected["publish_time"] == payload["decision_forecast"]["publish_time"]
    assert selected["lead_time_hours"] == 14.5
    assert payload["actual_mw"] is not None


def test_unknown_interval_returns_404(api_client):
    response = api_client.get(f"{API}/forecasts/2026-02-10T00:00:00Z/vintages")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_invalid_interval_returns_404(api_client):
    response = api_client.get(f"{API}/forecasts/not-a-date/vintages")
    assert response.status_code == 404


def test_out_of_range_period_returns_422(api_client):
    response = api_client.get(
        f"{API}/overview?start_date=2026-02-01&end_date=2026-02-02"
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "OUT_OF_RANGE"
    assert body["error"]["details"]["available_start"] == "2026-01-10"


def test_reversed_dates_return_422(api_client):
    response = api_client.get(
        f"{API}/analytics/summary?start_date=2026-01-12&end_date=2026-01-10"
    )
    assert response.status_code == 422


def test_invalid_cutoff_returns_validation_error(api_client):
    response = api_client.get(f"{API}/forecasts?cutoff=25:99")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_analytics_endpoints(api_client):
    summary = api_client.get(f"{API}/analytics/summary").json()
    assert summary["metrics"]["mae"]["n"] == 144
    assert summary["metrics"]["wape"]["unit"] == "%"
    assert summary["population"]["mape_excluded"] == 0

    daily = api_client.get(f"{API}/analytics/daily").json()
    assert len(daily["days"]) == 3

    hourly = api_client.get(f"{API}/analytics/hourly").json()
    assert len(hourly["hours"]) == 24
    assert len(hourly["heatmap"]["cells"]) == 3 * 24

    lead = api_client.get(f"{API}/analytics/lead-time").json()
    assert len(lead["buckets"]) == 7
    assert any(bucket["n"] > 0 for bucket in lead["buckets"])

    revisions = api_client.get(f"{API}/analytics/revisions").json()
    assert revisions["summary"]["intervals_with_vintages"] == 144
    assert revisions["top"]


def test_analytics_lead_time_filter_changes_population(api_client):
    payload = api_client.get(f"{API}/analytics/summary?lead_time_bucket=12to18").json()
    assert payload["population"]["matched_intervals"] > 0
    assert (
        payload["population"]["matched_intervals"]
        + payload["population"]["excluded_by_lead_time"]
        == 144
    )
    other = api_client.get(f"{API}/analytics/summary?lead_time_bucket=6to12").json()
    assert other["population"]["matched_intervals"] == 0
    assert other["population"]["excluded_by_lead_time"] == 144


def test_forecast_search_and_status_filter(api_client):
    payload = api_client.get(f"{API}/forecasts?search=00:30&page_size=100").json()
    assert payload["pagination"]["total_items"] == 6
    missing = api_client.get(f"{API}/forecasts?status=missing_actual").json()
    assert missing["pagination"]["total_items"] == 0


def test_sorting_and_pagination(api_client):
    first = api_client.get(
        f"{API}/forecasts?page=1&page_size=10&sort_by=forecast_mw&sort_dir=desc"
    ).json()
    second = api_client.get(
        f"{API}/forecasts?page=2&page_size=10&sort_by=forecast_mw&sort_dir=desc"
    ).json()
    assert first["pagination"]["total_pages"] == 15
    assert first["pagination"]["has_next"] is True
    assert first["items"][0]["forecast_mw"] >= second["items"][0]["forecast_mw"]


def test_csv_export(api_client):
    response = api_client.get(f"{API}/export")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "windiq_forecasts_2026-01-10_2026-01-12.csv" in response.headers["content-disposition"]
    assert response.headers["x-row-count"] == "144"
    text = response.content.decode("utf-8-sig")
    header = text.splitlines()[0]
    assert "forecast_mw" in header
    assert "decision_cutoff_utc" in header
    assert "synthetic" in header
    assert len(text.splitlines()) == 145


def test_csv_export_respects_filters(api_client):
    response = api_client.get(f"{API}/export?lead_time_bucket=6to12")
    assert response.status_code == 200
    assert response.headers["x-row-count"] == "0"


def test_openapi_schema_is_generated(api_client):
    schema = api_client.get("/openapi.json").json()
    assert schema["info"]["title"] == "WindIQ API"
    assert "/api/v1/forecasts/{delivery_interval}/vintages" in schema["paths"]
