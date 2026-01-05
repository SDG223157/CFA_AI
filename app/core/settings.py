from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AppSettings:
    active_root_dir: str | None = None


def load_settings(data_dir: Path) -> AppSettings:
    path = data_dir / "settings.json"
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            return AppSettings()
        return AppSettings(active_root_dir=str(obj.get("active_root_dir") or "") or None)
    except Exception:
        return AppSettings()


def save_settings(data_dir: Path, settings: AppSettings) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    path = data_dir / "settings.json"
    obj: dict[str, Any] = {"active_root_dir": settings.active_root_dir}
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


