"""Afternoon Market Close Routine (3:50 PM ET).

Workflow:
1. Check Emergency Kill Switch.
2. Fetch live quote and 20 EMA for benchmark (QQQ).
3. If regime is BEAR (QQQ < 20 EMA) -> Sit 100% in cash.
4. If regime is BULL -> Check earnings blackout, rank tech basket by Momentum - Dip.
5. Submit top proposals to RiskManager.
6. Submit vetted ApprovedOrders to Broker.
7. Record open overnight holdings into the ledger.
8. Generate and save structured Decision Dossier.
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
from execution.schwab_broker import SchwabBroker
from execution.dossier import DecisionDossier
from notifications.notifier import DiscordNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("CloseRoutine")


def get_broker():
    """Instantiate broker based on settings.ENV."""
    if settings.ENV == "live":
        logger.info("Operating in LIVE mode: Using SchwabBroker.")
        return SchwabBroker()
    else:
        logger.info("Operating in PAPER mode: Using PaperBroker.")
        return PaperBroker()


def run_close_routine(broker_override=None, fetcher_override=None, earnings_filter_override=None, audit_dir_override=None, trigger_source: str = "SCHEDULED"):
    """Execute Afternoon Close Buy Routine with full verbose dossier generation."""
    source_label = "⏱️ SCHEDULED (Cron)" if trigger_source.upper() == "SCHEDULED" else "👤 MANUAL (Dashboard)"
    logger.info("=" * 65)
    logger.info(f"STARTING AFTERNOON CLOSE ROUTINE (3:50 PM ET) [{source_label}]")
    logger.info("=" * 65)

    fetcher = fetcher_override or MarketDataFetcher()
    risk_mgr = RiskManager()
    broker = broker_override or get_broker()
    earnings_filter = earnings_filter_override or EarningsFilter()


    starting_cash = float(broker.get_cash_balance())

    # 0. Strategy Active & Enabled Check (from config overrides)
    override_file = ROOT_DIR / "data_cache" / "config_override.json"
    if override_file.exists():
        try:
            with open(override_file, "r") as f:
                cfg_data = json.load(f)
                if cfg_data.get("strategy_enabled") is False and not broker_override:
                    logger.warning("Automated execution is currently PAUSED by user in config settings.")
        except Exception:
            pass

    # 1. Kill Switch Check
    if risk_mgr.is_kill_switch_active():
        logger.error("KILL SWITCH IS ACTIVE. Halting all close routine actions.")
        return DecisionDossier.create_close_dossier(
            regime_status="HALTED_KILL_SWITCH",
            qqq_price=0.0,
            qqq_ema20=0.0,
            scanned_tickers=[],
            earnings_disqualified=[],
            candidate_rankings=[],
            rejected_candidates=[{"ticker": "ALL", "reason": "Kill switch engaged"}],
            risk_proposals=[],
            risk_rejections=["Kill switch engaged"],
            approved_orders=[],
            executed_orders=[],
            starting_cash=starting_cash,
            ending_cash=starting_cash,
            overnight_exposure=0.0,
            env=settings.ENV,
            custom_audit_dir=audit_dir_override,
        )

    # 2. Check Market Regime (QQQ > 20 EMA)
    bench_sym = settings.BENCHMARK_TICKER
    logger.info(f"Checking Market Regime on {bench_sym}...")
    bench_hist = fetcher.fetch_historical(bench_sym, start_date="2024-01-01", force_refresh=True)
    bench_quote = fetcher.get_latest_quote(bench_sym)

    if bench_hist.empty or bench_quote.get("last_price", 0) <= 0:
        logger.error("Failed to retrieve valid benchmark data. Aborting routine for safety.")
        return None

    bench_ema20 = float(bench_hist["Close"].ewm(span=settings.REGIME_EMA_PERIOD, adjust=False).mean().iloc[-1])
    bench_current = float(bench_quote["last_price"])
    is_bullish = bench_current >= bench_ema20
    regime_status = "BULL" if is_bullish else "BEAR"

    logger.info(f"{bench_sym} Current: ${bench_current:.2f} | 20 EMA: ${bench_ema20:.2f} [{regime_status}]")

    tickers = settings.ticker_list

    if not is_bullish:
        logger.warning(
            f"MARKET REGIME: BEARISH ({bench_sym} ${bench_current:.2f} < 20 EMA ${bench_ema20:.2f}). "
            f"Taking 0 trades today. Account sits 100% in CASH."
        )
        notifier = DiscordNotifier()
        notifier.notify_routine_status(
            routine_name="🔔 Market Close Scan Checked",
            message=f"Market Regime is **BEARISH** ({bench_sym} ${bench_current:.2f} < 20 EMA ${bench_ema20:.2f}). Sitting 100% in **CASH** ($0 deployed).",
            trigger_source=trigger_source,
            env=settings.ENV,
            details=[
                {"name": "Benchmark (QQQ)", "value": f"${bench_current:.2f} (EMA: ${bench_ema20:.2f})", "inline": True},
                {"name": "Regime Filter", "value": "❌ BEAR (Cash Protection)", "inline": True},
                {"name": "Orders Placed", "value": "0", "inline": True},
            ],
        )
        return DecisionDossier.create_close_dossier(
            regime_status="BEAR",
            qqq_price=bench_current,
            qqq_ema20=bench_ema20,
            scanned_tickers=tickers,
            earnings_disqualified=[],
            candidate_rankings=[],
            rejected_candidates=[{"ticker": t, "reason": "Market regime BEARISH (QQQ < 20 EMA)"} for t in tickers],
            risk_proposals=[],
            risk_rejections=[],
            approved_orders=[],
            executed_orders=[],
            starting_cash=starting_cash,
            ending_cash=starting_cash,
            overnight_exposure=0.0,
            env=settings.ENV,
            custom_audit_dir=audit_dir_override,
        )

    # 3. Score Universe: 20-day Momentum minus Intraday Dip + Earnings Blackout
    earnings_disqualified = []
    candidates = []
    rejected_candidates = []

    for sym in tickers:
        # Check earnings blackout tonight / tomorrow
        if earnings_filter.has_earnings_blackout(sym):
            earnings_disqualified.append(sym)
            rejected_candidates.append({"ticker": sym, "reason": "Pending earnings release tonight or tomorrow"})
            continue


        df = fetcher.fetch_historical(sym, start_date="2024-01-01")
        quote = fetcher.get_latest_quote(sym)
        last_p = quote.get("last_price", 0.0)
        open_p = quote.get("open", 0.0)

        if df.empty or last_p <= 0 or len(df) < 20:
            rejected_candidates.append({"ticker": sym, "reason": "Insufficient historical or quote data", "price": last_p})
            continue

        close_20d_ago = df["Close"].iloc[-20]
        mom20 = (last_p - close_20d_ago) / close_20d_ago

        if mom20 <= 0:
            rejected_candidates.append({"ticker": sym, "reason": f"Negative 20d momentum ({mom20*100:+.2f}%)", "price": last_p})
            continue

        intraday_ret = ((last_p - open_p) / open_p) if open_p > 0 else 0.0
        composite_score = mom20 - intraday_ret

        candidates.append({
            "ticker": sym,
            "price": last_p,
            "mom20": mom20,
            "intraday_ret": intraday_ret,
            "score": composite_score,
        })

    # Sort descending by score
    candidates.sort(key=lambda x: x["score"], reverse=True)
    top_candidates = candidates[:2]  # Default top 2

    ranked_display = []
    for rank_idx, c in enumerate(candidates, start=1):
        decision = "SELECTED (Top 2)" if rank_idx <= 2 else "EXCLUDED (Cut by Top N=2)"
        ranked_display.append({
            "rank": rank_idx,
            "ticker": c["ticker"],
            "price": c["price"],
            "mom20": c["mom20"],
            "intraday_ret": c["intraday_ret"],
            "score": c["score"],
            "decision": decision,
        })

    if not top_candidates:
        logger.info("No candidates qualified for purchase today. Sitting in cash.")
        return DecisionDossier.create_close_dossier(
            regime_status="BULL",
            qqq_price=bench_current,
            qqq_ema20=bench_ema20,
            scanned_tickers=tickers,
            earnings_disqualified=earnings_disqualified,
            candidate_rankings=[],
            rejected_candidates=rejected_candidates,
            risk_proposals=[],
            risk_rejections=[],
            approved_orders=[],
            executed_orders=[],
            starting_cash=starting_cash,
            ending_cash=starting_cash,
            overnight_exposure=0.0,
            env=settings.ENV,
            custom_audit_dir=audit_dir_override,
        )

    # 4. Formulate Order Proposals
    target_budget = (
        settings.LIVE_PILOT_BUDGET_USD
        if settings.ENV == "live"
        else settings.MAX_POSITION_SIZE_USD
    )

    proposals = [
        OrderProposal(ticker=c["ticker"], target_usd=target_budget, current_price=c["price"])
        for c in top_candidates
    ]

    proposal_dicts = [
        {"ticker": p.ticker, "target_usd": p.target_usd, "current_price": p.current_price}
        for p in proposals
    ]

    # 5. Risk Firewall Evaluation
    if hasattr(broker, "get_portfolio_exposure"):
        exposure = broker.get_portfolio_exposure()
    else:
        exposure = sum(p.shares * p.entry_price for p in broker.get_positions().values())

    approved_orders, rejections = risk_mgr.evaluate_proposals(
        proposals=proposals,
        available_cash=starting_cash,
        current_portfolio_exposure=exposure,
    )

    approved_dicts = [
        {"ticker": a.ticker, "shares": a.quantity, "estimated_price": a.estimated_price, "allocated_usd": a.allocated_usd}
        for a in approved_orders
    ]

    # 6. Execute Approved Orders
    executed_order_reports = []
    for order in approved_orders:
        report = broker.buy(ticker=order.ticker, shares=order.quantity, target_price=order.estimated_price)
        executed_order_reports.append({
            "ticker": order.ticker,
            "shares": order.quantity,
            "fill_price": order.estimated_price,
            "total_value": order.allocated_usd,
        })

    ending_cash = float(broker.get_cash_balance())
    overnight_exposure = sum(p.shares * p.entry_price for p in broker.get_positions().values())

    # Send Discord notification if enabled
    if executed_order_reports:
        notifier = DiscordNotifier()
        regime_str = f"QQQ ${bench_current:.2f} > 20 EMA ${bench_ema20:.2f} (BULL)"
        notifier.notify_buy_orders(
            orders=executed_order_reports,
            regime_info=regime_str,
            total_cost=sum(o["total_value"] for o in executed_order_reports),
            env=settings.ENV,
        )

    # 7. Generate & Persist Verbose Decision Dossier
    return DecisionDossier.create_close_dossier(
        regime_status="BULL",
        qqq_price=bench_current,
        qqq_ema20=bench_ema20,
        scanned_tickers=tickers,
        earnings_disqualified=earnings_disqualified,
        candidate_rankings=ranked_display,
        rejected_candidates=rejected_candidates,
        risk_proposals=proposal_dicts,
        risk_rejections=rejections,
        approved_orders=approved_dicts,
        executed_orders=executed_order_reports,
        starting_cash=starting_cash,
        ending_cash=ending_cash,
        overnight_exposure=overnight_exposure,
        env=settings.ENV,
        custom_audit_dir=audit_dir_override,
    )


if __name__ == "__main__":
    run_close_routine()
