"""Afternoon Market Close Routine (3:50 PM ET).

Workflow:
1. Check Emergency Kill Switch.
2. Fetch live quote and 20 EMA for benchmark (QQQ).
3. If regime is BEAR (QQQ < 20 EMA) -> Sit 100% in cash.
4. If regime is BULL -> Scan tech basket, rank by Momentum - Dip.
5. Submit top proposals to RiskManager.
6. Submit vetted ApprovedOrders to PaperBroker.
7. Record open overnight holdings into the ledger.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, date

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import numpy as np
import pandas as pd

from config.settings import settings
from data.fetcher import MarketDataFetcher
from data.earnings import EarningsFilter
from risk.risk_manager import RiskManager, OrderProposal
from execution.paper_broker import PaperBroker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CloseRoutine")


def run_close_routine():
    logger.info("=" * 65)
    logger.info("STARTING AFTERNOON CLOSE ROUTINE (3:50 PM ET)")
    logger.info("=" * 65)

    fetcher = MarketDataFetcher()
    risk_mgr = RiskManager()
    broker = PaperBroker()

    # 1. Kill Switch Check
    if risk_mgr.is_kill_switch_active():
        logger.error("KILL SWITCH IS ACTIVE. Halting all close routine actions.")
        return

    # 2. Check Market Regime (QQQ > 20 EMA)
    bench_sym = settings.BENCHMARK_TICKER
    logger.info(f"Checking Market Regime on {bench_sym}...")
    bench_hist = fetcher.fetch_historical(bench_sym, start_date="2024-01-01", force_refresh=True)
    bench_quote = fetcher.get_latest_quote(bench_sym)

    if bench_hist.empty or bench_quote.get("last_price", 0) <= 0:
        logger.error("Failed to retrieve valid benchmark data. Aborting routine for safety.")
        return

    bench_ema20 = float(bench_hist["Close"].ewm(span=settings.REGIME_EMA_PERIOD, adjust=False).mean().iloc[-1])
    bench_current = float(bench_quote["last_price"])

    logger.info(f"{bench_sym} Current: ${bench_current:.2f} | 20 EMA: ${bench_ema20:.2f}")

    if bench_current < bench_ema20:
        logger.warning(
            f"MARKET REGIME: BEARISH ({bench_sym} ${bench_current:.2f} < 20 EMA ${bench_ema20:.2f}). "
            f"Taking 0 trades today. Account sits 100% in CASH."
        )
        return

    logger.info("MARKET REGIME: BULLISH (Confirmed Uptrend). Proceeding to rank universe...")

    # 3. Score Universe: 20-day Momentum minus Intraday Dip
    tickers = settings.ticker_list
    candidates = []

    for sym in tickers:
        df = fetcher.fetch_historical(sym, start_date="2024-01-01")
        quote = fetcher.get_latest_quote(sym)
        last_p = quote.get("last_price", 0.0)
        open_p = quote.get("open", 0.0)

        if df.empty or last_p <= 0:
            continue

        # 20-day momentum
        if len(df) < 20:
            continue
        close_20d_ago = df["Close"].iloc[-20]
        mom20 = (last_p - close_20d_ago) / close_20d_ago

        # Only consider positive momentum leaders
        if mom20 <= 0:
            continue

        # Intraday return
        intraday_ret = ((last_p - open_p) / open_p) if open_p > 0 else 0.0
        composite_score = mom20 - intraday_ret

        candidates.append({
            "ticker": sym,
            "current_price": last_p,
            "mom20": mom20,
            "intraday_ret": intraday_ret,
            "score": composite_score,
        })

    if not candidates:
        logger.info("No candidates met the positive momentum threshold today. Sitting in cash.")
        return

    # Sort descending by score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = candidates[:2]  # Default top 2

    logger.info("\nTop Ranked Candidates:")
    for c in top_candidates:
        logger.info(
            f"  {c['ticker']}: Price=${c['current_price']:.2f}, 20d Mom={c['mom20']*100:+.2f}%, "
            f"Intraday={c['intraday_ret']*100:+.2f}%, Score={c['score']:.4f}"
        )

    # 4. Formulate Order Proposals
    proposals = []
    for c in top_candidates:
        proposals.append(
            OrderProposal(
                ticker=c["ticker"],
                target_usd=settings.MAX_POSITION_SIZE_USD,
                current_price=c["current_price"],
            )
        )

    # 5. Risk Firewall Evaluation
    cash = broker.get_cash_balance()
    exposure = broker.get_portfolio_exposure()
    approved_orders, rejections = risk_mgr.evaluate_proposals(
        proposals=proposals,
        available_cash=cash,
        current_portfolio_exposure=exposure,
    )

    if rejections:
        logger.info(f"Risk Engine Rejections ({len(rejections)}): {rejections}")

    if not approved_orders:
        logger.info("Zero orders approved by Risk Manager. Sitting in cash.")
        return

    # 6. Execute Approved Orders on Paper Broker
    logger.info(f"\nSubmitting {len(approved_orders)} approved orders to Paper Broker...")
    for order in approved_orders:
        broker.buy(ticker=order.ticker, shares=order.quantity, target_price=order.estimated_price)

    # 7. Print Active Holdings
    positions = broker.get_positions()
    print("\n" + "=" * 65)
    print("OPEN OVERNIGHT PORTFOLIO POSITION LEDGER:")
    print("-" * 65)
    for sym, pos in positions.items():
        print(f"  {sym:<6} | {pos.shares:>3} shares @ ${pos.entry_price:>7.2f} | Total: ${pos.shares * pos.entry_price:,.2f}")
    print(f"Remaining Settled Cash: ${broker.get_cash_balance():,.2f}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    run_close_routine()
