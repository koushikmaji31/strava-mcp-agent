#!/usr/bin/env python3
"""
Run this ONCE to authorize Strava and auto-configure Claude Desktop.
Usage:  strava-mcp-token
"""

from __future__ import annotations

import json
import os
import platform
import sys
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

import httpx


def _get_claude_config_path() -> Path:
    """Detect the Claude Desktop config path for the current OS."""
    system = platform.system()
    if system == "Darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Linux":
        # XDG_CONFIG_HOME or ~/.config
        config_home = os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))
        return Path(config_home) / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            return Path(appdata) / "Claude" / "claude_desktop_config.json"
        return Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".claude" / "claude_desktop_config.json"


def _find_python_command() -> str:
    """Return the python command that has strava_mcp installed."""
    return sys.executable


def _update_claude_config(client_id: str, client_secret: str, refresh_token: str) -> bool:
    """Write strava MCP entry into Claude Desktop config. Returns True on success."""
    config_path = _get_claude_config_path()

    # Load existing config or start fresh
    config: dict = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text())
        except (json.JSONDecodeError, OSError):
            config = {}

    if "mcpServers" not in config:
        config["mcpServers"] = {}

    python_cmd = _find_python_command()

    config["mcpServers"]["strava"] = {
        "command": python_cmd,
        "args": ["-m", "strava_mcp"],
        "env": {
            "STRAVA_CLIENT_ID": client_id,
            "STRAVA_CLIENT_SECRET": client_secret,
            "STRAVA_REFRESH_TOKEN": refresh_token,
        },
    }

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    return True


def main():
    print("\n=== Strava MCP Setup ===\n")
    print("Step 1: Go to https://www.strava.com/settings/api and create an app")
    print("        (set Authorization Callback Domain to: localhost)\n")

    CLIENT_ID = input("Enter your Strava CLIENT_ID: ").strip()
    CLIENT_SECRET = input("Enter your Strava CLIENT_SECRET: ").strip()

    if not CLIENT_ID or not CLIENT_SECRET:
        print("Client ID and Secret are required.")
        raise SystemExit(1)

    AUTH_URL = (
        "https://www.strava.com/oauth/authorize?"
        + urllib.parse.urlencode({
            "client_id": CLIENT_ID,
            "redirect_uri": "http://localhost:8888/callback",
            "response_type": "code",
            "scope": "read_all,activity:read_all,profile:read_all",
        })
    )

    code_holder = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            code_holder["code"] = qs.get("code", [""])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(
                b"<h2>Success! You can close this tab and return to your terminal.</h2>"
            )

        def log_message(self, *a):
            pass

    print("\nStep 2: Opening browser for Strava authorization...")
    webbrowser.open(AUTH_URL)

    httpd = HTTPServer(("localhost", 8888), Handler)
    httpd.handle_request()

    code = code_holder.get("code", "")
    if not code:
        print("No authorization code received. Try again.")
        raise SystemExit(1)

    resp = httpx.post("https://www.strava.com/oauth/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    })

    if resp.status_code != 200:
        print(f"\nStrava returned an error: {resp.text}")
        print("Check your Client ID and Client Secret and try again.")
        raise SystemExit(1)

    data = resp.json()
    refresh_token = data["refresh_token"]
    athlete = data.get("athlete", {})
    name = athlete.get("firstname", "")

    print(f"\nAuthorized as: {name} {athlete.get('lastname', '')}")

    # Auto-configure Claude Desktop
    print("\nStep 3: Configuring Claude Desktop...")
    config_path = _get_claude_config_path()

    try:
        _update_claude_config(CLIENT_ID, CLIENT_SECRET, refresh_token)
        print(f"  Config written to: {config_path}")
        print("\n  All done! Restart Claude Desktop and your Strava tools will be ready.")
    except OSError as e:
        print(f"\n  Could not write config automatically: {e}")
        print(f"  Please add this manually to {config_path}:\n")
        snippet = {
            "mcpServers": {
                "strava": {
                    "command": _find_python_command(),
                    "args": ["-m", "strava_mcp"],
                    "env": {
                        "STRAVA_CLIENT_ID": CLIENT_ID,
                        "STRAVA_CLIENT_SECRET": CLIENT_SECRET,
                        "STRAVA_REFRESH_TOKEN": refresh_token,
                    },
                }
            }
        }
        print(json.dumps(snippet, indent=2))

    print()


if __name__ == "__main__":
    main()
