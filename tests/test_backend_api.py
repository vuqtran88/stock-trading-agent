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


def test_login_and_authenticated_flow(monkeypatch):
    # Prevent unit tests from mutating production GCP Secret Manager config
    from backend.routes import config
    monkeypatch.setattr(config, "_sync_to_secret_manager", lambda overrides: None)

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


def test_schwab_web_oauth_endpoints(monkeypatch):
    from unittest.mock import MagicMock
    from execution.schwab_auth import SchwabAuth

    # 1. Test /api/auth/schwab/login
    resp = client.get("/api/auth/schwab/login")
    assert resp.status_code == 200
    data = resp.json()
    assert "auth_url" in data
    assert "api.schwabapi.com" in data["auth_url"]
    assert "callback_url" in data

    # 2. Test /api/auth/schwab/callback missing code
    resp_err = client.get("/api/auth/schwab/callback")
    assert resp_err.status_code == 400
    assert "Authentication Failed" in resp_err.text

    # 3. Test /api/auth/schwab/callback successful code exchange
    monkeypatch.setattr(
        SchwabAuth,
        "exchange_code_for_tokens",
        lambda self, code, redirect_uri=None: {"access_token": "TEST_ACC", "refresh_token": "TEST_REF"},
    )
    resp_ok = client.get("/api/auth/schwab/callback?code=MOCK_CODE")
    assert resp_ok.status_code == 200
    assert "Charles Schwab Connected!" in resp_ok.text


def test_activity_logs_and_schwab_status_endpoints(monkeypatch):
    from unittest.mock import MagicMock
    from execution.schwab_broker import SchwabBroker

    # Authenticate client
    resp = client.post("/api/auth/login", json={"password": settings.DASHBOARD_PASSWORD})
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test /api/trading/activity-logs (ensures ACTIVITY_LOG_FILE is defined and 200 OK)
    resp = client.get("/api/trading/activity-logs", headers=headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)

    # 2. Test /api/trading/schwab-status returns 200 OK without crashing
    monkeypatch.setattr(SchwabBroker, "get_cash_balance", lambda self: 2500.0)
    monkeypatch.setattr(SchwabBroker, "get_positions", lambda self: {})
    resp = client.get("/api/trading/schwab-status", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["connected"] is True
    assert resp.json()["settled_cash"] == 2500.0


def test_schwab_broker_retry_on_401(monkeypatch):
    from unittest.mock import MagicMock
    from execution.schwab_broker import SchwabBroker
    from execution.schwab_auth import SchwabAuth

    mock_auth = MagicMock(spec=SchwabAuth)
    mock_auth.tokens = {"refresh_token": "VALID_RT", "access_token": "EXPIRED_AT"}
    mock_auth.get_access_token.return_value = "EXPIRED_AT"
    mock_auth.refresh_access_token.return_value = "NEW_VALID_AT"

    broker = SchwabBroker(auth=mock_auth, account_hash="TEST_ACCOUNT_HASH")

    # Mock requests to return 401 on first call, then 200 on retry
    resp_401 = MagicMock()
    resp_401.status_code = 401
    resp_401.text = "Client not authorized"

    resp_200 = MagicMock()
    resp_200.status_code = 200
    resp_200.json.return_value = {
        "securitiesAccount": {
            "currentBalances": {"cashBalance": 1234.56}
        }
    }

    call_count = 0
    def mock_request(method, url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return resp_401
        return resp_200

    import requests
    monkeypatch.setattr(requests, "request", mock_request)

    cash = broker.get_cash_balance()
    assert cash == 1234.56
    assert call_count == 2
    assert mock_auth.refresh_access_token.called


