"""Authentication routes and JWT verification helpers."""

import time
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, Response
from jose import jwt, JWTError

from config.settings import settings
from backend.models import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "trade_session"


def create_access_token(data: dict, expires_in_seconds: int = 86400) -> str:
    """Generate JWT signed token."""
    to_encode = data.copy()
    to_encode.update({"exp": time.time() + expires_in_seconds})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> bool:
    """Check if token is valid and not expired."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload.get("sub") == "admin"
    except JWTError:
        return False


def get_current_user(request: Request) -> str:
    """Dependency to enforce authenticated access via cookie, Bearer header, or X-Cron-Key."""
    # 1. Check for Cloud Scheduler Cron API Key (via X-Cron-Key or Bearer)
    cron_header = request.headers.get("X-Cron-Key")
    if cron_header and settings.CRON_API_KEY and cron_header == settings.CRON_API_KEY:
        return "cron-scheduler"

    # 2. Check for cookie or Bearer token
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            if settings.CRON_API_KEY and token == settings.CRON_API_KEY:
                return "cron-scheduler"

    if not token or not verify_token(token):
        raise HTTPException(status_code=401, detail="Unauthorized access. Please log in.")
    return "admin"


@router.post("/login", response_model=LoginResponse)
def login(req: LoginRequest, response: Response):
    """Verify master password and set secure HTTP-only session cookie."""
    if req.password != settings.DASHBOARD_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect dashboard password.")

    token = create_access_token({"sub": "admin"})
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax",
    )
    return LoginResponse(success=True, message="Authenticated successfully", token=token)


@router.post("/logout")
def logout(response: Response):
    """Clear session cookie."""
    response.delete_cookie(key=COOKIE_NAME)
    return {"success": True, "message": "Logged out"}


@router.get("/status")
def auth_status(request: Request):
    """Check if user has an active valid session."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

    is_valid = bool(token and verify_token(token))
    return {"authenticated": is_valid}


@router.get("/schwab/login")
def schwab_oauth_login(request: Request):
    """Initiates Schwab OAuth2 flow directly from web dashboard."""
    import urllib.parse
    from execution.schwab_auth import SchwabAuth, SCHWAB_AUTH_URL

    auth = SchwabAuth()
    if not auth.app_key:
        raise HTTPException(status_code=400, detail="SCHWAB_APP_KEY is not configured.")

    # Determine public callback URL based on the request host
    base_url = str(request.base_url).rstrip("/")
    # Force https on cloud platforms if behind proxy
    if "run.app" in base_url and base_url.startswith("http://"):
        base_url = "https://" + base_url[7:]
    callback_url = f"{base_url}/api/auth/schwab/callback"

    params = {
        "client_id": auth.app_key,
        "redirect_uri": callback_url,
    }
    target_url = f"{SCHWAB_AUTH_URL}?{urllib.parse.urlencode(params)}"
    return {
        "auth_url": target_url,
        "callback_url": callback_url,
    }


@router.get("/schwab/callback")
def schwab_oauth_callback(code: Optional[str] = None, request: Request = None):
    """Receives redirected authorization code from Charles Schwab and syncs tokens."""
    from fastapi.responses import HTMLResponse
    from execution.schwab_auth import SchwabAuth

    if not code:
        return HTMLResponse(
            content="""
            <html>
              <head><title>Authentication Failed</title></head>
              <body style="font-family: system-ui, sans-serif; background: #090d16; color: #f87171; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;">
                <div style="background:#131b2e; padding:32px; border-radius:16px; border:1px solid #334155; text-align:center; max-width:480px;">
                  <h2 style="margin-top:0;">Authentication Failed</h2>
                  <p style="color:#94a3b8;">No authorization code received from Charles Schwab.</p>
                  <button onclick="window.close()" style="background:#ef4444; color:white; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-weight:bold;">Close Window</button>
                </div>
              </body>
            </html>
            """,
            status_code=400,
        )

    try:
        base_url = str(request.base_url).rstrip("/")
        if "run.app" in base_url and base_url.startswith("http://"):
            base_url = "https://" + base_url[7:]
        callback_url = f"{base_url}/api/auth/schwab/callback"

        auth = SchwabAuth()
        tokens = auth.exchange_code_for_tokens(code, redirect_uri=callback_url)
        # Note: auth._save_tokens automatically called auth.sync_to_secret_manager()

        return HTMLResponse(
            content="""
            <!DOCTYPE html>
            <html>
              <head>
                <title>Schwab Authorization Successful</title>
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <style>
                  body {
                    margin: 0;
                    padding: 0;
                    background: #020617;
                    color: #f8fafc;
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    min-height: 100vh;
                  }
                  .card {
                    background: #0f172a;
                    border: 1px solid #1e293b;
                    box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.5);
                    border-radius: 20px;
                    padding: 36px;
                    max-width: 440px;
                    text-align: center;
                  }
                  .badge {
                    width: 54px;
                    height: 54px;
                    background: rgba(16, 185, 129, 0.15);
                    border: 1px solid rgba(16, 185, 129, 0.4);
                    color: #34d399;
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    border-radius: 16px;
                    font-size: 26px;
                    margin-bottom: 20px;
                  }
                  h2 { margin: 0 0 10px 0; font-size: 20px; font-weight: 700; color: #ffffff; }
                  p { color: #94a3b8; font-size: 13px; line-height: 1.6; margin: 0 0 24px 0; }
                  .btn {
                    background: #0d9488;
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 12px;
                    font-size: 13px;
                    font-weight: 600;
                    cursor: pointer;
                    width: 100%;
                    transition: background 0.2s;
                  }
                  .btn:hover { background: #14b8a6; }
                </style>
              </head>
              <body>
                <div class="card">
                  <div class="badge">✓</div>
                  <h2>Charles Schwab Connected!</h2>
                  <p>Your OAuth refresh token has been renewed for 7 days and synchronized automatically to GCP Secret Manager.</p>
                  <button class="btn" onclick="if(window.opener){window.opener.location.reload(); window.close();} else {window.location.href='/';}">Return to Dashboard</button>
                </div>
                <script>
                  setTimeout(() => {
                    if (window.opener) {
                      try { window.opener.location.reload(); } catch(e){}
                      window.close();
                    }
                  }, 2500);
                </script>
              </body>
            </html>
            """,
            status_code=200,
        )
    except Exception as e:
        return HTMLResponse(
            content=f"""
            <html>
              <head><title>Authorization Failed</title></head>
              <body style="font-family: system-ui, sans-serif; background: #090d16; color: #f87171; display:flex; align-items:center; justify-content:center; height:100vh; margin:0;">
                <div style="background:#131b2e; padding:32px; border-radius:16px; border:1px solid #334155; text-align:center; max-width:480px;">
                  <h2 style="margin-top:0;">Failed to Exchange Code</h2>
                  <p style="color:#94a3b8; font-size:13px;">{e}</p>
                  <button onclick="window.close()" style="background:#ef4444; color:white; border:none; padding:10px 20px; border-radius:8px; cursor:pointer; font-weight:bold;">Close</button>
                </div>
              </body>
            </html>
            """,
            status_code=500,
        )

