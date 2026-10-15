"""Detailed short-window verification and trade inspector tool.

Allows step-by-step auditing of daily strategy decisions, entries, exits,
and P&L over customizable short date ranges (e.g., last 30, 60, or 90 days).
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd
import numpy as np

from config.settings import settings
from data.fetcher import MarketDataFetcher
from data.earnings import EarningsFilter
from strategies.overnight_strategy import OvernightDriftStrategy


def audit_window(start_date: str, end_date: str, top_n: int = 2):
    print("=" * 100)
    print(f"DETAILED STRATEGY AUDIT WINDOW: {start_date} to {end_date}")
    print("=" * 100)

    fetcher = MarketDataFetcher()
    earnings_filter = EarningsFilter()

    # Buffer start_date to calculate 20 EMA and 20 Momentum properly
    buffer_start = (pd.to_datetime(start_date) - timedelta(days=60)).strftime("%Y-%m-%d")

    # Fetch data
    bench_symbol = settings.BENCHMARK_TICKER
    bench_df = fetcher.fetch_historical(bench_symbol, start_date=buffer_start, end_date=end_date)
    
    tickers = settings.ticker_list
    market_data = {}
    earnings_dates = {}
    for sym in tickers:
        df = fetcher.fetch_historical(sym, start_date=buffer_start, end_date=end_date)
        if not df.empty:
            market_data[sym] = df
            earnings_dates[sym] = earnings_filter.get_upcoming_earnings_dates(sym)

    strategy = OvernightDriftStrategy(
        regime_ema_period=settings.REGIME_EMA_PERIOD,
        momentum_period=20,
        top_n=top_n,
        use_regime_filter=True,
        use_earnings_filter=True,
    )

    # Compute regime on benchmark
    regime_series = strategy.compute_regime(bench_df)
    weights_df = strategy.generate_signals(
        market_data=market_data,
        benchmark_data=bench_df,
        earnings_dates=earnings_dates,
    )

    # Filter to requested inspection window
    common_dates = [d for d in bench_df.index if pd.to_datetime(start_date).tz_localize(d.tz) <= d <= pd.to_datetime(end_date).tz_localize(d.tz)]

    print(f"\nEvaluating {len(common_dates)} trading sessions...\n")
    print(f"{'Date':<11} | {'QQQ Close':<9} | {'20 EMA':<8} | {'Regime':<8} | {'Selected Stocks & Overnight Return':<52}")
    print("-" * 100)

    trade_records = []
    portfolio_val = 10000.0

    for i in range(len(common_dates) - 1):
        dt = common_dates[i]
        next_dt = common_dates[i + 1]

        dt_str = dt.strftime("%Y-%m-%d")
        q_close = bench_df.loc[dt, "Close"]
        q_ema = bench_df["Close"].ewm(span=settings.REGIME_EMA_PERIOD, adjust=False).mean().loc[dt]
        is_bullish = bool(regime_series.loc[dt])
        regime_str = "BULL" if is_bullish else "BEAR (CASH)"

        if not is_bullish:
            print(f"{dt_str:<11} | ${q_close:>7.2f} | ${q_ema:>7.2f} | {regime_str:<8} | SITTING IN 100% CASH (Regime Filter Off)")
            continue

        row_weights = weights_df.loc[dt]
        active_picks = row_weights[row_weights > 0].index.tolist()

        if not active_picks:
            print(f"{dt_str:<11} | ${q_close:>7.2f} | ${q_ema:>7.2f} | {regime_str:<8} | NO QUALIFIED PICKS (Blackout or Negative Momentum)")
            continue

        picks_detail = []
        nightly_ret = 0.0

        for sym in active_picks:
            entry_close = market_data[sym].loc[dt, "Close"]
            exit_open = market_data[sym].loc[next_dt, "Open"]
            ret = (exit_open - entry_close) / entry_close
            nightly_ret += ret * (1.0 / len(active_picks))
            picks_detail.append(f"{sym} (${entry_close:.1f} -> ${exit_open:.1f}: {ret * 100:+.2f}%)")

            trade_records.append({
                "Date": dt_str,
                "Ticker": sym,
                "Entry_Close": entry_close,
                "Exit_Date": next_dt.strftime("%Y-%m-%d"),
                "Exit_Open": exit_open,
                "Return_Pct": ret * 100.0,
            })

        dollar_pnl = portfolio_val * nightly_ret
        portfolio_val += dollar_pnl
        detail_str = ", ".join(picks_detail)
        print(f"{dt_str:<11} | ${q_close:>7.2f} | ${q_ema:>7.2f} | {regime_str:<8} | {detail_str}")

    # Summary table
    print("=" * 100)
    print("\nWINDOW SUMMARY METRICS:")
    if trade_records:
        tdf = pd.DataFrame(trade_records)
        wins = tdf[tdf["Return_Pct"] > 0]
        losses = tdf[tdf["Return_Pct"] < 0]
        win_rate = len(wins) / len(tdf) * 100.0
        loss_rate = len(losses) / len(tdf) * 100.0
        avg_win = wins["Return_Pct"].mean() if len(wins) > 0 else 0.0
        avg_loss = abs(losses["Return_Pct"].mean()) if len(losses) > 0 else 0.0
        
        # Expected value per trade: (win_rate * avg_win) - (loss_rate * avg_loss)
        ev_per_trade = ((win_rate / 100.0) * avg_win) - ((loss_rate / 100.0) * avg_loss)
        payoff_ratio = (avg_win / avg_loss) if avg_loss > 0 else 0.0

        print(f"Total Completed Overnight Trades : {len(tdf)}")
        print(f"Win Rate                         : {win_rate:.1f}% ({len(wins)} Wins / {len(losses)} Losses)")
        print(f"Average Win                      : {avg_win:+.2f}%")
        print(f"Average Loss                     : -{avg_loss:.2f}%")
        print(f"Payoff Ratio (Avg Win / Avg Loss): {payoff_ratio:.2f}x")
        print(f"Expected Value (EV) per Trade    : {ev_per_trade:+.3f}%")
        print(f"Largest Win                      : {tdf['Return_Pct'].max():+.2f}% ({tdf.loc[tdf['Return_Pct'].idxmax(), 'Ticker']} on {tdf.loc[tdf['Return_Pct'].idxmax(), 'Date']})")
        print(f"Largest Loss                     : {tdf['Return_Pct'].min():+.2f}% ({tdf.loc[tdf['Return_Pct'].idxmin(), 'Ticker']} on {tdf.loc[tdf['Return_Pct'].idxmin(), 'Date']})")
        print(f"Ending Portfolio Equity ($10k)   : ${portfolio_val:,.2f}")
    else:
        print("No trades triggered during this specific window.")
    print("=" * 100 + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="Audit overnight drift strategy on a specific date window.")
    parser.add_argument("--days", type=int, default=60, help="Number of recent days to inspect (default: 60)")
    parser.add_argument("--start", type=str, default=None, help="Custom start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=None, help="Custom end date (YYYY-MM-DD)")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.start and args.end:
        s_date = args.start
        e_date = args.end
    else:
        e_date = datetime.today().strftime("%Y-%m-%d")
        s_date = (datetime.today() - timedelta(days=args.days)).strftime("%Y-%m-%d")

    audit_window(start_date=s_date, end_date=e_date)
