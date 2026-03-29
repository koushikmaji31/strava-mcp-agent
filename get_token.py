#!/usr/bin/env python3
"""
Run this ONCE to get your Strava refresh token.
Usage:  python get_token.py
"""

import os, webbrowser, urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import httpx

CLIENT_ID     = input("Enter your Strava CLIENT_ID: ").strip()
CLIENT_SECRET = input("Enter your Strava CLIENT_SECRET: ").strip()

AUTH_URL = (
    "https://www.strava.com/oauth/authorize?"
    + urllib.parse.urlencode({
        "client_id":     CLIENT_ID,
        "redirect_uri":  "http://localhost:8888/callback",
        "response_type": "code",
        "scope":         "read_all,activity:read_all,profile:read_all",
    })
)

code_holder = {}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        code_holder["code"] = qs.get("code", [""])[0]
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h2>Success! You can close this tab.</h2>")
    def log_message(self, *a): pass

print(f"\nOpening browser for Strava authorization...")
webbrowser.open(AUTH_URL)

httpd = HTTPServer(("localhost", 8888), Handler)
httpd.handle_request()

code = code_holder.get("code", "")
if not code:
    print("No code received. Try again.")
    exit(1)

resp = httpx.post("https://www.strava.com/oauth/token", data={
    "client_id":     CLIENT_ID,
    "client_secret": CLIENT_SECRET,
    "code":          code,
    "grant_type":    "authorization_code",
})
data = resp.json()

print("\n✅  SUCCESS — add these to your Claude Desktop config:\n")
print(f'  "STRAVA_CLIENT_ID":     "{CLIENT_ID}"')
print(f'  "STRAVA_CLIENT_SECRET": "{CLIENT_SECRET}"')
print(f'  "STRAVA_REFRESH_TOKEN": "{data["refresh_token"]}"')
print()
