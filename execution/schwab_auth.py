"""Charles Schwab OAuth2 Authentication & Token Manager.

Handles initial browser authorization code flow, automatic token refresh,
and secure local token caching.
"""

import json
import base64
import logging
import time
import webbrowser
import subprocess
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Optional
import requests

from config.settings import settings

logger = logging.getLogger(__name__)

SCHWAB_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"


def detect_redirect_url_from_system() -> Optional[str]:
    """Inspect active macOS browsers (Chrome, Safari, Brave, Edge) and clipboard for OAuth redirect."""
    # 1. Google Chrome
    chrome_script = """
    tell application "System Events"
        if (exists process "Google Chrome") then
            tell application "Google Chrome"
                repeat with w in windows
                    repeat with t in tabs of w
                        set u to URL of t
                        if (u contains "127.0.0.1" or u contains "localhost") and u contains "code=" then
                            return u
                        end if
                    end repeat
                end repeat
            end tell
        end if
    end tell
    return ""
    """
    try:
        res = subprocess.run(["osascript", "-e", chrome_script], capture_output=True, text=True, timeout=2)
        url = res.stdout.strip()
        if url and "code=" in url:
            return url
    except Exception:
        pass

    # 2. Safari
    safari_script = """
    tell application "System Events"
        if (exists process "Safari") then
            tell application "Safari"
                repeat with w in windows
                    repeat with t in tabs of w
                        set u to URL of t
                        if (u contains "127.0.0.1" or u contains "localhost") and u contains "code=" then
                            return u
                        end if
                    end repeat
                end repeat
            end tell
        end if
    end tell
    return ""
    """
    try:
        res = subprocess.run(["osascript", "-e", safari_script], capture_output=True, text=True, timeout=2)
        url = res.stdout.strip()
        if url and "code=" in url:
            return url
    except Exception:
        pass

    # 3. Brave Browser
    brave_script = """
    tell application "System Events"
        if (exists process "Brave Browser") then
            tell application "Brave Browser"
                repeat with w in windows
                    repeat with t in tabs of w
                        set u to URL of t
                        if (u contains "127.0.0.1" or u contains "localhost") and u contains "code=" then
                            return u
                        end if
                    end repeat
                end repeat
            end tell
        end if
    end tell
    return ""
    """
    try:
        res = subprocess.run(["osascript", "-e", brave_script], capture_output=True, text=True, timeout=2)
        url = res.stdout.strip()
        if url and "code=" in url:
            return url
    except Exception:
        pass

    # 4. Microsoft Edge
    edge_script = """
    tell application "System Events"
        if (exists process "Microsoft Edge") then
            tell application "Microsoft Edge"
                repeat with w in windows
                    repeat with t in tabs of w
                        set u to URL of t
                        if (u contains "127.0.0.1" or u contains "localhost") and u contains "code=" then
                            return u
                        end if
                    end repeat
                end repeat
            end tell
        end if
    end tell
    return ""
    """
    try:
        res = subprocess.run(["osascript", "-e", edge_script], capture_output=True, text=True, timeout=2)
        url = res.stdout.strip()
        if url and "code=" in url:
            return url
    except Exception:
        pass

    # 5. macOS Clipboard
    try:
        res = subprocess.run(["osascript", "-e", "return the clipboard"], capture_output=True, text=True, timeout=1)
        clip = res.stdout.strip()
        if "code=" in clip and ("127.0.0.1" in clip or "code=C0." in clip or "schwab" in clip):
            return clip
    except Exception:
        pass

    return None


def close_browser_redirect_tabs():
    """Politely close redirect tabs in open browsers after code extraction."""
    for browser in ["Google Chrome", "Safari", "Brave Browser", "Microsoft Edge"]:
        script = f"""
        tell application "System Events"
            if (exists process "{browser}") then
                tell application "{browser}"
                    repeat with w in windows
                        repeat with t in tabs of w
                            set u to URL of t
                            if (u contains "127.0.0.1" or u contains "localhost") and u contains "code=" then
                                close t
                                return "closed"
                            end if
                        end repeat
                    end repeat
                end tell
            end if
        end tell
        return ""
        """
        try:
            subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=2)
        except Exception:
            pass


