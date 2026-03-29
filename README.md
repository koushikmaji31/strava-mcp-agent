# strava-mcp

**Give Claude access to your Strava data.** An MCP server that exposes your runs, rides, swims, and all Strava metrics as tools for AI-powered coaching, analysis, and conversation.

---

## What it does

`strava-mcp` connects your Strava account to any MCP-compatible client (Claude Desktop, Claude Code, etc.) and provides **13 tools** covering every aspect of your athletic data:

| Tool | Description |
|------|-------------|
| `get_athlete` | Your profile — name, weight, FTP, bio |
| `get_athlete_stats` | All-time & recent totals for run/bike/swim |
| `list_activities` | Browse activities with date/type filtering |
| `get_activity` | Full detail for one activity (splits, HR, cadence, weather) |
| `get_activity_zones` | Heart-rate and power zone distribution |
| `get_activity_laps` | Per-lap pace, HR, and distance breakdown |
| `get_activity_streams` | Raw sensor data (GPS, HR, cadence, watts, altitude) |
| `get_starred_segments` | Your starred segments |
| `get_segment_efforts` | Efforts on a specific segment |
| `get_routes` | Routes you've created |
| `get_gear` | Shoe/bike details and mileage |
| `get_clubs` | Clubs you belong to |
| `get_running_summary` | AI-ready coaching summary (weekly mileage, pace trends, best efforts, HR stats) |

## Installation

```bash
pip install strava-mcp
```

Or install from source:

```bash
git clone https://github.com/koushikmaji/strava-mcp.git
cd strava-mcp
pip install -e .
```

## Setup

### 1. Create a Strava API Application

1. Go to [https://www.strava.com/settings/api](https://www.strava.com/settings/api)
2. Create an application (use `http://localhost:8888/callback` as the redirect URI)
3. Note your **Client ID** and **Client Secret**

### 2. Get Your Refresh Token

```bash
python get_token.py
```

This opens a browser for Strava authorization and returns your refresh token.

### 3. Set Environment Variables

```bash
export STRAVA_CLIENT_ID="your_client_id"
export STRAVA_CLIENT_SECRET="your_client_secret"
export STRAVA_REFRESH_TOKEN="your_refresh_token"
```

### 4. Configure Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "strava": {
      "command": "strava-mcp",
      "env": {
        "STRAVA_CLIENT_ID": "your_client_id",
        "STRAVA_CLIENT_SECRET": "your_client_secret",
        "STRAVA_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

Or run with Python directly:

```json
{
  "mcpServers": {
    "strava": {
      "command": "python",
      "args": ["-m", "strava_mcp"],
      "env": {
        "STRAVA_CLIENT_ID": "your_client_id",
        "STRAVA_CLIENT_SECRET": "your_client_secret",
        "STRAVA_REFRESH_TOKEN": "your_refresh_token"
      }
    }
  }
}
```

## Usage Examples

Once connected, just talk to Claude:

- *"How was my running this month?"*
- *"Compare my last 5 runs — am I getting faster?"*
- *"What's my average heart rate on long runs vs tempo runs?"*
- *"Show me my weekly mileage trend for the past 2 months"*
- *"What gear has the most miles on it?"*

The `get_running_summary` tool is especially powerful for coaching — it computes weekly mileage, pace trends, best 5K/10K efforts, and heart rate stats, all in one call.

## Security

Credentials are loaded from environment variables only — never hardcoded. The server uses Strava's OAuth2 refresh token flow and automatically handles token renewal.

## Requirements

- Python 3.10+
- A Strava account with API access
- MCP-compatible client (Claude Desktop, Claude Code, etc.)

## License

MIT
