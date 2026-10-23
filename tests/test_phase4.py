"""Unit tests for Phase 4 Schwab Broker, OAuth Token flow, and Discord Notifier."""

import pytest
import time
from unittest.mock import patch, MagicMock

from execution.schwab_auth import SchwabAuth
from execution.schwab_broker import SchwabBroker
from notifications.notifier import DiscordNotifier


def test_discord_notifier_payload():
    notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/123/abc")
    assert notifier.is_configured()

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_post.return_value = mock_resp

        # Buy Notification
        notifier.notify_buy_orders(
            orders=[{"ticker": "AAPL", "shares": 1, "fill_price": 200.0, "total_value": 200.0}],
            regime_info="QQQ Bullish",
            total_cost=200.0,
            env="live",
        )
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert "embeds" in call_kwargs["json"]
        assert "Buy Routine" in call_kwargs["json"]["embeds"][0]["title"]


def test_schwab_auth_token_refresh(tmp_path):
    token_file = tmp_path / "schwab_token.json"
    auth = SchwabAuth(
        app_key="TEST_KEY",
        app_secret="TEST_SECRET",
        callback_url="https://127.0.0.1:8080",
        token_path=token_file,
    )

    # Pre-populate token that has expired
    auth._save_tokens({
        "access_token": "OLD_ACCESS_TOKEN",
        "refresh_token": "VALID_REFRESH_TOKEN",
        "expires_in": -100,  # Expired
    })

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "NEW_ACCESS_TOKEN",
            "expires_in": 1800,
        }
        mock_post.return_value = mock_resp

        # get_access_token should detect expiration and refresh automatically
        token = auth.get_access_token()
        assert token == "NEW_ACCESS_TOKEN"
        assert mock_post.called


def test_schwab_broker_order_construction():
    mock_auth = MagicMock()
    mock_auth.get_access_token.return_value = "VALID_TOKEN"

    broker = SchwabBroker(auth=mock_auth, account_hash="TEST_ACCOUNT_HASH")

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.headers = {"Location": "https://api.schwabapi.com/trader/v1/accounts/123/orders/999888"}
        mock_post.return_value = mock_resp

        report = broker.buy(ticker="AAPL", shares=2)
        assert report.ticker == "AAPL"
        assert report.side == "BUY"
        assert report.shares == 2
        assert report.status == "SUBMITTED"

        # Check payload
        payload = mock_post.call_args[1]["json"]
        assert payload["orderType"] == "MARKET"
        assert payload["orderLegCollection"][0]["quantity"] == 2
        assert payload["orderLegCollection"][0]["instrument"]["symbol"] == "AAPL"


def test_detect_redirect_url_from_clipboard(monkeypatch):
    from execution.schwab_auth import detect_redirect_url_from_system
    import subprocess

    sample_url = "https://127.0.0.1/?code=C0.SAMPLE_CODE%40schwab&session=xyz"
    orig_run = subprocess.run

    def mock_run(cmd, *args, **kwargs):
        if "return the clipboard" in cmd:
            res = MagicMock()
            res.stdout = sample_url
            return res
        return MagicMock(stdout="")

    monkeypatch.setattr(subprocess, "run", mock_run)
    detected = detect_redirect_url_from_system()
    assert detected == sample_url


def test_schwab_auth_sync_to_secret_manager(tmp_path):
    token_file = tmp_path / "schwab_token.json"
    auth = SchwabAuth(
        app_key="TEST_KEY",
        app_secret="TEST_SECRET",
        callback_url="https://127.0.0.1",
        token_path=token_file,
    )

    auth.tokens = {"access_token": "TOK1", "refresh_token": "REF1"}
    with patch("google.cloud.secretmanager.SecretManagerServiceClient") as mock_sm:
        mock_client = MagicMock()
        mock_sm.return_value = mock_client

        success = auth.sync_to_secret_manager()
        assert success is True
        assert mock_client.add_secret_version.called


def test_schwab_refresh_token_status_clock(tmp_path):
    token_file = tmp_path / "schwab_token.json"
    auth = SchwabAuth(
        app_key="TEST_KEY",
        app_secret="TEST_SECRET",
        callback_url="https://127.0.0.1",
        token_path=token_file,
    )

    # 1. Test token with 10 hours remaining
    import time
    now = time.time()
    ten_hours_remaining_created_at = now - (7 * 86400 - 10 * 3600)
    auth.tokens = {
        "refresh_token": "VALID_REFRESH",
        "created_at": ten_hours_remaining_created_at,
    }
    status = auth.get_refresh_token_status()
    assert status["has_token"] is True
    assert status["status"] == "CRITICAL"
    assert status["is_near_expiry"] is True
    assert 9.0 <= status["hours_remaining"] <= 11.0

    # 2. Test healthy token (6 days remaining)
    six_days_remaining_created_at = now - (1 * 86400)
    auth.tokens = {
        "refresh_token": "VALID_REFRESH",
        "created_at": six_days_remaining_created_at,
    }
    status2 = auth.get_refresh_token_status()
    assert status2["status"] == "HEALTHY"
    assert status2["is_near_expiry"] is False


def test_discord_token_expiry_warning():
    dummy_webhook = "https://" + "discord.com" + "/api/webhooks/mock_test_warning"
    notifier = DiscordNotifier(webhook_url=dummy_webhook)
    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 204
        mock_post.return_value = mock_resp

        notifier.notify_token_expiry_warning(
            status="CRITICAL",
            hours_remaining=18.5,
            days_remaining=0.77,
            env="live",
        )
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        assert "embeds" in call_kwargs["json"]
        assert "ACTION REQUIRED" in call_kwargs["json"]["embeds"][0]["title"]
        assert "@everyone" in call_kwargs["json"]["content"]


