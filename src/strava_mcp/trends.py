"""Compute fitness trends from raw Strava activity data.

Pure functions — no API calls, no side effects. Takes activity dicts
(as returned by Strava API) and returns derived metrics.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


# ── Default HR zones (used when user hasn't configured their own) ────────────

DEFAULT_HR_ZONES = {
    "z1": [0, 130],
    "z2": [130, 152],
    "z3": [152, 162],
    "z4": [162, 172],
    "z5": [172, 999],
}


def _get_z2_range(hr_zones: dict | None) -> tuple[int, int]:
    """Extract Z2 heart rate range from zones config."""
    if hr_zones and "z2" in hr_zones:
        z2 = hr_zones["z2"]
        return (z2[0], z2[1])
    return (DEFAULT_HR_ZONES["z2"][0], DEFAULT_HR_ZONES["z2"][1])


def _is_z2_run(run: dict, z2_low: int, z2_high: int) -> bool:
    """Check if a run's average HR falls in Z2."""
    avg_hr = run.get("average_heartrate")
    if not avg_hr:
        return False
    return z2_low <= avg_hr <= z2_high


def compute_z2_pace(runs: list[dict], hr_zones: dict | None = None) -> dict:
    """Compute current Z2 pace from runs with avg HR in Z2 range.

    Returns:
        {"z2_pace_min_per_km": float|None, "z2_avg_hr": float|None, "z2_run_count": int}
    """
    z2_low, z2_high = _get_z2_range(hr_zones)
    z2_runs = [r for r in runs if _is_z2_run(r, z2_low, z2_high)]

    if not z2_runs:
        return {"z2_pace_min_per_km": None, "z2_avg_hr": None, "z2_run_count": 0}

    total_time = sum(r["moving_time"] for r in z2_runs)
    total_dist = sum(r["distance"] for r in z2_runs)
    avg_hr = sum(r["average_heartrate"] for r in z2_runs) / len(z2_runs)

    pace = round((total_time / 60) / (total_dist / 1000), 2) if total_dist > 0 else None

    return {
        "z2_pace_min_per_km": pace,
        "z2_avg_hr": round(avg_hr, 1),
        "z2_run_count": len(z2_runs),
    }


def compute_weekly_mileage(runs: list[dict], weeks: int = 8) -> list[dict]:
    """Group runs by ISO week and sum distance."""
    buckets: dict[str, dict] = {}
    for r in runs:
        try:
            d = datetime.fromisoformat(r["start_date_local"][:10])
        except (KeyError, ValueError):
            continue
        wk = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
        bucket = buckets.setdefault(wk, {"week": wk, "runs": 0, "km": 0.0})
        bucket["runs"] += 1
        bucket["km"] = round(bucket["km"] + r["distance"] / 1000, 2)

    return sorted(buckets.values(), key=lambda x: x["week"])[-weeks:]


def compute_z2_pace_trend(
    runs: list[dict], hr_zones: dict | None = None, months: int = 6
) -> list[dict]:
    """Compute monthly Z2 pace progression.

    Returns list of {"month": "YYYY-MM", "pace": float, "runs": int}.
    """
    z2_low, z2_high = _get_z2_range(hr_zones)
    monthly: dict[str, dict] = {}

    for r in runs:
        if not _is_z2_run(r, z2_low, z2_high):
            continue
        try:
            month = r["start_date_local"][:7]  # "YYYY-MM"
        except (KeyError, TypeError):
            continue
        dist_km = r["distance"] / 1000
        if dist_km <= 0:
            continue
        pace = (r["moving_time"] / 60) / dist_km
        bucket = monthly.setdefault(month, {"month": month, "paces": [], "runs": 0})
        bucket["paces"].append(pace)
        bucket["runs"] += 1

    result = []
    for m in sorted(monthly.keys())[-months:]:
        b = monthly[m]
        avg_pace = round(sum(b["paces"]) / len(b["paces"]), 2)
        result.append({"month": b["month"], "pace": avg_pace, "runs": b["runs"]})

    return result


def compute_avg_weekly_km(weekly_data: list[dict], last_n: int = 4) -> float | None:
    """Average weekly km over the last N weeks."""
    recent = weekly_data[-last_n:]
    if not recent:
        return None
    return round(sum(w["km"] for w in recent) / len(recent), 2)


def compute_long_run_avg(runs: list[dict], threshold_km: float = 10.0) -> float | None:
    """Average distance of runs longer than threshold."""
    long_runs = [r for r in runs if r["distance"] / 1000 >= threshold_km]
    if not long_runs:
        return None
    return round(sum(r["distance"] / 1000 for r in long_runs) / len(long_runs), 2)


def compute_avg_cadence(runs: list[dict]) -> float | None:
    """Average cadence across runs that have cadence data."""
    cadences = [r["average_cadence"] * 2 for r in runs if r.get("average_cadence")]
    if not cadences:
        return None
    return round(sum(cadences) / len(cadences), 1)


def build_fitness_metrics(runs: list[dict], hr_zones: dict | None = None) -> dict:
    """Compute all fitness metrics from a list of run activities.

    This is the main orchestrator. Call this with 8+ weeks of runs.
    """
    weekly = compute_weekly_mileage(runs, weeks=12)
    z2 = compute_z2_pace(runs, hr_zones)
    z2_trend = compute_z2_pace_trend(runs, hr_zones)

    now = datetime.now(timezone.utc)
    date_range = []
    if runs:
        dates = sorted(r.get("start_date_local", "")[:10] for r in runs if r.get("start_date_local"))
        if dates:
            date_range = [dates[0], dates[-1]]

    return {
        "updated": now.isoformat(),
        "computed_from": {
            "activity_count": len(runs),
            "date_range": date_range,
        },
        "z2_pace_min_per_km": z2["z2_pace_min_per_km"],
        "z2_avg_hr": z2["z2_avg_hr"],
        "z2_run_count": z2["z2_run_count"],
        "avg_weekly_km_4w": compute_avg_weekly_km(weekly, 4),
        "avg_weekly_km_8w": compute_avg_weekly_km(weekly, 8),
        "long_run_avg_km": compute_long_run_avg(runs),
        "avg_cadence": compute_avg_cadence(runs),
        "weekly_mileage_trend": weekly,
        "z2_pace_trend": z2_trend,
    }
