"""Unit tests for Phase 2 backtesting components."""

import pytest
import pandas as pd
import numpy as np

from backtesting.metrics import PerformanceMetrics
from backtesting.engine import BacktestEngine
from strategies.overnight_strategy import OvernightDriftStrategy


def test_performance_metrics_cagr_and_drawdown():
    # Synthetic equity curve: 100 -> 120 -> 90 -> 150
    equity = pd.Series([100.0, 120.0, 90.0, 150.0], index=pd.date_range("2024-01-01", periods=4))
    
    # Max drawdown should be from 120 to 90 = -30 / 120 = -25%
    max_dd = PerformanceMetrics.calculate_max_drawdown(equity)
    assert pytest.approx(max_dd, rel=1e-3) == -0.25

    # Win rate
    returns = pd.Series([0.05, -0.02, 0.03, 0.01])
    win_rate = PerformanceMetrics.calculate_win_rate(returns)
    assert pytest.approx(win_rate, rel=1e-3) == 0.75  # 3 wins out of 4


def test_overnight_strategy_regime_filtering():
    dates = pd.date_range("2024-01-01", periods=30)
    
    # Benchmark trending down: Close strictly below EMA
    bench_prices = np.linspace(100, 70, 30)
    benchmark_df = pd.DataFrame({"Close": bench_prices, "Open": bench_prices}, index=dates)

    stock_df = pd.DataFrame(
        {"Close": np.linspace(100, 120, 30), "Open": np.linspace(99, 119, 30)},
        index=dates,
    )
    market_data = {"AAPL": stock_df}

    strategy = OvernightDriftStrategy(regime_ema_period=5, use_regime_filter=True)
    weights = strategy.generate_signals(market_data=market_data, benchmark_data=benchmark_df)

    # When benchmark is crashing, weights must be 0 (cash)
    assert (weights["AAPL"].iloc[-5:] == 0.0).all()


def test_backtest_engine_execution():
    dates = pd.date_range("2024-01-01", periods=5)
    bench_df = pd.DataFrame({"Close": [100, 102, 104, 106, 108], "Open": [99, 101, 103, 105, 107]}, index=dates)
    
    # AAPL rises overnight each night (Next Open > Current Close)
    # Day 0: Close 100, Day 1: Open 105 (+5%)
    aapl_df = pd.DataFrame(
        {
            "Close": [100.0, 104.0, 108.0, 112.0, 116.0],
            "Open": [98.0, 102.0, 106.0, 110.0, 114.0],
        },
        index=dates,
    )
    market_data = {"AAPL": aapl_df}

    strategy = OvernightDriftStrategy(regime_ema_period=2, top_n=1, use_regime_filter=False, use_earnings_filter=False)
    engine = BacktestEngine(initial_capital=10000.0, slippage_bps=0.0)

    res = engine.run(strategy=strategy, market_data=market_data, benchmark_data=bench_df)
    assert len(res["equity_curve"]) == 5
    assert res["equity_curve"].iloc[0] == 10000.0
