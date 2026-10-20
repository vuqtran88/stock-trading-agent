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

from typing import Optional
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


def get_broker(active_env: Optional[str] = None):
    """Instantiate broker based on active_env or settings.ENV."""
    env = active_env or settings.ENV
    if env == "live":
        logger.info("Operating in LIVE mode: Using SchwabBroker.")
        return SchwabBroker()
    else:
        logger.info("Operating in PAPER mode: Using PaperBroker.")
        return PaperBroker()


def run_close_routine(broker_override=None, fetcher_override=None, earnings_filter_override=None, audit_dir_override=None, trigger_source: str = "SCHEDULED"):
    """Execute Afternoon Close Buy Routine with full verbose dossier generation."""
    # 0. Strategy Active & Enabled Check (from config overrides / Secret Manager)
    from backend.routes.config import get_active_overrides
    cfg_data = get_active_overrides()
    active_env = cfg_data.get("env") or settings.ENV

    source_label = "⏱️ SCHEDULED (Cron)" if trigger_source.upper() == "SCHEDULED" else "👤 MANUAL (Dashboard)"
    logger.info("=" * 65)
    logger.info(f"STARTING AFTERNOON CLOSE ROUTINE (3:50 PM ET) [{source_label}] [{active_env.upper()}]")
    logger.info("=" * 65)

    fetcher = fetcher_override or MarketDataFetcher()
    risk_mgr = RiskManager()
    broker = broker_override or get_broker(active_env=active_env)
    earnings_filter = earnings_filter_override or EarningsFilter()

    starting_cash = float(broker.get_cash_balance())

    if cfg_data.get("strategy_enabled") is False and not broker_override:
        logger.warning("Automated execution is currently PAUSED by user in config settings. Halting routine.")
        notifier = DiscordNotifier(env=active_env)
        notifier.notify_routine_status(
            routine_name="⏸️ Market Close Scan Paused",
            message="Strategy execution is currently **PAUSED** by user in config. Close routine halted — taking 0 trades.",
            trigger_source=trigger_source,
            env=active_env,
            details=[
                {"name": "Status", "value": "⏸️ PAUSED_BY_USER", "inline": True},
                {"name": "Action", "value": "Skipped (0 trades placed)", "inline": True},
            ],
        )
        return DecisionDossier.create_close_dossier(
            regime_status="PAUSED_BY_USER",
            qqq_price=0.0,
            qqq_ema20=0.0,
            scanned_tickers=[],
            earnings_disqualified=[],
            candidate_rankings=[],
            rejected_candidates=[{"ticker": "ALL", "reason": "Strategy execution paused by user"}],
            risk_proposals=[],
            risk_rejections=["Strategy execution paused by user"],
            approved_orders=[],
            executed_orders=[],
            starting_cash=starting_cash,
            ending_cash=starting_cash,
            overnight_exposure=0.0,
            env=active_env,
            custom_audit_dir=audit_dir_override,
        )


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
            env=active_env,
            custom_audit_dir=audit_dir_override,
        )

    # 2. Check Market Regime (QQQ > Configured EMA)
    bench_sym = settings.BENCHMARK_TICKER
    logger.info(f"Checking Market Regime on {bench_sym}...")
    bench_hist = fetcher.fetch_historical(bench_sym, start_date="2024-01-01", force_refresh=True)
    bench_quote = fetcher.get_latest_quote(bench_sym)

    if bench_hist.empty or bench_quote.get("last_price", 0) <= 0:
        logger.error("Failed to retrieve valid benchmark data. Aborting routine for safety.")
        return None

    ema_period = cfg_data.get("regime_ema_period", settings.REGIME_EMA_PERIOD)

    bench_ema = float(bench_hist["Close"].ewm(span=ema_period, adjust=False).mean().iloc[-1])
    bench_current = float(bench_quote["last_price"])
    is_bullish = bench_current >= bench_ema
    regime_status = "BULL" if is_bullish else "BEAR"

    logger.info(f"{bench_sym} Current: ${bench_current:.2f} | {ema_period} EMA: ${bench_ema:.2f} [{regime_status}]")

    tickers = cfg_data.get("tickers") or settings.ticker_list
    top_n = max(1, int(cfg_data.get("top_n", 2)))

    if not is_bullish:
        logger.warning(
            f"MARKET REGIME: BEARISH ({bench_sym} ${bench_current:.2f} < {ema_period} EMA ${bench_ema:.2f}). "
            f"Taking 0 trades today. Account sits 100% in CASH."
        )
        notifier = DiscordNotifier(env=active_env)
        notifier.notify_routine_status(
            routine_name="🔔 Market Close Scan Checked",
            message=f"Market Regime is **BEARISH** ({bench_sym} ${bench_current:.2f} < {ema_period} EMA ${bench_ema:.2f}). Sitting 100% in **CASH** ($0 deployed).",
            trigger_source=trigger_source,
            env=active_env,
            details=[
                {"name": "Benchmark (QQQ)", "value": f"${bench_current:.2f} ({ema_period} EMA: ${bench_ema:.2f})", "inline": True},
                {"name": "Regime Filter", "value": "❌ BEAR (Cash Protection)", "inline": True},
                {"name": "Orders Placed", "value": "0", "inline": True},
            ],
        )
        return DecisionDossier.create_close_dossier(
            regime_status="BEAR",
            qqq_price=bench_current,
            qqq_ema20=bench_ema,
            scanned_tickers=tickers,
            earnings_disqualified=[],
            candidate_rankings=[],
            rejected_candidates=[{"ticker": t, "reason": f"Market regime BEARISH (QQQ < {ema_period} EMA)"} for t in tickers],
            risk_proposals=[],
            risk_rejections=[],
            approved_orders=[],
            executed_orders=[],
            starting_cash=starting_cash,
            ending_cash=starting_cash,
            overnight_exposure=0.0,
            env=active_env,
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
    top_candidates = candidates[:top_n]

    ranked_display = []
    for rank_idx, c in enumerate(candidates, start=1):
        decision = f"SELECTED (Top {top_n})" if rank_idx <= top_n else f"EXCLUDED (Cut by Top N={top_n})"
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
            qqq_ema20=bench_ema,
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
            env=active_env,
            custom_audit_dir=audit_dir_override,
        )

    # 4. Formulate Order Proposals
    target_budget = (
        cfg_data.get("live_pilot_budget_usd") or settings.LIVE_PILOT_BUDGET_USD
        if active_env == "live"
        else cfg_data.get("max_position_size_usd") or settings.MAX_POSITION_SIZE_USD
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

    # Send Discord notification
    notifier = DiscordNotifier(env=active_env)
    regime_str = f"QQQ ${bench_current:.2f} >= {ema_period} EMA ${bench_ema:.2f} (BULL)"

    if executed_order_reports:
        notifier.notify_buy_orders(
            orders=executed_order_reports,
            regime_info=regime_str,
            total_cost=sum(o["total_value"] for o in executed_order_reports),
            cash_balance=ending_cash,
            rejections=rejections,
            trigger_source=trigger_source,
            env=active_env,
        )
    else:
        # Zero buy orders placed (e.g. insufficient cash for high share prices or exposure reached)
        rejection_summary = "\n".join(f"• {r}" for r in rejections[:3]) if rejections else "All candidates filtered by constraints."
        details = [
            {"name": "Benchmark (QQQ)", "value": f"${bench_current:.2f} ({ema_period} EMA: ${bench_ema:.2f})", "inline": True},
            {"name": "Available Cash", "value": f"${starting_cash:,.2f}", "inline": True},
            {"name": "Orders Executed", "value": "0", "inline": True},
        ]
        if rejections:
            details.append({"name": "🛡️ Rejection Rationale", "value": rejection_summary, "inline": False})

        notifier.notify_routine_status(
            routine_name="🔔 Afternoon Buy Scan Checked",
            message=f"Market Regime is **BULLISH**, but **0 orders were placed** (insufficient cash or stock price too high). Sitting in **CASH**.",
            trigger_source=trigger_source,
            env=active_env,
            details=details,
        )

    # 7. Generate & Persist Verbose Decision Dossier
    return DecisionDossier.create_close_dossier(
        regime_status="BULL",
        qqq_price=bench_current,
        qqq_ema20=bench_ema,
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
        env=active_env,
        custom_audit_dir=audit_dir_override,
    )


if __name__ == "__main__":
    run_close_routine()
