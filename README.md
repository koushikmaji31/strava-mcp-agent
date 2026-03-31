# strava-mcp-agent

**Your AI running coach that actually remembers.** An MCP server with persistent memory that connects your Strava data to Claude — tracking your zones, pace trends, injuries, and goals across sessions so coaching advice stays current.

---

## What it does

`strava-mcp-agent` gives Claude **18 tools** — 13 for live Strava data and 5 for persistent memory that carries context across every conversation.

### Memory & Context Tools

| Tool | Description |
|------|-------------|
| `get_athlete_context` | Loads your full training profile at conversation start — HR zones, current Z2 pace, weekly mileage trends, goals, injuries. Auto-refreshes if stale. |
| `update_athlete_profile` | Save your max HR, resting HR, weight, FTP, and custom HR zones |
| `update_athlete_goals` | Track race targets, training phase, and deadlines |
| `update_athlete_injuries` | Log injuries, update recovery status, mark as resolved |
| `add_training_note` | Persistent coaching notes across sessions (last 50 kept) |

### Strava Data Tools

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

### Why memory matters

Without memory, Claude forgets everything between conversations:
- Session 1: "Your Z2 pace is 9:30/km"
- Session 2: "Your Z2 pace improved to 8:10/km"
- Session 3: "I recommend running at 9:00–9:30/km" ← **wrong**, forgot the improvement

With memory, fitness metrics are auto-computed from your Strava data and persist. Claude always knows your current zones, trends, and injuries.

---

## Quick Start (2 commands)

```bash
pip install strava-mcp-agent
strava-mcp-token
```

### Step 1: Create a Strava API app (one time)

Go to [strava.com/settings/api](https://www.strava.com/settings/api) and fill in:

| Field | What to enter |
|-------|---------------|
| **Application Name** | Anything (e.g. `My Claude MCP`) |
| **Category** | Pick any |
| **Club** | Leave blank |
| **Website** | `http://localhost` |
| **Authorization Callback Domain** | `localhost` |

> The callback domain **must** be `localhost` — this is what allows the setup wizard to receive the authorization code on your machine.

Click **Create**. On the next page, copy your **Client ID** (a number like `123456`) and **Client Secret** (a long code like `abc123def456...`).

### Step 2: Run the setup wizard

```bash
strava-mcp-token
```

It will:
1. Ask for your Client ID and Client Secret
2. Open your browser — click **Authorize** on the Strava page
3. Auto-detect your OS (macOS / Linux / Windows)
4. Find the Python that has the package installed
5. Write the Claude Desktop config file for you

### Step 3: Restart Claude Desktop

Your 18 tools are ready. To get the most out of coaching, start by telling Claude your max HR and goals:

> *"Set my max HR to 190, resting HR 48, and my goal is sub-50 10K by June"*

Claude will save this and use it to compute accurate training zones from then on.

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

---

## Usage Examples

Once connected, just talk to Claude:

- *"What's my current Z2 pace and how has it changed over the last 3 months?"*
- *"My left knee is sore — adjust my training plan for this week"*
- *"Am I on track for my sub-50 10K goal?"*
- *"How was my running this month compared to last month?"*
- *"Which shoes have the most miles on them?"*

Memory is stored in `~/.strava-mcp/memory/` as plain JSON files — easy to inspect or back up.

---

## Security

Credentials are loaded from environment variables only — never hardcoded. The server uses Strava's OAuth2 refresh token flow and automatically handles token renewal.

## Requirements

- Python 3.10+
- A Strava account with API access
- Claude Desktop (or any MCP-compatible client)

## License

MIT
