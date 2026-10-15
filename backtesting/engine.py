"""Backtesting engine for overnight trading strategies."""

from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from backtesting.metrics import PerformanceMetrics
from strategies.base import BaseStrategy


class BacktestEngine:
    """Simulates Buy-at-Close, Sell-at-Open portfolio dynamics."""

    def __init__(
        self,
        initial_capital: float = 10000.0,
        slippage_bps: float = 3.0,  # 3 basis points = 0.03%
    ):
        self.initial_capital = initial_capital
        self.slippage_rate = slippage_bps / 10000.0

    def run(
        self,
        strategy: BaseStrategy,
        market_data: Dict[str, pd.DataFrame],
        benchmark_data: pd.DataFrame,
        earnings_dates: Optional[Dict[str, List]] = None,
    ) -> Dict:
        """Run backtest simulation.

        Returns:
            Dict containing:
                - 'equity_curve': pd.Series
                - 'daily_returns': pd.Series
                - 'benchmark_equity': pd.Series
                - 'weights': pd.DataFrame
                - 'metrics': Dict
        """
        # Generate target portfolio weights for each date T
        weights_df = strategy.generate_signals(
            market_data=market_data,
            benchmark_data=benchmark_data,
            earnings_dates=earnings_dates,
        )

        common_dates = benchmark_data.index
        tickers = sorted(list(market_data.keys()))

        # Align close and open matrices
        close_matrix = pd.DataFrame(
            {t: market_data[t]["Close"].reindex(common_dates) for t in tickers}
        )
        open_matrix = pd.DataFrame(
            {t: market_data[t]["Open"].reindex(common_dates) for t in tickers}
        )

        # Overnight return matrix: Return of entering at Close(T) and exiting at Open(T+1)
        # Note: Open(T+1) is shifted backwards by 1 period so that row T contains Open(T+1)
        next_open_matrix = open_matrix.shift(-1)
        overnight_return_matrix = (next_open_matrix - close_matrix) / close_matrix

        # Deduct slippage on entry and exit (2x slippage)
        overnight_return_matrix = overnight_return_matrix - (2.0 * self.slippage_rate)

        # Portfolio return on date T: sum over all tickers of weight(T) * overnight_return(T)
        portfolio_overnight_ret = (weights_df * overnight_return_matrix).sum(axis=1)

        # Since the last date cannot exit at T+1, set return to 0.0
        if len(portfolio_overnight_ret) > 0:
            portfolio_overnight_ret.iloc[-1] = 0.0

        # Construct daily equity curve
        # Shift portfolio returns by 1 to represent realizing overnight return in the morning of T+1
        realized_daily_ret = portfolio_overnight_ret.shift(1).fillna(0.0)
        equity_curve = self.initial_capital * (1.0 + realized_daily_ret).cumprod()

        # Benchmark Buy-and-Hold curve (normalized to initial_capital)
        bench_close = benchmark_data["Close"]
        bench_equity = self.initial_capital * (bench_close / bench_close.iloc[0])

        metrics = PerformanceMetrics.compute_all_metrics(
            equity_curve=equity_curve,
            daily_returns=realized_daily_ret,
            benchmark_equity=bench_equity,
        )

        return {
            "equity_curve": equity_curve,
            "daily_returns": realized_daily_ret,
            "benchmark_equity": bench_equity,
            "weights": weights_df,
            "metrics": metrics,
        }
