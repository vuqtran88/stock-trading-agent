"""Morning Market Open Routine (9:28 AM ET).

Workflow:
1. Query active open overnight positions from PaperBroker ledger.
2. If no positions held -> Log "Sitting 100% Cash" and exit.
3. If positions held -> Sell each position at Market Open (9:30 AM ET).
4. Calculate overnight realized P&L and credit cash to ledger.
5. Account returns to 100% Cash for the rest of the day.
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from execution.paper_broker import PaperBroker
from execution.schwab_broker import SchwabBroker
from data.fetcher import MarketDataFetcher
from notifications.notifier import DiscordNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("OpenRoutine")


def get_broker():
    """Instantiate broker based on settings.ENV."""
    if settings.ENV == "live":
        logger.info("Operating in LIVE mode: Using SchwabBroker.")
        return SchwabBroker()
    else:
        logger.info("Operating in PAPER mode: Using PaperBroker.")
        return PaperBroker()


def run_open_routine():
    logger.info("=" * 65)
    logger.info("STARTING MORNING OPEN ROUTINE (9:28 AM ET)")
    logger.info("=" * 65)

    broker = get_broker()
    fetcher = MarketDataFetcher()

    # 1. Query Open Overnight Positions
    positions = broker.get_positions()
    if not positions:
        logger.info("No open overnight positions found in ledger. Account is already 100% in CASH.")
        return

    logger.info(f"Discovered {len(positions)} active overnight holdings to liquidate at open:")
    for sym, pos in positions.items():
        logger.info(f"  Holding {pos.shares} shares of {sym} (Cost: ${pos.shares * pos.entry_price:,.2f})")

    # 2. Liquidate Each Position at Market Open
    print("\n" + "=" * 75)
    print(f"{'Ticker':<8} | {'Shares':<6} | {'Entry Close':<12} | {'Exit Open':<12} | {'Overnight P&L':<15}")
    print("-" * 75)

    total_realized_pnl = 0.0
    executed_sell_reports = []

    for sym, pos in positions.items():
        # Get opening price from fast quote or fallback
        quote = fetcher.get_latest_quote(sym)
        exit_price = quote.get("open") or quote.get("last_price", 0.0)

        report = broker.sell(ticker=sym, shares=pos.shares, target_price=exit_price)
        pnl = report.realized_pnl or 0.0
        total_realized_pnl += pnl
        pnl_pct = (pnl / (pos.shares * pos.entry_price)) * 100.0 if pos.entry_price > 0 else 0.0

        pnl_str = f"${pnl:+,.2f} ({pnl_pct:+.2f}%)"
        print(f"{sym:<8} | {pos.shares:<6} | ${pos.entry_price:>10.2f} | ${exit_price:>10.2f} | {pnl_str:>15}")

        executed_sell_reports.append({
            "ticker": sym,
            "shares": pos.shares,
            "fill_price": exit_price,
            "realized_pnl": pnl,
        })

    # Send Discord notification
    notifier = DiscordNotifier()
    notifier.notify_sell_orders(
        reports=executed_sell_reports,
        total_pnl=total_realized_pnl,
        cash_balance=broker.get_cash_balance(),
        env=settings.ENV,
    )

    print("=" * 75)
    print(f"Total Net Overnight P&L Realized: ${total_realized_pnl:+,.2f}")
    print(f"New Settled Cash Balance        : ${broker.get_cash_balance():,.2f}")
    print("Portfolio is now 100% in CASH for the day.\n")


if __name__ == "__main__":
    run_open_routine()
