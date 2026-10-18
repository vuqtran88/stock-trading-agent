"""Unit tests for FastAPI backend API routes."""

import pytest
from fastapi.testclient import TestClient

from backend.app import app
from config.settings import settings

client = TestClient(app)


def test_api_status_unauthorized():
    # Attempting to fetch portfolio without auth should yield 401
    resp = client.get("/api/trading/portfolio")
    assert resp.status_code == 401


def test_login_and_authenticated_flow():
    # 1. Invalid password
    resp = client.post("/api/auth/login", json={"password": "wrongpassword"})
    assert resp.status_code == 401

    # 2. Valid login
    resp = client.post("/api/auth/login", json={"password": settings.DASHBOARD_PASSWORD})
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert "token" in data

    token = data["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Check auth status
    resp = client.get("/api/auth/status", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["authenticated"] is True

    # 4. Fetch config
    resp = client.get("/api/config", headers=headers)
    assert resp.status_code == 200
    cfg = resp.json()
    assert "tickers" in cfg
    assert "AAPL" in cfg["tickers"]
    assert "active_strategy" in cfg
    assert "strategy_enabled" in cfg
    assert "available_strategies" in cfg
    assert "close_routine_time" in cfg
    assert "open_routine_time" in cfg

    # 4b. Update strategy controls and scan times
    resp = client.post(
        "/api/config",
        json={
            "strategy_enabled": False,
            "open_routine_time": "09:30",
            "close_routine_time": "15:45",
            "active_strategy": "overnight_drift",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    updated_cfg = client.get("/api/config", headers=headers).json()
    assert updated_cfg["strategy_enabled"] is False
    assert updated_cfg["open_routine_time"] == "09:30"
    assert updated_cfg["close_routine_time"] == "15:45"

    # Re-enable strategy execution for standard test environment
    client.post("/api/config", json={"strategy_enabled": True}, headers=headers)

    # 4c. Check daemon status endpoint
    resp = client.get("/api/trading/daemon-status", headers=headers)
    assert resp.status_code == 200
    assert "status" in resp.json()

    # 5. Fetch portfolio
    resp = client.get("/api/trading/portfolio", headers=headers)
    assert resp.status_code == 200
    port = resp.json()
    assert "cash" in port
    assert "positions" in port

    # 6. Manual Paper Order (Buy 1 share AAPL)
    resp = client.post(
        "/api/trading/order",
        json={"ticker": "AAPL", "shares": 1, "side": "BUY"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True
