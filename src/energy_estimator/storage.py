"""Local JSON storage with validation, atomic updates and portable backups."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import Device, Scenario, Tariff

SCHEMA_VERSION = 1
APP_ID = "energy-usage-estimator"
_STORE_LOCK = threading.RLock()
MAX_IMPORT_BYTES = 5 * 1024 * 1024
VALID_THEMES = frozenset({"light", "dark"})
DEFAULT_THEME = "light"


class StorageError(RuntimeError):
    """A local file was inaccessible, invalid, or could not be saved."""


def sync_local_file(handle: Any) -> None:
    """Flush writes; fsync is unavailable in the browser's virtual filesystem."""
    handle.flush()
    if not is_browser_runtime():
        os.fsync(handle.fileno())


def is_browser_runtime() -> bool:
    """Detect the Python/WebAssembly runtime used on static GitHub Pages."""
    return sys.platform == "emscripten"


def data_directory(project_root: Path) -> Path:
    """Select server JSON storage or browser-persistent IDBFS JSON storage."""
    configured = os.environ.get("ENERGY_ESTIMATOR_DATA_DIR", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if is_browser_runtime():
        # stlite mounts /mnt through IndexedDB; all visitors get separate browser stores.
        return Path("/mnt/energy-usage-estimator")
    return project_root / "data"


def _decode_document(raw: bytes, path: str) -> dict[str, Any]:
    try:
        parsed = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise StorageError(f"JSON inválido em {path}: {exc}") from exc
    if not isinstance(parsed, dict) or parsed.get("schema_version") != SCHEMA_VERSION:
        raise StorageError(f"Formato ou versão incompatível em {path}; esperado schema_version={SCHEMA_VERSION}.")
    return parsed


def _unique_identifiers(objects: list[Device] | list[Scenario], collection: str) -> None:
    ids = [item.id for item in objects]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Existem IDs duplicados na lista de {collection}.")
    names = [item.name.casefold() for item in objects]
    if len(names) != len(set(names)):
        raise ValueError(f"Existem nomes duplicados na lista de {collection}.")


def _validate_refs(devices: list[Device], scenarios: list[Scenario]) -> None:
    existing = {device.id for device in devices}
    for scenario in scenarios:
        for item in scenario.items:
            if item.device_id not in existing:
                raise ValueError(f"O cenário '{scenario.name}' referencia um aparelho inexistente.")
