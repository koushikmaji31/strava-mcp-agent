#!/usr/bin/env python3
"""
Strava MCP Server — Full Data Access + Persistent Memory
Exposes all Strava data as tools for Claude to use, with athlete context
that persists across sessions.

Required environment variables:
  STRAVA_CLIENT_ID
  STRAVA_CLIENT_SECRET
  STRAVA_REFRESH_TOKEN
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

from strava_mcp.memory import StravaMemoryStore
from strava_mcp.trends import build_fitness_metrics

# ── Strava OAuth config ──────────────────────────────────────────────────────

BASE_URL = "https://www.strava.com/api/v3"
TOKEN_URL = "https://www.strava.com/oauth/token"

_access_token: str | None = None
_token_expiry: float = 0.0

# ── Memory store ─────────────────────────────────────────────────────────────

memory = StravaMemoryStore()


def _get_credentials() -> tuple[str, str, str]:
    """Load OAuth credentials from environment variables."""
    client_id = os.environ.get("STRAVA_CLIENT_ID", "")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET", "")
    refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN", "")
    if not all([client_id, client_secret, refresh_token]):
        raise RuntimeError(
            "Missing Strava credentials. Set STRAVA_CLIENT_ID, "
            "STRAVA_CLIENT_SECRET, and STRAVA_REFRESH_TOKEN environment variables."
        )
    return client_id, client_secret, refresh_token


# ── Token management ─────────────────────────────────────────────────────────

def get_access_token() -> str:
    global _access_token, _token_expiry
    if _access_token and time.time() < _token_expiry - 60:
        return _access_token

    client_id, client_secret, refresh_token = _get_credentials()
    resp = httpx.post(TOKEN_URL, data={
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    data = resp.json()
    _access_token = data["access_token"]
    _token_expiry = data["expires_at"]
    return _access_token


def strava_get(path: str, params: dict | None = None) -> Any:
    headers = {"Authorization": f"Bearer {get_access_token()}"}
    resp = httpx.get(f"{BASE_URL}{path}", headers=headers, params=params or {})
    resp.raise_for_status()
    return resp.json()


# ── Auto-update trends ───────────────────────────────────────────────────────

def _maybe_refresh_trends(activities: list[dict]) -> None:
    """Refresh fitness_metrics if stale, using fetched activities as input."""
    if not memory.is_stale("fitness_metrics", max_age_hours=24):
        return
    runs = [a for a in activities if a.get("type") == "Run"]
    if not runs:
        return
    profile = memory.read("athlete_profile")
    hr_zones = profile.get("hr_zones") or None
    metrics = build_fitness_metrics(runs, hr_zones)
    memory.write("fitness_metrics", metrics)


def _fetch_and_refresh_trends() -> None:
    """Fetch last 12 weeks of activities from Strava and recompute trends."""
    after_dt = datetime.now(timezone.utc) - timedelta(weeks=12)
    activities = strava_get("/athlete/activities", {
        "after": int(after_dt.timestamp()),
        "per_page": 200,
    })
    runs = [a for a in activities if a.get("type") == "Run"]
    if not runs:
        return
    profile = memory.read("athlete_profile")
    hr_zones = profile.get("hr_zones") or None
    metrics = build_fitness_metrics(runs, hr_zones)
    memory.write("fitness_metrics", metrics)


# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    # ── Strava data tools ────────────────────────────────────────────────
    types.Tool(
        name="get_athlete",
        description="Get the authenticated athlete's full profile (name, weight, FTP, stats, clubs).",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_athlete_stats",
        description="Get all-time and recent running/cycling/swimming totals for the athlete.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="list_activities",
        description="List recent activities. Filter by type, date range, or page.",
        inputSchema={
            "type": "object",
            "properties": {
                "per_page": {"type": "integer", "description": "Number of activities (default 30, max 200)"},
                "page": {"type": "integer", "description": "Page number (default 1)"},
                "before": {"type": "string", "description": "ISO date — return activities before this date"},
                "after": {"type": "string", "description": "ISO date — return activities after this date"},
            },
        },
    ),
    types.Tool(
        name="get_activity",
        description="Get full details for a single activity by ID (splits, HR, cadence, device, weather).",
        inputSchema={
            "type": "object",
            "properties": {
                "activity_id": {"type": "integer", "description": "Strava activity ID"},
            },
            "required": ["activity_id"],
        },
    ),
    types.Tool(
        name="get_activity_zones",
        description="Get heart-rate and power zones for a specific activity.",
        inputSchema={
            "type": "object",
            "properties": {
                "activity_id": {"type": "integer", "description": "Strava activity ID"},
            },
            "required": ["activity_id"],
        },
    ),
    types.Tool(
        name="get_activity_laps",
        description="Get per-lap breakdown (pace, HR, distance) for an activity.",
        inputSchema={
            "type": "object",
            "properties": {
                "activity_id": {"type": "integer", "description": "Strava activity ID"},
            },
            "required": ["activity_id"],
        },
    ),
    types.Tool(
        name="get_activity_streams",
        description="Get raw sensor streams: heartrate, pace, cadence, altitude, watts, GPS.",
        inputSchema={
            "type": "object",
            "properties": {
                "activity_id": {"type": "integer", "description": "Strava activity ID"},
                "keys": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Stream types: time, distance, latlng, altitude, "
                        "velocity_smooth, heartrate, cadence, watts, moving, grade_smooth"
                    ),
                },
            },
            "required": ["activity_id"],
        },
    ),
    types.Tool(
        name="get_starred_segments",
        description="List all segments the athlete has starred.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_segment_efforts",
        description="Get all efforts on a specific segment by the athlete.",
        inputSchema={
            "type": "object",
            "properties": {
                "segment_id": {"type": "integer", "description": "Strava segment ID"},
                "per_page": {"type": "integer", "description": "Results per page (default 30)"},
            },
            "required": ["segment_id"],
        },
    ),
    types.Tool(
        name="get_routes",
        description="List all routes created by the athlete.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_gear",
        description="Get details for a specific piece of gear (shoes or bike) by ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "gear_id": {"type": "string", "description": "Gear ID (e.g. g12345678)"},
            },
            "required": ["gear_id"],
        },
    ),
    types.Tool(
        name="get_clubs",
        description="List all clubs the athlete is a member of.",
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="get_running_summary",
        description="Summarise recent runs: avg pace, weekly mileage, best efforts, HR trends — for coaching analysis.",
        inputSchema={
            "type": "object",
            "properties": {
                "weeks": {"type": "integer", "description": "How many weeks back to analyse (default 8)"},
            },
        },
    ),

    # ── Memory / context tools ───────────────────────────────────────────
    types.Tool(
        name="get_athlete_context",
        description=(
            "CALL THIS FIRST in every coaching conversation. Returns the athlete's "
            "persistent training context: HR zones, current Z2 pace, weekly mileage "
            "trends, Z2 pace progression, goals, injuries, and coaching notes. "
            "Auto-refreshes fitness metrics if stale (>3 days)."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    types.Tool(
        name="update_athlete_profile",
        description=(
            "Update the athlete's profile: max HR, resting HR, weight, FTP, HR zones, "
            "or coaching notes. Only provide fields you want to change."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "max_hr": {"type": "integer", "description": "Maximum heart rate"},
                "resting_hr": {"type": "integer", "description": "Resting heart rate"},
                "weight_kg": {"type": "number", "description": "Body weight in kg"},
                "ftp_watts": {"type": "integer", "description": "Functional Threshold Power"},
                "hr_zones": {
                    "type": "object",
                    "description": (
                        "HR zones as {z1: [low, high], z2: [low, high], ...}. "
                        "Example: {z1: [0, 130], z2: [130, 152], z3: [152, 162], z4: [162, 172], z5: [172, 999]}"
                    ),
                },
                "notes": {"type": "string", "description": "General coaching notes about the athlete"},
            },
        },
    ),
    types.Tool(
        name="update_athlete_goals",
        description="Update training goals, race calendar, or current training phase.",
        inputSchema={
            "type": "object",
            "properties": {
                "primary_goal": {"type": "string", "description": "Main training goal (e.g. 'Sub-50 10k by June')"},
                "race_calendar": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of upcoming races: [{name, date, target}]",
                },
                "training_phase": {"type": "string", "description": "Current phase: base building, build, peak, taper, recovery"},
                "notes": {"type": "string", "description": "Additional goal notes"},
            },
        },
    ),
    types.Tool(
        name="update_athlete_injuries",
        description="Track current injuries and recovery. Add new injuries, update status, or mark as resolved.",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["add", "update", "resolve"],
                    "description": "add: new injury, update: change status/notes, resolve: mark as healed",
                },
                "area": {"type": "string", "description": "Body area (e.g. 'left knee', 'right achilles')"},
                "status": {"type": "string", "description": "Current status (e.g. 'monitoring', 'recovering', 'pain-free')"},
                "notes": {"type": "string", "description": "Details about the injury"},
                "since": {"type": "string", "description": "When the injury started (ISO date)"},
            },
            "required": ["action", "area"],
        },
    ),
    types.Tool(
        name="add_training_note",
        description="Add a coaching note or observation that persists across sessions. Keeps last 50 entries.",
        inputSchema={
            "type": "object",
            "properties": {
                "note": {"type": "string", "description": "The training note or observation"},
                "date": {"type": "string", "description": "Date for this note (ISO date, defaults to today)"},
            },
            "required": ["note"],
        },
    ),
]


# ── Tool handlers ────────────────────────────────────────────────────────────

def _json_out(data: Any) -> list[types.TextContent]:
    return [types.TextContent(type="text", text=json.dumps(data, indent=2))]


def _build_running_summary(runs: list[dict], weeks: int) -> dict:
    """Build a structured running summary from a list of run activities."""
    summary: dict[str, Any] = {
        "period_weeks": weeks,
        "total_runs": len(runs),
        "total_distance_km": round(sum(r["distance"] for r in runs) / 1000, 2),
        "total_time_hrs": round(sum(r["moving_time"] for r in runs) / 3600, 2),
        "avg_pace_min_per_km": None,
        "best_5k_effort_min": None,
        "best_10k_effort_min": None,
        "avg_hr": None,
        "weekly_km": [],
        "recent_runs": [],
    }

    if not runs:
        return summary

    total_dist = sum(r["distance"] for r in runs)
    total_time = sum(r["moving_time"] for r in runs)
    if total_dist > 0:
        summary["avg_pace_min_per_km"] = round((total_time / 60) / (total_dist / 1000), 2)

    hr_values = [r["average_heartrate"] for r in runs if r.get("average_heartrate")]
    if hr_values:
        summary["avg_hr"] = round(sum(hr_values) / len(hr_values), 1)

    # Best efforts from activity best_efforts field
    best_5k = None
    best_10k = None
    for r in runs:
        for effort in r.get("best_efforts") or []:
            elapsed = effort.get("elapsed_time", 0) / 60
            if effort.get("name") == "5k" and (best_5k is None or elapsed < best_5k):
                best_5k = elapsed
            elif effort.get("name") == "10k" and (best_10k is None or elapsed < best_10k):
                best_10k = elapsed
    summary["best_5k_effort_min"] = round(best_5k, 2) if best_5k else None
    summary["best_10k_effort_min"] = round(best_10k, 2) if best_10k else None

    # Weekly breakdown
    week_buckets: dict[str, dict] = {}
    for r in runs:
        d = datetime.fromisoformat(r["start_date_local"][:10])
        wk = (d - timedelta(days=d.weekday())).strftime("%Y-%m-%d")
        bucket = week_buckets.setdefault(wk, {"week": wk, "runs": 0, "km": 0.0})
        bucket["runs"] += 1
        bucket["km"] = round(bucket["km"] + r["distance"] / 1000, 2)
    summary["weekly_km"] = sorted(week_buckets.values(), key=lambda x: x["week"])

    # Last 5 runs
    for r in sorted(runs, key=lambda x: x["start_date"], reverse=True)[:5]:
        dist_km = round(r["distance"] / 1000, 2)
        pace = round((r["moving_time"] / 60) / dist_km, 2) if dist_km else None
        summary["recent_runs"].append({
            "id": r["id"],
            "name": r["name"],
            "date": r["start_date_local"][:10],
            "distance_km": dist_km,
            "pace_min_per_km": pace,
            "avg_hr": r.get("average_heartrate"),
            "elapsed_min": round(r["elapsed_time"] / 60, 1),
        })

    return summary


# ── Memory tool handlers ─────────────────────────────────────────────────────

def _handle_get_athlete_context() -> list[types.TextContent]:
    """Load full athlete context. Auto-refresh trends if stale."""
    if memory.is_stale("fitness_metrics", max_age_hours=72):
        try:
            _fetch_and_refresh_trends()
        except Exception:
            pass  # return stale data rather than failing

    ctx = memory.read_all_context()

    # Add a hint about zones being defaults
    profile = ctx.get("athlete_profile", {})
    if not profile.get("hr_zones"):
        ctx["_hint"] = (
            "HR zones are not configured. Using defaults (Z2: 130-152 bpm). "
            "Ask the athlete for their max HR or lactate threshold to set accurate zones "
            "via update_athlete_profile."
        )

    return _json_out(ctx)


def _handle_update_athlete_profile(arguments: dict) -> list[types.TextContent]:
    fields = {k: v for k, v in arguments.items() if v is not None}
    updated = memory.merge("athlete_profile", fields)
    # If zones changed, invalidate fitness metrics so they recompute with new zones
    if "hr_zones" in fields:
        try:
            _fetch_and_refresh_trends()
        except Exception:
            pass
    return _json_out({"status": "updated", "athlete_profile": updated})


def _handle_update_athlete_goals(arguments: dict) -> list[types.TextContent]:
    fields = {k: v for k, v in arguments.items() if v is not None}
    updated = memory.merge("goals", fields)
    return _json_out({"status": "updated", "goals": updated})


def _handle_update_athlete_injuries(arguments: dict) -> list[types.TextContent]:
    action = arguments["action"]
    area = arguments["area"]
    injuries = memory.read("injuries")

    if action == "add":
        injuries["current"].append({
            "area": area,
            "status": arguments.get("status", "monitoring"),
            "since": arguments.get("since", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
            "notes": arguments.get("notes", ""),
        })
    elif action == "update":
        for entry in injuries["current"]:
            if entry["area"].lower() == area.lower():
                if arguments.get("status"):
                    entry["status"] = arguments["status"]
                if arguments.get("notes"):
                    entry["notes"] = arguments["notes"]
                break
    elif action == "resolve":
        resolved_entry = None
        injuries["current"] = [
            e for e in injuries["current"]
            if e["area"].lower() != area.lower() or (resolved_entry := e) is None
        ]
        if resolved_entry:
            resolved_entry["resolved_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            resolved_entry["status"] = "resolved"
            injuries["resolved"].append(resolved_entry)

    memory.write("injuries", injuries)
    return _json_out({"status": "updated", "injuries": injuries})


def _handle_add_training_note(arguments: dict) -> list[types.TextContent]:
    note_date = arguments.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    notes = memory.read("training_notes")
    notes["entries"].append({"date": note_date, "note": arguments["note"]})
    # Keep only the last 50 entries
    notes["entries"] = notes["entries"][-50:]
    memory.write("training_notes", notes)
    return _json_out({"status": "added", "total_notes": len(notes["entries"])})


# ── MCP Server ───────────────────────────────────────────────────────────────

server = Server("strava-mcp")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    # ── Memory tools ─────────────────────────────────────────────────────
    if name == "get_athlete_context":
        return _handle_get_athlete_context()
    if name == "update_athlete_profile":
        return _handle_update_athlete_profile(arguments)
    if name == "update_athlete_goals":
        return _handle_update_athlete_goals(arguments)
    if name == "update_athlete_injuries":
        return _handle_update_athlete_injuries(arguments)
    if name == "add_training_note":
        return _handle_add_training_note(arguments)

    # ── Strava data tools ────────────────────────────────────────────────

    # Simple GET endpoints
    simple_routes = {
        "get_athlete": "/athlete",
        "get_starred_segments": "/segments/starred",
    }
    if name in simple_routes:
        return _json_out(strava_get(simple_routes[name]))

    if name == "get_athlete_stats":
        athlete = strava_get("/athlete")
        return _json_out(strava_get(f"/athletes/{athlete['id']}/stats"))

    if name == "list_activities":
        params: dict[str, Any] = {
            "per_page": arguments.get("per_page", 30),
            "page": arguments.get("page", 1),
        }
        for key in ("before", "after"):
            if key in arguments:
                params[key] = int(datetime.fromisoformat(arguments[key]).timestamp())
        activities = strava_get("/athlete/activities", params)
        _maybe_refresh_trends(activities)  # auto-update trends
        return _json_out(activities)

    if name == "get_activity":
        return _json_out(strava_get(f"/activities/{arguments['activity_id']}"))

    if name == "get_activity_zones":
        return _json_out(strava_get(f"/activities/{arguments['activity_id']}/zones"))

    if name == "get_activity_laps":
        return _json_out(strava_get(f"/activities/{arguments['activity_id']}/laps"))

    if name == "get_activity_streams":
        keys = arguments.get("keys", [
            "time", "distance", "altitude", "velocity_smooth",
            "heartrate", "cadence", "moving", "grade_smooth",
        ])
        params = {"keys": ",".join(keys), "key_by_type": True}
        return _json_out(strava_get(f"/activities/{arguments['activity_id']}/streams", params))

    if name == "get_segment_efforts":
        params = {
            "segment_id": arguments["segment_id"],
            "per_page": arguments.get("per_page", 30),
        }
        return _json_out(strava_get("/segment_efforts", params))

    if name == "get_routes":
        athlete = strava_get("/athlete")
        return _json_out(strava_get(f"/athletes/{athlete['id']}/routes"))

    if name == "get_gear":
        return _json_out(strava_get(f"/gear/{arguments['gear_id']}"))

    if name == "get_clubs":
        return _json_out(strava_get("/athlete/clubs"))

    if name == "get_running_summary":
        weeks = arguments.get("weeks", 8)
        after_dt = datetime.now(timezone.utc) - timedelta(weeks=weeks)
        activities = strava_get("/athlete/activities", {
            "after": int(after_dt.timestamp()),
            "per_page": 200,
        })
        runs = [a for a in activities if a.get("type") == "Run"]
        _maybe_refresh_trends(activities)  # auto-update trends
        return _json_out(_build_running_summary(runs, weeks))

    return [types.TextContent(type="text", text=f"Unknown tool: {name}")]


# ── Entry point ──────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (r, w):
        await server.run(r, w, server.create_initialization_options())


def run():
    """CLI entry point."""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    run()
