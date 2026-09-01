from __future__ import annotations

import argparse
import getpass
import secrets
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import httpx

SCOPES = (
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.settings.basic",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create the Pitmark Cloud Gmail OAuth refresh token.")
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", default="")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    client_secret = args.client_secret or getpass.getpass("Google OAuth client secret: ")
    if not client_secret:
        raise SystemExit("A Google OAuth client secret is required.")

    redirect_uri = f"http://localhost:{args.port}/"
    state = secrets.token_urlsafe(24)
    result: dict[str, str] = {}
    ready = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            query = parse_qs(urlparse(self.path).query)
            if query.get("state", [""])[0] != state:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"OAuth state mismatch. Close this tab and run the script again.")
            else:
                result["code"] = query.get("code", [""])[0]
                result["error"] = query.get("error", [""])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<h2>Pitmark Gmail authorization received.</h2>"
                    b"<p>You can close this tab and return to the terminal.</p>"
                )
            ready.set()

        def log_message(self, _format, *args):
            return

    server = HTTPServer(("127.0.0.1", args.port), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    authorization_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
        {
            "client_id": args.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )
    print("Opening Google authorization in your browser...")
    print(authorization_url)
    webbrowser.open(authorization_url)
    ready.wait(timeout=300)
    server.shutdown()

    if result.get("error"):
        raise SystemExit(f"Google authorization failed: {result['error']}")
    if not result.get("code"):
        raise SystemExit("No authorization code was received within five minutes.")

    response = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": args.client_id,
            "client_secret": client_secret,
            "code": result["code"],
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        raise SystemExit(f"Token exchange failed ({response.status_code}): {response.text}")
    refresh_token = str(response.json().get("refresh_token") or "")
    if not refresh_token:
        raise SystemExit("Google did not return a refresh token. Revoke the app grant and run again.")

    print("\nAdd this secret to Render as GOOGLE_GMAIL_REFRESH_TOKEN:\n")
    print(refresh_token)
    print("\nDo not commit this token to GitHub.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
