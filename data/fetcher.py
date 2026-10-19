"""Market data fetching and caching module."""

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd
import yfinance as yf

from config.settings import settings

logger = logging.getLogger(__name__)


class MarketDataFetcher:
    """Fetches and caches historical and current market data using yfinance."""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or settings.DATA_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_filepath(self, ticker: str, interval: str) -> Path:
        """Returns path for local Parquet cache."""
        clean_ticker = ticker.upper().replace("/", "_")
        return self.cache_dir / f"{clean_ticker}_{interval}.parquet"

    def fetch_historical(
        self,
        ticker: str,
        start_date: str = "2018-01-01",
        end_date: Optional[str] = None,
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data with Parquet caching.

        Args:
            ticker: Stock symbol (e.g. 'AAPL')
            start_date: ISO date string 'YYYY-MM-DD'
            end_date: ISO date string 'YYYY-MM-DD' (defaults to today)
            interval: Bar size ('1d', '1h', etc.)
            force_refresh: If True, bypass cache and re-download

        Returns:
            pd.DataFrame with standard OHLCV columns indexed by Datetime
        """
        cache_file = self._get_cache_filepath(ticker, interval)

        if not force_refresh and cache_file.exists():
            try:
                df = pd.read_parquet(cache_file)
                if not df.empty:
                    # Check if cache starts on or before requested start_date
                    req_start = pd.to_datetime(start_date).tz_localize(None)
                    df_start = pd.to_datetime(df.index[0]).tz_localize(None)
                    if df_start <= req_start:
                        # Slice to requested date range
                        filtered = df.copy()
                        idx_naive = pd.to_datetime(filtered.index).tz_localize(None)
                        mask = idx_naive >= req_start
                        if end_date:
                            req_end = pd.to_datetime(end_date).tz_localize(None)
                            mask = mask & (idx_naive <= req_end)
                        filtered = filtered.loc[mask]
                        logger.debug(f"Loaded {ticker} ({interval}) from cache: {len(filtered)} rows.")
                        return filtered
            except Exception as e:
                logger.warning(f"Error reading cache for {ticker}: {e}. Re-downloading...")

        logger.info(f"Downloading {ticker} historical data ({start_date} to {end_date or 'latest'})...")
        ticker_obj = yf.Ticker(ticker)
        df = ticker_obj.history(start=start_date, end=end_date, interval=interval, auto_adjust=False)

        if df.empty:
            logger.warning(f"No data returned for ticker {ticker}.")
            return pd.DataFrame()

        # Clean up column multi-indexing if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Ensure index is timezone-aware or standardized UTC/naive
        if df.index.tz is not None:
            df.index = df.index.tz_convert("America/New_York")

        # Save to parquet
        try:
            df.to_parquet(cache_file)
            logger.debug(f"Cached {len(df)} rows for {ticker} at {cache_file}.")
        except Exception as e:
            logger.warning(f"Failed to cache data for {ticker}: {e}")

        return df

    def fetch_universe_historical(
        self,
        tickers: Optional[List[str]] = None,
        start_date: str = "2018-01-01",
        end_date: Optional[str] = None,
        interval: str = "1d",
        force_refresh: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """Fetch historical data for a list of symbols."""
        symbols = tickers or settings.all_tickers
        results = {}
        for sym in symbols:
            df = self.fetch_historical(
                ticker=sym,
                start_date=start_date,
                end_date=end_date,
                interval=interval,
                force_refresh=force_refresh,
            )
            if not df.empty:
                results[sym] = df
        return results

    def get_latest_quote(self, ticker: str) -> Dict[str, float]:
        """Fetch real-time snapshot / fast quote for a given ticker."""
        t = yf.Ticker(ticker)
        fast_info = getattr(t, "fast_info", None)
        if fast_info:
            last_p = fast_info.get("lastPrice") or fast_info.get("last_price") or 0.0
            open_p = fast_info.get("open") or 0.0
            prev_close = fast_info.get("previousClose") or fast_info.get("previous_close") or 0.0
            high_p = fast_info.get("dayHigh") or fast_info.get("day_high") or 0.0
            low_p = fast_info.get("dayLow") or fast_info.get("day_low") or 0.0
            return {
                "last_price": float(last_p),
                "open": float(open_p),
                "previous_close": float(prev_close),
                "regular_market_day_high": float(high_p),
                "regular_market_day_low": float(low_p),
            }

        # Fallback to 1-day 1-minute history
        hist = t.history(period="1d", interval="1m")
        if not hist.empty:
            latest = hist.iloc[-1]
            return {
                "last_price": float(latest["Close"]),
                "open": float(hist.iloc[0]["Open"]),
                "previous_close": float(hist.iloc[0]["Open"]),
                "regular_market_day_high": float(hist["High"].max()),
                "regular_market_day_low": float(hist["Low"].min()),
            }

        return {"last_price": 0.0, "open": 0.0, "previous_close": 0.0}
