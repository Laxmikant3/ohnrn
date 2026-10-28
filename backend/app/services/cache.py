"""File-backed cache for normalised Elexon records.

Trade-off documented in the README: a 2.5 MB immutable month of data does not
justify PostgreSQL for this assignment. A JSON cache gives reproducible,
git-ignorable persistence with atomic writes, integrity hashes and retrieval
audit events, and the API can start with no upstream connectivity.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

from app.config import Settings
from app.domain import SCHEMA_VERSION
from app.utils.timeutils import iso_z

logger = logging.getLogger("windiq.cache")

ACTUAL_FILE = "actual_wind.json"
FORECAST_FILE = "forecast_wind.json"
MANIFEST_FILE = "manifest.json"


class CacheError(RuntimeError):
    pass


class CacheStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cache_dir = settings.cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    def paths(self) -> dict[str, Path]:
        return {
            "actual": self.cache_dir / ACTUAL_FILE,
            "forecast": self.cache_dir / FORECAST_FILE,
            "manifest": self.cache_dir / MANIFEST_FILE,
        }

    def exists(self) -> bool:
        paths = self.paths()
        return paths["actual"].exists() and paths["forecast"].exists()

    def signature(self) -> str:
        """Cheap fingerprint used to invalidate in-memory derived data."""
        digest = hashlib.sha256()
        for key in ("actual", "forecast", "manifest"):
            path = self.paths()[key]
            try:
                stat = path.stat()
                digest.update(f"{key}:{stat.st_mtime_ns}:{stat.st_size}".encode())
            except FileNotFoundError:
                digest.update(f"{key}:missing".encode())
        return digest.hexdigest()[:16]

    # ------------------------------------------------------------------
    def read_json(self, key: str) -> dict[str, Any] | None:
        path = self.paths()[key]
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise CacheError(f"Cache file {path.name} is unreadable: {exc}") from exc
        if not isinstance(payload, dict):
            raise CacheError(f"Cache file {path.name} has an unexpected structure")
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise CacheError(
                f"Cache file {path.name} has schema version "
                f"{payload.get('schema_version')}, expected {SCHEMA_VERSION}"
            )
        return payload

    def read_actual(self) -> dict[str, Any] | None:
        return self.read_json("actual")

    def read_forecast(self) -> dict[str, Any] | None:
        return self.read_json("forecast")

    def read_manifest(self) -> dict[str, Any]:
        with self._lock:
            payload = self.read_json("manifest") or {}
        payload.setdefault("schema_version", SCHEMA_VERSION)
        payload.setdefault("retrieval_events", [])
        payload.setdefault("files", {})
        payload.setdefault("last_success", {})
        return payload

    # ------------------------------------------------------------------
    def write_actual(
        self,
        records: list[dict[str, Any]],
        windows: list[dict[str, str]],
        stats: dict[str, Any],
        retrieved_at: dt.datetime,
        first_retrieved_at: dt.datetime | None,
        is_synthetic: bool = False,
    ) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "dataset": "FUELHH",
            "fuel_type": "WIND",
            "source": "Elexon BMRS",
            "source_endpoint": f"{self.settings.elexon_base_url}/datasets/FUELHH/stream",
            "documentation_url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/FUELHH/stream",
            "is_synthetic": is_synthetic,
            "unit": "MW",
            "granularity_minutes": 30,
            "retrieved_at": iso_z(retrieved_at),
            "first_retrieved_at": iso_z(first_retrieved_at or retrieved_at),
            "request_windows": windows,
            "stats": stats,
            "records": records,
        }
        self._write("actual", payload)

    def write_forecast(
        self,
        records: list[dict[str, Any]],
        windows: list[dict[str, str]],
        stats: dict[str, Any],
        retrieved_at: dt.datetime,
        first_retrieved_at: dt.datetime | None,
        granularity_minutes: int,
        is_synthetic: bool = False,
    ) -> None:
        payload = {
            "schema_version": SCHEMA_VERSION,
            "dataset": "WINDFOR",
            "source": "Elexon BMRS",
            "source_endpoint": f"{self.settings.elexon_base_url}/datasets/WINDFOR/stream",
            "documentation_url": "https://bmrs.elexon.co.uk/api-documentation/endpoint/datasets/WINDFOR/stream",
            "is_synthetic": is_synthetic,
            "unit": "MW",
            "granularity_minutes": granularity_minutes,
            "retrieved_at": iso_z(retrieved_at),
            "first_retrieved_at": iso_z(first_retrieved_at or retrieved_at),
            "request_windows": windows,
            "stats": stats,
            "records": records,
        }
        self._write("forecast", payload)

    def _write(self, key: str, payload: dict[str, Any]) -> None:
        path = self.paths()[key]
        tmp = path.with_suffix(path.suffix + ".tmp")
        encoded = json.dumps(payload, separators=(",", ":"), default=str)
        with self._lock:
            try:
                with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp, path)
            except OSError as exc:
                raise CacheError(f"Could not write cache file {path.name}: {exc}") from exc
            manifest = self.read_json("manifest") or {
                "schema_version": SCHEMA_VERSION,
                "created_at": iso_z(dt.datetime.now(dt.UTC)),
                "retrieval_events": [],
                "last_success": {},
                "files": {},
            }
            digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
            manifest.setdefault("files", {})[key] = {
                "file": path.name,
                "bytes": len(encoded.encode("utf-8")),
                "sha256": digest,
                "records": len(payload.get("records", [])),
                "retrieved_at": payload.get("retrieved_at"),
            }
            manifest["updated_at"] = iso_z(dt.datetime.now(dt.UTC))
            manifest["is_synthetic"] = False
            manifest.setdefault("last_success", {})[key] = payload.get("retrieved_at")
            self._write_manifest(manifest)

    def _write_manifest(self, manifest: dict[str, Any]) -> None:
        path = self.paths()["manifest"]
        tmp = path.with_suffix(path.suffix + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(manifest, handle, indent=2, default=str)
            os.replace(tmp, path)
        except OSError as exc:
            raise CacheError(f"Could not write manifest: {exc}") from exc

    def append_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            manifest = self.read_manifest()
            events = manifest.get("retrieval_events", [])
            events.append(event)
            manifest["retrieval_events"] = events[-200:]
            manifest["updated_at"] = iso_z(dt.datetime.now(dt.UTC))
            self._write_manifest(manifest)

    # ------------------------------------------------------------------
    def file_metadata(self) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        for key, path in self.paths().items():
            try:
                stat = path.stat()
                meta[key] = {
                    "file": path.name,
                    "exists": True,
                    "bytes": stat.st_size,
                    "modified_at": iso_z(dt.datetime.fromtimestamp(stat.st_mtime, dt.UTC)),
                }
            except FileNotFoundError:
                meta[key] = {"file": path.name, "exists": False}
        return meta
