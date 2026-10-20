"""Morning Market Open Routine (9:28 AM ET).

Workflow:
1. Query active open overnight positions from Broker ledger.
2. If no positions held -> Log "Sitting 100% Cash" and return empty dossier.
3. If positions held -> Sell each position at Market Open (9:30 AM ET).
4. Calculate overnight realized P&L and credit cash to ledger.
5. Account returns to 100% Cash for the rest of the day.
6. Generate and save structured Decision Dossier.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from typing import Optional

from config.settings import settings
from execution.paper_broker import PaperBroker
from execution.schwab_broker import SchwabBroker
from execution.dossier import DecisionDossier
from data.fetcher import MarketDataFetcher
from notifications.notifier import DiscordNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpenRoutine")


def get_broker(active_env: Optional[str] = None):
    """Instantiate broker based on active_env or settings.ENV."""
    env = active_env or settings.ENV
    if env == "live":
        logger.info("Operating in LIVE mode: Using SchwabBroker.")
        return SchwabBroker()
    else:
        logger.info("Operating in PAPER mode: Using PaperBroker.")
        return PaperBroker()


def run_open_routine(broker_override=None, fetcher_override=None, audit_dir_override=None, trigger_source: str = "SCHEDULED"):
    """Execute Morning Open Sell Routine with full verbose dossier generation."""
    from backend.routes.config import get_active_overrides
    cfg_data = get_active_overrides()
    active_env = cfg_data.get("env") or settings.ENV

    source_label = "⏱️ SCHEDULED (Cron)" if trigger_source.upper() == "SCHEDULED" else "👤 MANUAL (Dashboard)"
    logger.info("=" * 65)
    logger.info(f"STARTING MORNING OPEN ROUTINE (9:28 AM ET) [{source_label}] [{active_env.upper()}]")
    logger.info("=" * 65)

    broker = broker_override or get_broker(active_env=active_env)
    fetcher = fetcher_override or MarketDataFetcher()

    starting_cash = float(broker.get_cash_balance())

    # 1. Query Open Overnight Positions
    positions = broker.get_positions()
    if not positions:
        logger.info(f"No open overnight positions found in ledger. Account is already 100% in CASH (${starting_cash:,.2f}).")
        notifier = DiscordNotifier(env=active_env)
        notifier.notify_routine_status(
            routine_name="☀️ Morning Exit Routine Checked",
            message=f"Account is already 100% in **CASH** (${starting_cash:,.2f}). 0 overnight positions required liquidation.",
            trigger_source=trigger_source,
            env=active_env,
            details=[
                {"name": "Total Liquidations", "value": "0 positions", "inline": True},
                {"name": "Settled Cash", "value": f"${starting_cash:,.2f}", "inline": True},
            ],
        )
        return DecisionDossier.create_open_dossier(
            liquidated_positions=[],
            starting_cash=starting_cash,
            ending_cash=starting_cash,
            total_proceeds=0.0,
            total_net_pnl=0.0,
            env=active_env,
            custom_audit_dir=audit_dir_override,
        )

    logger.info(f"Discovered {len(positions)} active overnight holdings to liquidate at open:")
    for sym, pos in positions.items():
        logger.info(f"  Holding {pos.shares} shares of {sym} (Cost: ${pos.shares * pos.entry_price:,.2f})")

    # 2. Liquidate Each Position at Market Open
    total_realized_pnl = 0.0
    total_proceeds = 0.0
    liquidated_details = []
    executed_sell_reports = []

    for sym, pos in positions.items():
        quote = fetcher.get_latest_quote(sym)
        exit_price = float(quote.get("open") or quote.get("last_price", 0.0))

        report = broker.sell(ticker=sym, shares=pos.shares, target_price=exit_price)
        pnl = float(report.realized_pnl or 0.0)
        proceeds = float(pos.shares * exit_price)

        total_realized_pnl += pnl
        total_proceeds += proceeds
        ret_pct = (pnl / (pos.shares * pos.entry_price)) * 100.0 if pos.entry_price > 0 else 0.0

        liquidated_details.append({
            "ticker": sym,
            "shares": pos.shares,
            "entry_price": round(float(pos.entry_price), 2),
            "exit_price": round(exit_price, 2),
            "proceeds": round(proceeds, 2),
            "pnl": round(pnl, 2),
            "return_pct": round(ret_pct, 2),
        })

        executed_sell_reports.append({
            "ticker": sym,
            "shares": pos.shares,
            "fill_price": exit_price,
            "realized_pnl": pnl,
        })

    ending_cash = float(broker.get_cash_balance())

    # Send Discord notification
    if executed_sell_reports:
        notifier = DiscordNotifier(env=active_env)
        notifier.notify_sell_orders(
            reports=executed_sell_reports,
            total_pnl=total_realized_pnl,
            cash_balance=ending_cash,
            env=active_env,
        )

    # Generate & Persist Verbose Decision Dossier
    return DecisionDossier.create_open_dossier(
        liquidated_positions=liquidated_details,
        starting_cash=starting_cash,
        ending_cash=ending_cash,
        total_proceeds=total_proceeds,
        total_net_pnl=total_realized_pnl,
        env=active_env,
        custom_audit_dir=audit_dir_override,
    )


if __name__ == "__main__":
    run_open_routine()
