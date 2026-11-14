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


class JsonStore:
    """Single-user JSON repository; all files stay under a chosen local directory."""

    def __init__(self, directory: Path):
        self.directory = Path(directory)

    def _path(self, name: str) -> Path:
        return self.directory / f"{name}.json"

    def _read(self, name: str) -> dict[str, Any] | None:
        path = self._path(name)
        if not path.exists():
            return None
        try:
            return _decode_document(path.read_bytes(), str(path))
        except OSError as exc:
            raise StorageError(f"Falha ao ler {path}: {exc}") from exc

    def _write(self, name: str, document: dict[str, Any]) -> None:
        """Write a valid JSON document using same-directory atomic replacement."""
        path = self._path(name)
        tmp_name: str | None = None
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.directory, prefix=f".{name}-", suffix=".tmp",
                delete=False,
            ) as handle:
                tmp_name = handle.name
                json.dump(document, handle, ensure_ascii=False, indent=2, allow_nan=False)
                handle.write("\n")
                handle.flush()
                sync_local_file(handle)
            os.replace(tmp_name, path)
        except (OSError, ValueError, TypeError) as exc:
            raise StorageError(f"Falha ao salvar {path}: {exc}") from exc
        finally:
            if tmp_name is not None:
                Path(tmp_name).unlink(missing_ok=True)

    def load_devices(self) -> list[Device]:
        """Load all devices without silently replacing malformed files."""
        with _STORE_LOCK:
            document = self._read("devices")
            if document is None:
                return []
            try:
                raw = document["devices"]
                if not isinstance(raw, list):
                    raise ValueError("devices precisa ser uma lista.")
                devices = [Device.from_dict(item) for item in raw]
                _unique_identifiers(devices, "aparelhos")
                return devices
            except (KeyError, TypeError, ValueError) as exc:
                raise StorageError(f"Dados inválidos em {self._path('devices')}: {exc}") from exc

    def load_scenarios(self) -> list[Scenario]:
        """Load all saved usage scenarios."""
        with _STORE_LOCK:
            document = self._read("scenarios")
            if document is None:
                return []
            try:
                raw = document["scenarios"]
                if not isinstance(raw, list):
                    raise ValueError("scenarios precisa ser uma lista.")
                scenarios = [Scenario.from_dict(item) for item in raw]
                _unique_identifiers(scenarios, "cenários")
                return scenarios
            except (KeyError, TypeError, ValueError) as exc:
                raise StorageError(f"Dados inválidos em {self._path('scenarios')}: {exc}") from exc

    def load_tariff(self) -> Tariff:
        """Load the remembered billing mode and input figures."""
        with _STORE_LOCK:
            document = self._read("settings")
            if document is None:
                return Tariff()
            try:
                return Tariff.from_dict(document["tariff"])
            except (KeyError, TypeError, ValueError) as exc:
                raise StorageError(f"Tarifa inválida em {self._path('settings')}: {exc}") from exc

    def load_theme(self) -> str:
        """Read optional appearance preference from settings.json (legacy files default to light)."""
        with _STORE_LOCK:
            document = self._read("settings")
            theme = document.get("appearance", DEFAULT_THEME) if document is not None else DEFAULT_THEME
            if not isinstance(theme, str) or theme not in VALID_THEMES:
                raise StorageError("Tema inválido em settings.json. Use 'light' ou 'dark'.")
            return theme

    def save_theme(self, theme: str) -> None:
        """Persist theme without discarding saved tariff or older settings fields."""
        if not isinstance(theme, str) or theme not in VALID_THEMES:
            raise ValueError("Tema inválido. Escolha 'light' ou 'dark'.")
        with _STORE_LOCK:
            current = self._read("settings") or {"schema_version": SCHEMA_VERSION, "tariff": Tariff().to_dict()}
            # Do not silently replace a damaged tariff with defaults.
            Tariff.from_dict(current["tariff"])
            current["appearance"] = theme
            self._write("settings", current)

    def load_all(self) -> tuple[list[Device], list[Scenario], Tariff]:
        """Read a consistent logical snapshot and verify all device references."""
        with _STORE_LOCK:
            devices = self.load_devices()
            scenarios = self.load_scenarios()
            try:
                _validate_refs(devices, scenarios)
            except ValueError as exc:
                raise StorageError(str(exc)) from exc
            return devices, scenarios, self.load_tariff()

    def upsert_device(self, device: Device) -> None:
        """Insert or update a device; reject duplicate names of different devices."""
        with _STORE_LOCK:
            devices = self.load_devices()
            if any(other.name.casefold() == device.name.casefold() and other.id != device.id for other in devices):
                raise ValueError("Já existe um aparelho com esse nome.")
            devices = [item for item in devices if item.id != device.id] + [device]
            self._write("devices", {"schema_version": SCHEMA_VERSION, "devices": [item.to_dict() for item in devices]})

    def delete_device(self, device_id: str) -> bool:
        """Delete an unused device; prevent dangling references in scenarios."""
        with _STORE_LOCK:
            if any(item.device_id == device_id for scenario in self.load_scenarios() for item in scenario.items):
                raise ValueError("Remova o aparelho dos cenários salvos antes de excluí-lo.")
            devices = self.load_devices()
            updated = [device for device in devices if device.id != device_id]
            if len(updated) == len(devices):
                return False
            self._write("devices", {"schema_version": SCHEMA_VERSION, "devices": [item.to_dict() for item in updated]})
            return True

    def upsert_scenario(self, scenario: Scenario) -> None:
        """Insert or update a scenario after validating its device references."""
        with _STORE_LOCK:
            scenarios = self.load_scenarios()
            if any(other.name.casefold() == scenario.name.casefold() and other.id != scenario.id for other in scenarios):
                raise ValueError("Já existe um cenário com esse nome.")
            updated = [item for item in scenarios if item.id != scenario.id] + [scenario]
            _validate_refs(self.load_devices(), updated)
            self._write("scenarios", {"schema_version": SCHEMA_VERSION, "scenarios": [item.to_dict() for item in updated]})

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario without affecting its reusable devices."""
        with _STORE_LOCK:
            scenarios = self.load_scenarios()
            updated = [item for item in scenarios if item.id != scenario_id]
            if len(updated) == len(scenarios):
                return False
            self._write("scenarios", {"schema_version": SCHEMA_VERSION, "scenarios": [item.to_dict() for item in updated]})
            return True

    def save_tariff(self, tariff: Tariff) -> None:
        """Persist the tariff without resetting the saved light/dark preference."""
        with _STORE_LOCK:
            current = self._read("settings") or {"schema_version": SCHEMA_VERSION}
            # Validate previous preference so corrupted settings are not overwritten.
            self.load_theme()
            current["tariff"] = tariff.to_dict()
            self._write("settings", current)

    def backup_bytes(self) -> bytes:
        """Export all user data in one versioned, portable JSON backup."""
        with _STORE_LOCK:
            devices, scenarios, tariff = self.load_all()
            document = {
                "app": APP_ID,
                "schema_version": SCHEMA_VERSION,
                "exported_at_utc": datetime.now(timezone.utc).isoformat(),
                "devices": [item.to_dict() for item in devices],
                "scenarios": [item.to_dict() for item in scenarios],
                "tariff": tariff.to_dict(),
                "appearance": self.load_theme(),
            }
            return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")

    def save_now(self) -> Path:
        """Explicitly flush a verified snapshot to all JSON files and save a dated on-disk backup.

        Automatic persistence on each confirmed edit remains in place; this is a manual
        checkpoint, not a mechanism to capture unsubmitted Streamlit form drafts.
        """
        with _STORE_LOCK:
            devices, scenarios, tariff = self.load_all()
            theme = self.load_theme()
            snapshot = self.backup_bytes()
            # Re-write all canonical files, including missing files on a fresh install.
            self._write("devices", {"schema_version": SCHEMA_VERSION, "devices": [d.to_dict() for d in devices]})
            self._write("scenarios", {"schema_version": SCHEMA_VERSION, "scenarios": [s.to_dict() for s in scenarios]})
            self._write("settings", {"schema_version": SCHEMA_VERSION, "tariff": tariff.to_dict(), "appearance": theme})
            folder = self.directory / "backups"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            path = folder / f"manual-{stamp}.json"
            try:
                folder.mkdir(parents=True, exist_ok=True)
                with path.open("xb") as handle:
                    handle.write(snapshot)
                    handle.flush()
                    sync_local_file(handle)
            except OSError as exc:
                raise StorageError(f"Falha ao criar cópia manual de segurança: {exc}") from exc
            return path

    def restore_backup(self, raw: bytes) -> Path:
        """Validate whole backup before replacing data; save old state first."""
        if len(raw) > MAX_IMPORT_BYTES:
            raise ValueError("Backup excede o limite de 5 MB.")
        try:
            document = _decode_document(raw, "backup importado")
            if document.get("app") != APP_ID:
                raise ValueError("O arquivo não é um backup deste aplicativo.")
            if not isinstance(document.get("devices"), list) or not isinstance(document.get("scenarios"), list):
                raise ValueError("Listas devices/scenarios não encontradas.")
            devices = [Device.from_dict(item) for item in document["devices"]]
            scenarios = [Scenario.from_dict(item) for item in document["scenarios"]]
            tariff = Tariff.from_dict(document["tariff"])
            appearance = document.get("appearance", DEFAULT_THEME)
            if not isinstance(appearance, str) or appearance not in VALID_THEMES:
                raise ValueError("Tema inválido no backup.")
            _unique_identifiers(devices, "aparelhos")
            _unique_identifiers(scenarios, "cenários")
            _validate_refs(devices, scenarios)
        except (KeyError, TypeError, ValueError, StorageError) as exc:
            raise ValueError(f"Backup rejeitado: {exc}") from exc

        with _STORE_LOCK:
            old_state = self.backup_bytes()  # Aborts without modifying files if existing state is corrupt.
            backup_folder = self.directory / "backups"
            try:
                backup_folder.mkdir(parents=True, exist_ok=True)
                backup_path = backup_folder / f"before-import-{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}.json"
                with backup_path.open("xb") as handle:
                    handle.write(old_state)
                    handle.flush()
                    sync_local_file(handle)
            except OSError as exc:
                raise StorageError(f"Não foi possível criar backup de segurança: {exc}") from exc

            # Each file is atomically replaced. On failure, revert already-written files.
            try:
                self._write("devices", {"schema_version": SCHEMA_VERSION, "devices": [item.to_dict() for item in devices]})
                self._write("scenarios", {"schema_version": SCHEMA_VERSION, "scenarios": [item.to_dict() for item in scenarios]})
                self._write("settings", {"schema_version": SCHEMA_VERSION, "tariff": tariff.to_dict(), "appearance": appearance})
            except StorageError as exc:
                original = json.loads(old_state)
                try:
                    self._write("devices", {"schema_version": SCHEMA_VERSION, "devices": original["devices"]})
                    self._write("scenarios", {"schema_version": SCHEMA_VERSION, "scenarios": original["scenarios"]})
                    self._write("settings", {"schema_version": SCHEMA_VERSION, "tariff": original["tariff"], "appearance": original.get("appearance", DEFAULT_THEME)})
                except StorageError as rollback_exc:
                    raise StorageError(f"Falha na importação e reversão: {rollback_exc}. Backup: {backup_path}") from exc
                raise
            return backup_path
