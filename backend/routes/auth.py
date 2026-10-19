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
