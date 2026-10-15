"""Unit tests for Phase 1 components."""

import pytest
import pandas as pd
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from config.settings import Settings
from data.fetcher import MarketDataFetcher
from data.earnings import EarningsFilter


def test_settings_properties():
    s = Settings(TICKERS="AAPL, MSFT , NVDA", BENCHMARK_TICKER="QQQ")
    assert s.ticker_list == ["AAPL", "MSFT", "NVDA"]
    assert s.all_tickers == ["QQQ", "AAPL", "MSFT", "NVDA"]


def test_market_data_fetcher_caching(tmp_path):
    fetcher = MarketDataFetcher(cache_dir=tmp_path)
    
    # Mock yf.Ticker to avoid external network in unit test
    with patch("yfinance.Ticker") as mock_ticker:
        mock_instance = MagicMock()
        mock_df = pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [102.0, 103.0],
                "Low": [99.0, 100.0],
                "Close": [101.0, 102.0],
                "Volume": [1000, 1500],
            },
            index=pd.to_datetime(["2024-01-01", "2024-01-02"]),
        )
        mock_instance.history.return_value = mock_df
        mock_ticker.return_value = mock_instance

        # First call: downloads and caches
        df1 = fetcher.fetch_historical("AAPL", start_date="2024-01-01", force_refresh=True)
        assert len(df1) == 2
        cache_file = fetcher._get_cache_filepath("AAPL", "1d")
        assert cache_file.exists()

        # Second call: reads from cache without invoking history
        mock_instance.history.reset_mock()
        df2 = fetcher.fetch_historical("AAPL", start_date="2024-01-01", force_refresh=False)
        assert len(df2) == 2
        mock_instance.history.assert_not_called()


def test_earnings_blackout_filter():
    ef = EarningsFilter(blackout_days=1)
    today = date(2026, 10, 14)
    tomorrow = today + timedelta(days=1)
    next_week = today + timedelta(days=7)

    with patch.object(ef, "get_upcoming_earnings_dates") as mock_dates:
        # Case 1: Earnings tonight or tomorrow -> Blackout triggered
        mock_dates.return_value = [tomorrow]
        assert ef.has_earnings_blackout("AAPL", target_date=today) is True

        # Case 2: Earnings next week -> No blackout
        mock_dates.return_value = [next_week]
        assert ef.has_earnings_blackout("AAPL", target_date=today) is False
