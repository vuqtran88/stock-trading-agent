"""Charles Schwab OAuth2 Authentication & Token Manager.

Handles initial browser authorization code flow, automatic token refresh,
and secure local token caching.
"""

import json
import base64
import logging
import time
import webbrowser
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, Optional
import requests

from config.settings import settings

logger = logging.getLogger(__name__)

SCHWAB_AUTH_URL = "https://api.schwabapi.com/v1/oauth/authorize"
SCHWAB_TOKEN_URL = "https://api.schwabapi.com/v1/oauth/token"


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
        """Load stored tokens from disk if present."""
        if self.token_file.exists():
            try:
                with open(self.token_file, "r") as f:
                    self.tokens = json.load(f)
            except Exception as e:
                logger.warning(f"Error reading token file: {e}")

    def _save_tokens(self, token_data: Dict):
        """Save tokens with calculated expiration timestamp."""
        # Schwab access token typically expires in 1800 seconds (30 mins)
        expires_in = token_data.get("expires_in", 1800)
        token_data["expires_at"] = time.time() + expires_in - 60  # 60s safety buffer

        # Preserve existing refresh token if not in response
        if "refresh_token" not in token_data and self.tokens and "refresh_token" in self.tokens:
            token_data["refresh_token"] = self.tokens["refresh_token"]

        self.tokens = token_data
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)
        logger.info(f"Schwab tokens cached at {self.token_file}")

    def _get_basic_auth_header(self) -> Dict[str, str]:
        """Schwab requires Basic Auth encoding of AppKey:AppSecret."""
        credentials = f"{self.app_key}:{self.app_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def exchange_code_for_tokens(self, auth_code_or_url: str) -> Dict:
        """Exchange an authorization code or full redirect URL for tokens."""
        code = auth_code_or_url.strip()
        if "code=" in code:
            parsed = urllib.parse.urlparse(code)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                code = params["code"][0]

        # Decode URL encoding if needed (e.g. %40 -> @)
        code = urllib.parse.unquote(code)

        headers = self._get_basic_auth_header()
        payload = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.callback_url,
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

        print(f"Attempting to catch redirect at {self.callback_url}...")
        try:
            _OAuthCallbackHandler.auth_code = None
            server = HTTPServer(("127.0.0.1", listen_port), _OAuthCallbackHandler)
            server.timeout = 10
            # Wait up to 60 seconds
            start_t = time.time()
            while _OAuthCallbackHandler.auth_code is None and (time.time() - start_t) < 60:
                server.handle_request()
            server.server_close()
            if _OAuthCallbackHandler.auth_code:
                return self.exchange_code_for_tokens(_OAuthCallbackHandler.auth_code)
        except Exception as e:
            logger.debug(f"Local server listener failed or timed out: {e}")

        # Fallback to manual paste prompt
        print("\nIf your browser redirected to 'This site can't be reached' or 127.0.0.1:")
        print("Please COPY the entire redirected URL from your browser address bar and paste it below.")
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
