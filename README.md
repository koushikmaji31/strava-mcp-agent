# strava-mcp-agent

**Give Claude access to your Strava data.** An MCP server that exposes your runs, rides, swims, and all Strava metrics as tools for AI-powered coaching, analysis, and conversation.

---

## What it does

`strava-mcp-agent` connects your Strava account to any MCP-compatible client (Claude Desktop, Claude Code, etc.) and provides **13 tools** covering every aspect of your athletic data:

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

## Quick Start (2 commands)

```bash
pip install strava-mcp-agent
strava-mcp-token
```

That's it. The setup wizard will:

1. Ask for your Strava API credentials ([create an app here](https://www.strava.com/settings/api) first — set callback domain to `localhost`)
2. Open your browser for Strava authorization
3. Auto-detect your OS (macOS / Linux / Windows)
4. Find the Python that has the package installed
5. Write the Claude Desktop config for you

Just restart Claude Desktop and your 13 Strava tools are ready.

### Manual setup (if you prefer)

<details>
<summary>Click to expand</summary>

Add to your Claude Desktop config:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

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

</details>

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
