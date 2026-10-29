"""Unit tests for FastAPI backend API routes."""

import json
import pytest
from fastapi.testclient import TestClient

from backend.app import app
from config.settings import settings

client = TestClient(app)


def test_api_status_unauthorized():
    # Attempting to fetch portfolio without auth should yield 401
    resp = client.get("/api/trading/portfolio")
    assert resp.status_code == 401


def test_login_and_authenticated_flow(monkeypatch, tmp_path):
    # Prevent unit tests from mutating production GCP Secret Manager config
    from backend.routes import config
    test_override_file = tmp_path / "config_override.json"
    monkeypatch.setattr(config, "OVERRIDE_FILE", test_override_file)
    monkeypatch.setattr(config, "_fetch_from_secret_manager", lambda: None)
    monkeypatch.setattr(config, "_sync_to_secret_manager", lambda overrides: None)
    monkeypatch.setattr(config, "_IN_MEMORY_CACHE", (None, 0.0))

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
    assert isinstance(cfg["tickers"], list)
    assert len(cfg["tickers"]) > 0
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


def test_paper_and_live_config_isolation(monkeypatch, tmp_path):
    from backend.routes import config
    # Use temporary file for test config cache
    test_override_file = tmp_path / "config_override.json"
    monkeypatch.setattr(config, "OVERRIDE_FILE", test_override_file)
    monkeypatch.setattr(config, "_fetch_from_secret_manager", lambda: None)
    monkeypatch.setattr(config, "_sync_to_secret_manager", lambda overrides: None)

    # Authenticate client
    resp = client.post("/api/auth/login", json={"password": settings.DASHBOARD_PASSWORD})
    token = resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Update Paper settings with custom tickers and position size
    resp = client.post(
        "/api/config",
        json={
            "target_env": "paper",
            "tickers": ["SPY", "QQQ", "IWM"],
            "max_position_size_usd": 3000.0,
            "top_n": 3,
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # 2. Update Live settings with distinct tickers and position size
    resp = client.post(
        "/api/config",
        json={
            "target_env": "live",
            "tickers": ["NVDA", "AMD"],
            "max_position_size_usd": 1000.0,
            "top_n": 1,
        },
        headers=headers,
    )
    assert resp.status_code == 200

    # 3. Retrieve config and check separation
    cfg = client.get("/api/config", headers=headers).json()
    assert cfg["paper"]["tickers"] == ["SPY", "QQQ", "IWM"]
    assert cfg["paper"]["max_position_size_usd"] == 3000.0
    assert cfg["paper"]["top_n"] == 3

    assert cfg["live"]["tickers"] == ["NVDA", "AMD"]
    assert cfg["live"]["max_position_size_usd"] == 1000.0
    assert cfg["live"]["top_n"] == 1

    # 4. Toggle active env to live
    resp = client.post("/api/config", json={"env": "live"}, headers=headers)
    assert resp.status_code == 200
    cfg_live = client.get("/api/config", headers=headers).json()
    assert cfg_live["env"] == "live"
    # Active tickers should match live
    assert cfg_live["tickers"] == ["NVDA", "AMD"]
    assert cfg_live["max_position_size_usd"] == 1000.0

    # 5. Toggle active env to paper
    resp = client.post("/api/config", json={"env": "paper"}, headers=headers)
    assert resp.status_code == 200
    cfg_paper = client.get("/api/config", headers=headers).json()
    assert cfg_paper["env"] == "paper"
    # Active tickers should match paper
    assert cfg_paper["tickers"] == ["SPY", "QQQ", "IWM"]
    assert cfg_paper["max_position_size_usd"] == 3000.0


def test_schwab_web_oauth_endpoints(monkeypatch):
    from unittest.mock import MagicMock
    from execution.schwab_auth import SchwabAuth

    # Mock Schwab app key so tests run hermetically even in clean docker environments without .env
    monkeypatch.setattr(SchwabAuth, "__init__", lambda self: setattr(self, "app_key", "MOCK_APP_KEY"))

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


def test_secret_manager_precedence_over_stale_disk_cache(monkeypatch, tmp_path):
    from backend.routes import config
    test_override_file = tmp_path / "config_override.json"
    
    # Write a stale config to disk with top_n = 2
    stale_disk_data = {
        "env": "live",
        "live": {"tickers": ["NVDA"], "top_n": 2},
        "paper": {"tickers": ["NVDA"], "top_n": 2},
    }
    with open(test_override_file, "w") as f:
        json.dump(stale_disk_data, f)

    # Secret Manager has the authoritative top_n = 3
    remote_authoritative_data = {
        "env": "live",
        "live": {"tickers": ["NVDA", "AMD", "AMZN"], "top_n": 3},
        "paper": {"tickers": ["NVDA", "AMD", "AMZN"], "top_n": 3},
    }

    monkeypatch.setattr(config, "OVERRIDE_FILE", test_override_file)
    monkeypatch.setattr(config, "_fetch_from_secret_manager", lambda: remote_authoritative_data)
    monkeypatch.setattr(config, "_IN_MEMORY_CACHE", (None, 0.0))

    # _raw_load_overrides must prioritize Secret Manager over stale disk cache
    loaded = config._raw_load_overrides(force_refresh=True)
    assert loaded["live"]["top_n"] == 3
    assert loaded["paper"]["top_n"] == 3
    assert loaded["live"]["tickers"] == ["NVDA", "AMD", "AMZN"]

    # Active overrides should reflect top_n = 3
    active = config.get_active_overrides("live")
    assert active["top_n"] == 3




def test_production_write_guardrail_blocks_unmocked_secret_manager_write():
    """Verify that any unmocked SecretManager add_secret_version call is strictly blocked."""
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    with pytest.raises(RuntimeError, match="CRITICAL TEST GUARD"):
        client.add_secret_version(parent="projects/stock-trading-agent-249477/secrets/test", payload={"data": b"leak"})
