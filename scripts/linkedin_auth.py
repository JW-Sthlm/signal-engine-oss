"""
linkedin_auth.py: one-time OAuth helper to get a LinkedIn access token.

Opens your browser, you sign in to LinkedIn, the script captures the redirect on
localhost, exchanges the code for an access token, fetches your author URN, and
writes both to your .env file.

Run this ONCE per 60 days (LinkedIn tokens expire). You'll know it's time when
linkedin_post.py starts returning 401 errors.

Setup before running:
  1. Create a LinkedIn Developer App at https://www.linkedin.com/developers/apps
  2. Under "Auth", add this redirect URL: http://localhost:8765/callback
  3. Under "Products", request "Sign In with LinkedIn using OpenID Connect"
     and "Share on LinkedIn". Approval is usually instant.
  4. From the "Auth" tab, copy the Client ID and Client Secret into your .env:
       LINKEDIN_CLIENT_ID=...
       LINKEDIN_CLIENT_SECRET=...
  5. Run: python scripts/linkedin_auth.py
  6. Follow the browser prompts.
  7. The script writes LINKEDIN_ACCESS_TOKEN and LINKEDIN_AUTHOR_URN to .env.

Usage:
    python scripts/linkedin_auth.py

Requires:
    pip install httpx
"""
from __future__ import annotations

import http.server
import os
import secrets
import socketserver
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"

REDIRECT_HOST = "localhost"
REDIRECT_PORT = 8765
REDIRECT_PATH = "/callback"
REDIRECT_URI = f"http://{REDIRECT_HOST}:{REDIRECT_PORT}{REDIRECT_PATH}"

AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

SCOPES = "openid profile email w_member_social"


def _read_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        return {}
    env: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        env[key.strip()] = value.strip()
    return env


def _write_env(updates: dict[str, str]) -> None:
    existing = _read_env()
    existing.update(updates)
    lines = [f"{k}={v}" for k, v in existing.items()]
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    captured: dict[str, str] = {}

    def do_GET(self):  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != REDIRECT_PATH:
            self.send_response(404)
            self.end_headers()
            return
        params = urllib.parse.parse_qs(parsed.query)
        for key in ("code", "state", "error", "error_description"):
            if key in params:
                _CallbackHandler.captured[key] = params[key][0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        msg = (
            "<h1>signal-engine</h1><p>OAuth complete. You can close this tab.</p>"
            if "code" in _CallbackHandler.captured
            else f"<h1>signal-engine</h1><p>OAuth failed: {_CallbackHandler.captured.get('error_description','unknown')}</p>"
        )
        self.wfile.write(msg.encode("utf-8"))

    def log_message(self, *args, **kwargs):  # silence default logging
        pass


def main() -> int:
    env = _read_env()
    client_id = os.environ.get("LINKEDIN_CLIENT_ID") or env.get("LINKEDIN_CLIENT_ID")
    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET") or env.get("LINKEDIN_CLIENT_SECRET")

    if not client_id or not client_secret:
        print(
            "ERROR: LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET must be set in .env "
            "or environment. See the docstring at the top of this file for setup.",
            file=sys.stderr,
        )
        return 2

    state = secrets.token_urlsafe(16)
    auth_query = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "scope": SCOPES,
    })
    auth_url = f"{AUTH_URL}?{auth_query}"

    print(f"[linkedin-auth] opening browser to authorize signal-engine")
    print(f"[linkedin-auth] if it doesn't open, paste this URL:\n  {auth_url}")
    webbrowser.open(auth_url)

    with socketserver.TCPServer((REDIRECT_HOST, REDIRECT_PORT), _CallbackHandler) as httpd:
        print(f"[linkedin-auth] waiting for callback on {REDIRECT_URI}")
        thread = threading.Thread(target=httpd.serve_forever)
        thread.daemon = True
        thread.start()
        try:
            while "code" not in _CallbackHandler.captured and "error" not in _CallbackHandler.captured:
                threading.Event().wait(0.5)
        finally:
            httpd.shutdown()

    if "error" in _CallbackHandler.captured:
        print(
            f"ERROR: OAuth failed: {_CallbackHandler.captured.get('error_description')}",
            file=sys.stderr,
        )
        return 1
    if _CallbackHandler.captured.get("state") != state:
        print("ERROR: state mismatch, possible CSRF. Aborting.", file=sys.stderr)
        return 1

    code = _CallbackHandler.captured["code"]
    print("[linkedin-auth] exchanging code for access token")
    r = httpx.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"ERROR: token exchange failed ({r.status_code}): {r.text}", file=sys.stderr)
        return 1
    token_data = r.json()
    access_token = token_data["access_token"]
    expires_in = token_data.get("expires_in", 0)

    print(f"[linkedin-auth] fetching user info to get author URN")
    r = httpx.get(
        USERINFO_URL,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    if r.status_code >= 400:
        print(f"ERROR: userinfo failed ({r.status_code}): {r.text}", file=sys.stderr)
        return 1
    user = r.json()
    author_urn = f"urn:li:person:{user['sub']}"

    _write_env({
        "LINKEDIN_CLIENT_ID": client_id,
        "LINKEDIN_CLIENT_SECRET": client_secret,
        "LINKEDIN_ACCESS_TOKEN": access_token,
        "LINKEDIN_AUTHOR_URN": author_urn,
    })

    days = expires_in // 86400 if expires_in else "unknown"
    print(f"[linkedin-auth] DONE. Token saved to .env, expires in {days} days.")
    print(f"[linkedin-auth] author URN: {author_urn}")
    print("[linkedin-auth] you can now run: python scripts/linkedin_post.py --post ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
