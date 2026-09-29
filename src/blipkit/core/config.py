"""Platform paths and persistent application settings."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def data_dir() -> Path:
    override = os.environ.get("BLIPKIT_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Blipkit"
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home())) / "Blipkit"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "Blipkit"


@dataclass
class AppSettings:
    theme: str = "light"
    autosave_seconds: int = 120
    recent_projects: list[str] = field(default_factory=list)
    last_project: str = ""
    piano_labels: str = "notes"

    @classmethod
    def load(cls) -> AppSettings:
        path = data_dir() / "settings.json"
        if not path.exists():
            return cls()
        try:
            raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return cls(
                theme=str(raw.get("theme", "light")),
                autosave_seconds=int(raw.get("autosave_seconds", 120)),
                recent_projects=list(raw.get("recent_projects", []))[:10],
                last_project=str(raw.get("last_project", "")),
                piano_labels=str(raw.get("piano_labels", "notes")),
            )
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self) -> None:
        root = data_dir()
        root.mkdir(parents=True, exist_ok=True)
        path = root / "settings.json"
        temp = path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temp.replace(path)

    def remember_project(self, path: Path) -> None:
        normalized = str(path.expanduser().resolve())
        self.recent_projects = [item for item in self.recent_projects if item != normalized]
        self.recent_projects.insert(0, normalized)
        self.recent_projects = self.recent_projects[:10]
        self.last_project = normalized
        self.save()
