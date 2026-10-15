"""Backtest execution script with comparative reporting and chart generation."""

import sys
from pathlib import Path

# Ensure root dir in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import logging
import matplotlib.pyplot as plt
import pandas as pd

from config.settings import settings
from data.fetcher import MarketDataFetcher
from data.earnings import EarningsFilter
from strategies.overnight_strategy import OvernightDriftStrategy
from backtesting.engine import BacktestEngine
from backtesting.metrics import PerformanceMetrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RunBacktest")


def plot_results(
    strategy_res: dict,
    unfiltered_res: dict,
    benchmark_equity: pd.Series,
    output_path: Path,
):
    """Generate high-resolution comparison chart."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 9), sharex=True, gridspec_kw={"height_ratios": [2.5, 1.2]})

    # Top Plot: Equity Curves
    ax1.plot(
        strategy_res["equity_curve"].index,
        strategy_res["equity_curve"],
        label=f"Overnight Strategy (Regime + Earnings Filter)",
        color="#00C805",
        linewidth=2.0,
    )
    ax1.plot(
        unfiltered_res["equity_curve"].index,
        unfiltered_res["equity_curve"],
        label="Raw Overnight (No Filters)",
        color="#FFA500",
        linestyle="--",
        linewidth=1.4,
    )
    ax1.plot(
        benchmark_equity.index,
        benchmark_equity,
        label=f"Benchmark ({settings.BENCHMARK_TICKER}) Buy-and-Hold",
        color="#3498DB",
        alpha=0.8,
        linewidth=1.4,
    )

    ax1.set_title("Overnight Drift Strategy Backtest (2018 - Present)", fontsize=14, fontweight="bold")
    ax1.set_ylabel("Portfolio Value ($)", fontsize=11)
    ax1.grid(True, linestyle=":", alpha=0.6)
    ax1.legend(loc="upper left", frameon=True)

    # Bottom Plot: Drawdown Underwater Charts
    strat_dd = PerformanceMetrics.calculate_drawdown_series(strategy_res["equity_curve"]) * 100.0
    bench_dd = PerformanceMetrics.calculate_drawdown_series(benchmark_equity) * 100.0

    ax2.plot(strat_dd.index, strat_dd, label="Strategy Drawdown", color="#00C805", linewidth=1.5)
    ax2.plot(bench_dd.index, bench_dd, label="Benchmark Drawdown", color="#E74C3C", linewidth=1.2, alpha=0.7)
    ax2.fill_between(strat_dd.index, strat_dd, 0, color="#00C805", alpha=0.15)
    ax2.fill_between(bench_dd.index, bench_dd, 0, color="#E74C3C", alpha=0.08)

    ax2.set_ylabel("Drawdown (%)", fontsize=11)
    ax2.set_xlabel("Date", fontsize=11)
    ax2.grid(True, linestyle=":", alpha=0.6)
    ax2.legend(loc="lower left", frameon=True)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=300)
    plt.close()
    logger.info(f"Chart saved to {output_path}")


def main():
    logger.info("=" * 65)
    logger.info("STARTING OVERNIGHT DRIFT HISTORICAL BACKTEST (2018 - PRESENT)")
    logger.info("=" * 65)

    fetcher = MarketDataFetcher()
    earnings_filter = EarningsFilter()

    # 1. Fetch historical data for basket and benchmark
    tickers = settings.ticker_list
    bench_symbol = settings.BENCHMARK_TICKER

    logger.info(f"Fetching historical data for benchmark: {bench_symbol}...")
    bench_df = fetcher.fetch_historical(bench_symbol, start_date="2018-01-01")

    logger.info(f"Fetching historical data for {len(tickers)} basket stocks: {tickers}...")
    market_data = {}
    earnings_dates = {}

    for sym in tickers:
        df = fetcher.fetch_historical(sym, start_date="2018-01-01")
        if not df.empty:
            market_data[sym] = df
            ed = earnings_filter.get_upcoming_earnings_dates(sym)
            earnings_dates[sym] = ed

    logger.info(f"Successfully loaded data for {len(market_data)} symbols.")

    # 2. Run Strategy 1: Regime-Filtered + Earnings Filter (Our Core Strategy)
    logger.info("\nRunning Backtest: Filtered Overnight Drift (Regime EMA=20 + Earnings Blackout)...")
    core_strategy = OvernightDriftStrategy(
        regime_ema_period=settings.REGIME_EMA_PERIOD,
        momentum_period=20,
        top_n=2,
        use_regime_filter=True,
        use_earnings_filter=True,
    )
    engine = BacktestEngine(initial_capital=10000.0, slippage_bps=3.0)
    filtered_results = engine.run(
        strategy=core_strategy,
        market_data=market_data,
        benchmark_data=bench_df,
        earnings_dates=earnings_dates,
    )

    # 3. Run Strategy 2: Raw Overnight Drift (No Filters) for Comparison
    logger.info("Running Backtest: Raw Overnight Drift (No Filters)...")
    raw_strategy = OvernightDriftStrategy(
        regime_ema_period=settings.REGIME_EMA_PERIOD,
        momentum_period=20,
        top_n=2,
        use_regime_filter=False,
        use_earnings_filter=False,
    )
    raw_results = engine.run(
        strategy=raw_strategy,
        market_data=market_data,
        benchmark_data=bench_df,
        earnings_dates=earnings_dates,
    )

    # 4. Display Results Table
    m_filt = filtered_results["metrics"]
    m_raw = raw_results["metrics"]

    print("\n" + "=" * 78)
    print(f"{'Performance Metric':<32} | {'Filtered Strategy':<18} | {'Raw Strategy':<18}")
    print("-" * 78)
    print(f"{'Total Return (%)':<32} | {m_filt['Total Return (%)']:>16.2f}% | {m_raw['Total Return (%)']:>16.2f}%")
    print(f"{'CAGR (Annual Return)':<32} | {m_filt['CAGR (%)']:>16.2f}% | {m_raw['CAGR (%)']:>16.2f}%")
    print(f"{'Max Drawdown (%)':<32} | {m_filt['Max Drawdown (%)']:>16.2f}% | {m_raw['Max Drawdown (%)']:>16.2f}%")
    print(f"{'Sharpe Ratio':<32} | {m_filt['Sharpe Ratio']:>16.2f}  | {m_raw['Sharpe Ratio']:>16.2f} ")
    print(f"{'Sortino Ratio':<32} | {m_filt['Sortino Ratio']:>16.2f}  | {m_raw['Sortino Ratio']:>16.2f} ")
    print(f"{'Win Rate (%)':<32} | {m_filt['Win Rate (%)']:>16.2f}% | {m_raw['Win Rate (%)']:>16.2f}%")
    print(f"{'Profit Factor':<32} | {m_filt['Profit Factor']:>16.2f}  | {m_raw['Profit Factor']:>16.2f} ")
    print(f"{'Expected Value per Trade':<32} | {m_filt.get('Expected Value per Trade (%)', 0.0):>15.3f}% | {m_raw.get('Expected Value per Trade (%)', 0.0):>15.3f}%")
    print(f"{'Active Days Held':<32} | {m_filt['Total Active Trading Days']:>16d}  | {m_raw['Total Active Trading Days']:>16d} ")
    print("-" * 78)
    print(f"{'Benchmark (QQQ) Total Return':<32} | {m_filt.get('Benchmark Total Return (%)', 0.0):>16.2f}% |")
    print(f"{'Benchmark (QQQ) Max Drawdown':<32} | {m_filt.get('Benchmark Max Drawdown (%)', 0.0):>16.2f}% |")
    print(f"{'Benchmark (QQQ) Sharpe':<32} | {m_filt.get('Benchmark Sharpe', 0.0):>16.2f}  |")
    print("=" * 78 + "\n")

    # 5. Plot and save chart
    chart_file = ROOT_DIR / "output" / "backtest_performance.png"
    plot_results(
        strategy_res=filtered_results,
        unfiltered_res=raw_results,
        benchmark_equity=filtered_results["benchmark_equity"],
        output_path=chart_file,
    )


if __name__ == "__main__":
    main()
