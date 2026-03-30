"""Persistent athlete memory store for strava-mcp-agent.

Stores training context (zones, goals, injuries, fitness metrics) as JSON files
in ~/.strava-mcp/memory/ so Claude has context across sessions.
"""

from __future__ import annotations

import json
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MEMORY_DIR = Path.home() / ".strava-mcp" / "memory"

# Known memory files and their default structures
DEFAULTS: dict[str, dict] = {
    "athlete_profile": {
        "updated": None,
        "max_hr": None,
        "resting_hr": None,
        "weight_kg": None,
        "ftp_watts": None,
        "hr_zones": {},
        "pace_zones": {},
        "notes": "",
    },
    "fitness_metrics": {
        "updated": None,
        "computed_from": {},
        "z2_pace_min_per_km": None,
        "z2_avg_hr": None,
        "avg_weekly_km_4w": None,
        "avg_weekly_km_8w": None,
        "long_run_avg_km": None,
        "avg_cadence": None,
        "weekly_mileage_trend": [],
        "z2_pace_trend": [],
    },
    "injuries": {
        "updated": None,
        "current": [],
        "resolved": [],
    },
    "goals": {
        "updated": None,
        "primary_goal": "",
        "race_calendar": [],
        "training_phase": "",
        "notes": "",
    },
    "training_notes": {
        "updated": None,
        "entries": [],
    },
}


class StravaMemoryStore:
    """Simple JSON-file-based memory store."""

    def __init__(self, directory: Path | None = None):
        self.dir = directory or MEMORY_DIR
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.dir / f"{name}.json"

    def read(self, name: str) -> dict:
        """Read a memory file, returning defaults if it doesn't exist."""
        path = self._path(name)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return dict(DEFAULTS.get(name, {}))

    def write(self, name: str, data: dict) -> None:
        """Atomically write a memory file."""
        data["updated"] = datetime.now(timezone.utc).isoformat()
        # Write to temp file then rename for atomic write
        tmp = tempfile.NamedTemporaryFile(
            mode="w", dir=self.dir, suffix=".tmp", delete=False
        )
        try:
            json.dump(data, tmp, indent=2)
            tmp.close()
            Path(tmp.name).replace(self._path(name))
        except Exception:
            Path(tmp.name).unlink(missing_ok=True)
            raise

    def merge(self, name: str, updates: dict) -> dict:
        """Read, merge updates, write back. Returns merged data."""
        data = self.read(name)
        for k, v in updates.items():
            if v is not None:
                data[k] = v
        self.write(name, data)
        return data

    def read_all_context(self) -> dict:
        """Read all memory files into a single context dict."""
        ctx = {}
        for name in DEFAULTS:
            ctx[name] = self.read(name)
        return ctx

    def is_stale(self, name: str, max_age_hours: float = 72) -> bool:
        """Check if a memory file is older than max_age_hours."""
        data = self.read(name)
        updated = data.get("updated")
        if not updated:
            return True
        try:
            dt = datetime.fromisoformat(updated)
            age_hrs = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
            return age_hrs > max_age_hours
        except (ValueError, TypeError):
            return True
