"""Earnings calendar and blackout filter module."""

import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Set
import pandas as pd
import yfinance as yf

from config.settings import settings

logger = logging.getLogger(__name__)


class EarningsFilter:
    """Detects upcoming earnings events and enforces blackout windows."""

    def __init__(self, blackout_days: Optional[int] = None):
        self.blackout_days = (
            blackout_days if blackout_days is not None else settings.EARNINGS_BLACKOUT_DAYS
        )

    def get_upcoming_earnings_dates(self, ticker: str) -> List[date]:
        """Fetch list of scheduled earnings dates for a given ticker."""
        earnings_dates: Set[date] = set()
        t = yf.Ticker(ticker)

        # Method 1: Check calendar dict
        try:
            cal = t.calendar
            if isinstance(cal, dict) and "Earnings Date" in cal:
                dates_val = cal["Earnings Date"]
                if isinstance(dates_val, list):
                    for d in dates_val:
                        if isinstance(d, (datetime, pd.Timestamp)):
                            earnings_dates.add(d.date())
                        elif isinstance(d, date):
                            earnings_dates.add(d)
                elif isinstance(dates_val, (datetime, pd.Timestamp)):
                    earnings_dates.add(dates_val.date())
                elif isinstance(dates_val, date):
                    earnings_dates.add(dates_val)
        except Exception as e:
            logger.debug(f"Calendar lookup failed for {ticker}: {e}")

        # Method 2: Check get_earnings_dates dataframe
        try:
            df = t.get_earnings_dates(limit=10)
            if df is not None and not df.empty:
                for idx in df.index:
                    if isinstance(idx, (datetime, pd.Timestamp)):
                        earnings_dates.add(idx.date())
        except Exception as e:
            logger.debug(f"get_earnings_dates lookup failed for {ticker}: {e}")

        # Return sorted in ascending order
        return sorted(list(earnings_dates))

    def get_future_earnings_dates(
        self, ticker: str, ref_date: Optional[date] = None
    ) -> List[date]:
        """Fetch scheduled earnings dates strictly on or after ref_date."""
        target = ref_date or date.today()
        all_dates = self.get_upcoming_earnings_dates(ticker)
        return [d for d in all_dates if d >= target]

    def has_earnings_blackout(
        self,
        ticker: str,
        target_date: Optional[date] = None,
        days_window: Optional[int] = None,
    ) -> bool:
        """Determines if ticker has an earnings announcement within the blackout window.

        For Buy-at-Close (Day T) and Sell-at-Open (Day T+1):
        - Post-market earnings on Day T (tonight) will gap overnight.
        - Pre-market earnings on Day T+1 (tomorrow morning) will gap overnight before market open.

        A blackout window of 1 day checks if earnings fall between [target_date, target_date + days_window].

        Args:
            ticker: Stock symbol
            target_date: The date of the proposed trade entry (defaults to today's date)
            days_window: Window in days to check forward (defaults to self.blackout_days)

        Returns:
            bool: True if an earnings event falls within the blackout window, False otherwise.
        """
        ref_date = target_date or date.today()
        window = days_window if days_window is not None else self.blackout_days

        scheduled_dates = self.get_upcoming_earnings_dates(ticker)

        # Check forward window [ref_date, ref_date + window]
        start_check = ref_date
        end_check = ref_date + timedelta(days=window)

        for ed in scheduled_dates:
            if start_check <= ed <= end_check:
                logger.info(
                    f"EARNINGS BLACKOUT for {ticker}: Earnings scheduled on {ed} "
                    f"(target: {ref_date}, window: {window} days)"
                )
                return True

        return False

    def scan_universe_blackouts(
        self,
        tickers: Optional[List[str]] = None,
        target_date: Optional[date] = None,
    ) -> Dict[str, Dict]:
        """Scan entire universe and return status of each ticker.

        Returns:
            Dict mapping ticker to dict with:
                - is_blackout: bool
                - upcoming_earnings: List of dates
        """
        symbols = tickers or settings.ticker_list
        ref_date = target_date or date.today()
        report = {}

        for sym in symbols:
            upcoming = self.get_future_earnings_dates(sym, ref_date=ref_date)
            is_blackout = self.has_earnings_blackout(sym, target_date=ref_date)
            report[sym] = {
                "is_blackout": is_blackout,
                "upcoming_earnings": upcoming,
            }

        return report