class _OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Temporary local HTTP handler to capture redirect code."""
    auth_code: Optional[str] = None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if "code" in params:
            _OAuthCallbackHandler.auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Authentication Successful!</h2><p>You can close this window now.</p></body></html>")
        else:
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<html><body><h2>Authentication Failed</h2><p>No authorization code received.</p></body></html>")

    def log_message(self, format, *args):
        # Suppress standard server logging to stdout
        pass


class SchwabAuth:
    """Manages Charles Schwab OAuth2 tokens with automatic refresh."""

    def __init__(
        self,
        app_key: Optional[str] = None,
        app_secret: Optional[str] = None,
        callback_url: Optional[str] = None,
        token_path: Optional[Path] = None,
    ):
        self.app_key = app_key or settings.SCHWAB_APP_KEY
        self.app_secret = app_secret or settings.SCHWAB_APP_SECRET
        self.callback_url = callback_url or settings.SCHWAB_CALLBACK_URL
        self.token_file = token_path or (settings.DATA_DIR / "schwab_token.json")
        self.tokens: Optional[Dict] = None
        self._load_cached_tokens()

    def _load_cached_tokens(self):
        """Load stored tokens from disk or dynamically from GCP Secret Manager API."""
        # 1. First check local disk cache
        if self.token_file.exists():
            try:
                with open(self.token_file, "r") as f:
                    self.tokens = json.load(f)
                    return
            except Exception as e:
                logger.warning(f"Error reading token file: {e}")

        # 2. In cloud environments, fetch latest token directly from GCP Secret Manager API
        try:
            from google.cloud import secretmanager
            client = secretmanager.SecretManagerServiceClient()
            secret_name = "projects/stock-trading-agent-249477/secrets/schwab-token-data/versions/latest"
            resp = client.access_secret_version(name=secret_name)
            payload = resp.payload.data.decode("utf-8")
            if payload:
                self.tokens = json.loads(payload)
                logger.info("Fetched fresh Schwab tokens directly from GCP Secret Manager API.")
                return
        except Exception as e:
            logger.debug(f"Direct Secret Manager token fetch skipped/failed: {e}")

        # 3. Fallback to SCHWAB_TOKEN_DATA environment variable
        if settings.SCHWAB_TOKEN_DATA:
            try:
                self.tokens = json.loads(settings.SCHWAB_TOKEN_DATA)
                logger.info("Loaded Schwab OAuth tokens from Secret Manager environment variable.")
            except Exception as e:
                logger.warning(f"Failed to parse SCHWAB_TOKEN_DATA JSON: {e}")

    def _save_tokens(self, token_data: Dict):
        """Save tokens with calculated expiration timestamp."""
        # Schwab access token typically expires in 1800 seconds (30 mins)
        expires_in = token_data.get("expires_in", 1800)
        token_data["expires_at"] = time.time() + expires_in - 60  # 60s safety buffer

        # Preserve existing refresh token if not in response
        if "refresh_token" not in token_data and self.tokens and "refresh_token" in self.tokens:
            token_data["refresh_token"] = self.tokens["refresh_token"]

        # Record token creation timestamp if not present (useful for 7-day refresh token lifespan tracking)
        if "created_at" not in token_data:
            token_data["created_at"] = time.time()

        self.tokens = token_data
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info(f"Schwab tokens cached at {self.token_file}")

        # Automatically synchronize token to Google Cloud Secret Manager if configured/available
        self.sync_to_secret_manager()

    def get_refresh_token_status(self) -> Dict:
        """Returns refresh token health, age, remaining lifetime (7-day maximum), and warning status."""
        if not self.tokens or not self.tokens.get("refresh_token"):
            return {
                "has_token": False,
                "status": "MISSING",
                "message": "No refresh token available",
                "hours_remaining": 0.0,
                "days_remaining": 0.0,
                "expires_at_ts": 0,
                "is_near_expiry": True,
            }

        # 1. Determine token creation time (7 days = 604,800 seconds max lifespan)
        created_at = self.tokens.get("created_at")
        if not created_at and "id_token" in self.tokens:
            try:
                parts = self.tokens["id_token"].split(".")
                if len(parts) >= 2:
                    body = parts[1] + "=" * (-len(parts[1]) % 4)
                    claims = json.loads(base64.b64decode(body))
                    created_at = float(claims.get("iat", 0))
            except Exception:
                pass

        if not created_at:
            created_at = time.time()  # Fallback

        lifespan_sec = 7 * 86400  # 7 days
        expires_at_ts = created_at + lifespan_sec
        now = time.time()
        sec_remaining = max(0.0, expires_at_ts - now)
        hours_remaining = round(sec_remaining / 3600, 1)
        days_remaining = round(sec_remaining / 86400, 2)

        # Status categorization
        if sec_remaining <= 0:
            status = "EXPIRED"
            message = "Refresh token expired. Live trading will fail until renewed."
        elif hours_remaining <= 24:
            status = "CRITICAL"
            message = f"Refresh token expires in {hours_remaining:.0f}h! Renew immediately."
        elif hours_remaining <= 48:
            status = "WARNING"
            message = f"Refresh token expires in {days_remaining:.1f} days ({hours_remaining:.0f}h)."
        else:
            status = "HEALTHY"
            message = f"Refresh token active ({days_remaining:.1f} days remaining)."

        return {
            "has_token": True,
            "created_at": created_at,
            "expires_at_ts": expires_at_ts,
            "hours_remaining": hours_remaining,
            "days_remaining": days_remaining,
            "status": status,
            "message": message,
            "is_near_expiry": hours_remaining <= 48,
        }

    def sync_to_secret_manager(self) -> bool:
        """Persist tokens directly to GCP Secret Manager (schwab-token-data)."""
        if not self.tokens:
            return False
        try:
            from google.cloud import secretmanager
            secret_name = "projects/stock-trading-agent-249477/secrets/schwab-token-data"
            client = secretmanager.SecretManagerServiceClient()
            payload_bytes = json.dumps(self.tokens, indent=2).encode("utf-8")
            client.add_secret_version(
                parent=secret_name,
                payload={"data": payload_bytes},
            )
            logger.info("Persisted updated Schwab tokens to GCP Secret Manager.")
            return True
        except Exception as e:
            logger.warning(f"Could not persist Schwab tokens to Secret Manager: {e}")
            return False

    def _get_basic_auth_header(self) -> Dict[str, str]:
        """Schwab requires Basic Auth encoding of AppKey:AppSecret."""
        credentials = f"{self.app_key}:{self.app_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def exchange_code_for_tokens(self, auth_code_or_url: str, redirect_uri: Optional[str] = None) -> Dict:
        """Exchange an authorization code or full redirect URL for tokens."""
        code = auth_code_or_url.strip()
        if "code=" in code:
            parsed = urllib.parse.urlparse(code)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                code = params["code"][0]

        # Decode URL encoding if needed (e.g. %40 -> @)
        code = urllib.parse.unquote(code)

        cb_url = redirect_uri or self.callback_url
        headers = self._get_basic_auth_header()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": cb_url,
        }

        resp = requests.post(SCHWAB_TOKEN_URL, headers=headers, data=payload, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to exchange authorization code: {resp.text}")

        token_data = resp.json()
        self._save_tokens(token_data)
        logger.info("Authentication complete! Schwab tokens stored successfully.")
        return token_data

    def login_interactive(self, port: int = 8080) -> Dict:
        """Run local browser authentication to fetch initial refresh and access token."""
        if not self.app_key or not self.app_secret:
            raise ValueError("SCHWAB_APP_KEY and SCHWAB_APP_SECRET must be configured in .env")

        auth_url = (
            f"{SCHWAB_AUTH_URL}?client_id={self.app_key}"
            f"&redirect_uri={urllib.parse.quote(self.callback_url)}"
        )

        print("\n" + "=" * 70)
        print("CHARLES SCHWAB OAUTH2 AUTHORIZATION")
        print("=" * 70)
        print("Opening your browser to log into Charles Schwab...")
        print(f"URL: {auth_url}\n")
        webbrowser.open(auth_url)

        # Parse port from callback_url if provided, else default
        parsed_cb = urllib.parse.urlparse(self.callback_url)
        listen_port = parsed_cb.port or 80

        print(f"Waiting for redirect code from browser...")
        print("(You just log in and click Approve — the code will be captured automatically!)")

        # 1. Attempt local HTTP server listener if port specified
        server = None
        try:
            _OAuthCallbackHandler.auth_code = None
            server = HTTPServer(("127.0.0.1", listen_port), _OAuthCallbackHandler)
            server.timeout = 1
        except Exception as e:
            logger.debug(f"Could not bind local listener on port {listen_port}: {e}")

        # 2. Poll for redirect in browser URL bar, clipboard, or local HTTP server (up to 120s)
        start_t = time.time()
        timeout_seconds = 120
        captured_url_or_code = None

        while (time.time() - start_t) < timeout_seconds:
            # Check local server if active
            if server:
                try:
                    server.handle_request()
                    if _OAuthCallbackHandler.auth_code:
                        captured_url_or_code = _OAuthCallbackHandler.auth_code
                        break
                except Exception:
                    pass

            # Check active browser address bar and clipboard automatically
            detected = detect_redirect_url_from_system()
            if detected:
                captured_url_or_code = detected
                print("\n⚡ Automatically captured redirect code from browser!")
                close_browser_redirect_tabs()
                break

            time.sleep(1)

        if server:
            try:
                server.server_close()
            except Exception:
                pass

        if captured_url_or_code:
            return self.exchange_code_for_tokens(captured_url_or_code)

        # Fallback to manual paste prompt if auto-detection timed out
        print("\nCould not automatically read browser redirect URL.")
        print("Please COPY the URL from your browser address bar and paste it below:")
        user_input = input("Paste redirected URL or code: ").strip()
        return self.exchange_code_for_tokens(user_input)

    def refresh_access_token(self) -> str:
        """Refresh access token using refresh_token."""
        if not self.tokens or "refresh_token" not in self.tokens:
            raise RuntimeError("No refresh token found. Please run login_interactive() first.")

        headers = self._get_basic_auth_header()
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": self.tokens["refresh_token"],
        }

        resp = requests.post(SCHWAB_TOKEN_URL, headers=headers, data=payload, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"Failed to refresh Schwab token: {resp.text}")

        token_data = resp.json()
        self._save_tokens(token_data)
        logger.info("Successfully refreshed Schwab access token.")
        return token_data["access_token"]

    def get_access_token(self) -> str:
        """Returns valid access token, auto-refreshing if expired."""
        if not self.tokens:
            raise RuntimeError("No cached Schwab tokens found. Run `python3 scripts/schwab_login.py`.")

        expires_at = self.tokens.get("expires_at", 0)
        if time.time() >= expires_at:
            logger.info("Access token expired or near expiration. Refreshing...")
            return self.refresh_access_token()

        return self.tokens["access_token"]
