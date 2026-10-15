"""Overnight Drift Strategy implementation.

Strategy Rules:
1. Entry: Buy at Market Close (Day T).
2. Exit: Sell at Market Open (Day T+1).
3. Regime Filter: Benchmark (QQQ) Close > EMA (e.g. 20 EMA).
4. Earnings Filter: Exclude stocks with earnings today or tomorrow morning.
5. Ranking / Selection: Rank eligible stocks by (20-day Momentum - Intraday Return)
   to pick strong leaders currently experiencing an intraday dip.
6. Diversification: Allocate equally among top N stocks (e.g., top 2 or 3).
"""

from datetime import date
from typing import Dict, List, Optional, Set
import numpy as np
import pandas as pd

from strategies.base import BaseStrategy


class OvernightDriftStrategy(BaseStrategy):
    """Buy-at-Close, Sell-at-Open (Overnight Drift) Strategy."""

    def __init__(
        self,
        regime_ema_period: int = 20,
        momentum_period: int = 20,
        top_n: int = 2,
        use_regime_filter: bool = True,
        use_earnings_filter: bool = True,
    ):
        self.regime_ema_period = regime_ema_period
        self.momentum_period = momentum_period
        self.top_n = top_n
        self.use_regime_filter = use_regime_filter
        self.use_earnings_filter = use_earnings_filter

    def compute_regime(self, benchmark_df: pd.DataFrame) -> pd.Series:
        """Compute regime filter: True if benchmark Close > EMA."""
        if benchmark_df.empty:
            return pd.Series(dtype=bool)

        close = benchmark_df["Close"]
        ema = close.ewm(span=self.regime_ema_period, adjust=False).mean()
        regime = close > ema
        regime.name = "regime_bullish"
        return regime

    def generate_signals(
        self,
        market_data: Dict[str, pd.DataFrame],
        benchmark_data: pd.DataFrame,
        earnings_dates: Optional[Dict[str, List]] = None,
    ) -> pd.DataFrame:
        """Generate overnight allocation weights (sums to <= 1.0) for each trading date T.

        Weight > 0 on date T means: buy at Day T Close, sell at Day T+1 Open.

        Returns:
            pd.DataFrame indexed by Date with tickers as columns, containing portfolio weights.
        """
        if not market_data or benchmark_data.empty:
            return pd.DataFrame()

        # Align on benchmark dates
        common_dates = benchmark_data.index
        tickers = sorted(list(market_data.keys()))

        # Regime indicator series
        if self.use_regime_filter:
            regime = self.compute_regime(benchmark_data)
        else:
            regime = pd.Series(True, index=common_dates)

        # Prepare matrices for ranking
        # 1. Momentum: 20-day percentage change
        momentum_dict = {}
        # 2. Intraday return: (Close - Open) / Open
        intraday_ret_dict = {}
        # 3. Available prices
        close_dict = {}

        for ticker in tickers:
            df = market_data[ticker].reindex(common_dates)
            close = df["Close"]
            open_p = df["Open"]

            close_dict[ticker] = close
            mom = close.pct_change(self.momentum_period, fill_method=None)
            momentum_dict[ticker] = mom

            # Avoid division by zero
            with np.errstate(divide="ignore", invalid="ignore"):
                intra = (close - open_p) / open_p
            intraday_ret_dict[ticker] = intra

        mom_df = pd.DataFrame(momentum_dict, index=common_dates)
        intra_df = pd.DataFrame(intraday_ret_dict, index=common_dates)
        close_matrix = pd.DataFrame(close_dict, index=common_dates)

        # Convert earnings dates to sets of dates for fast lookup
        earnings_set_dict: Dict[str, Set[date]] = {}
        if self.use_earnings_filter and earnings_dates:
            for sym, dates in earnings_dates.items():
                s = set()
                for d in dates:
                    if hasattr(d, "date"):
                        s.add(d.date())
                    elif isinstance(d, date):
                        s.add(d)
                earnings_set_dict[sym] = s

        # Composite Score = Momentum - Intraday Return
        # (High momentum stock on an intraday dip gets highest score)
        score_df = mom_df - intra_df

        weights = pd.DataFrame(0.0, index=common_dates, columns=tickers)

        for current_idx, dt in enumerate(common_dates):
            # Check regime filter
            is_bullish = regime.loc[dt] if dt in regime.index else False
            if not is_bullish:
                continue

            current_date_val = dt.date() if hasattr(dt, "date") else dt

            # Next trading date for earnings check
            next_date_val = None
            if current_idx + 1 < len(common_dates):
                next_dt = common_dates[current_idx + 1]
                next_date_val = next_dt.date() if hasattr(next_dt, "date") else next_dt

            # Collect eligible candidates and scores
            candidates = []
            for ticker in tickers:
                score = score_df.loc[dt, ticker]
                close_p = close_matrix.loc[dt, ticker]

                # Basic sanity: price valid & score not NaN
                if np.isnan(score) or np.isnan(close_p) or close_p <= 0:
                    continue

                # Momentum must be positive to be considered an uptrend leader
                if mom_df.loc[dt, ticker] <= 0:
                    continue

                # Earnings blackout check (Day T tonight or Day T+1 morning)
                if self.use_earnings_filter and ticker in earnings_set_dict:
                    ed_set = earnings_set_dict[ticker]
                    if current_date_val in ed_set or (
                        next_date_val and next_date_val in ed_set
                    ):
                        continue

                candidates.append((ticker, score))

            if not candidates:
                continue

            # Sort descending by score
            candidates.sort(key=lambda x: x[1], reverse=True)
            selected = candidates[: self.top_n]

            # Assign equal weights among selected
            w = 1.0 / len(selected)
            for sym, _ in selected:
                weights.loc[dt, sym] = w

        return weights
