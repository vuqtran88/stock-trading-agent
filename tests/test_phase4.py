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
