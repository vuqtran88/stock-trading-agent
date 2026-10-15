"""Emergency Kill Switch & Flatten Tool.

Immediately activates emergency lock, blocks all new orders, and flattens
any open positions back to cash.
"""

import sys
import argparse
import logging
from pathlib import Path

# Ensure project root in sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from risk.risk_manager import RiskManager
from execution.paper_broker import PaperBroker
from execution.schwab_broker import SchwabBroker
from notifications.notifier import DiscordNotifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EmergencyStop")


def get_broker():
    """Instantiate broker based on settings.ENV."""
    if settings.ENV == "live":
        return SchwabBroker()
    else:
        return PaperBroker()


def handle_emergency(action: str, reason: str = "Manual Emergency Stop"):
    risk_mgr = RiskManager()
    broker = get_broker()

    if action == "status":
        active = risk_mgr.is_kill_switch_active()
        status_str = "ACTIVE (TRADING HALTED)" if active else "INACTIVE (NORMAL)"
        print(f"\nKill Switch Status: {status_str}")
        print(f"Environment       : {settings.ENV.upper()}")
        print(f"Open Positions    : {len(broker.get_positions())}")
        print(f"Current Cash      : ${broker.get_cash_balance():,.2f}\n")
        return

    if action == "reset":
        risk_mgr.deactivate_kill_switch()
        print("\nEmergency Kill Switch DEACTIVATED. Normal trading resumed.\n")
        return

    if action == "stop":
        # 1. Activate lock
        risk_mgr.activate_kill_switch(reason=reason)
        print("\n" + "!" * 65)
        print(f"EMERGENCY KILL SWITCH ACTIVATED: {reason}")
        print("!" * 65)

        # 2. Flatten all positions
        positions = broker.get_positions()
        flattened_count = len(positions)
        if positions:
            print(f"Liquidating {flattened_count} open positions immediately to CASH on {settings.ENV.upper()}...")
            reports = broker.flatten_all_positions()
            for r in reports:
                print(f"  SOLD {r.shares} {r.ticker} @ ${r.fill_price:.2f} (P&L: ${r.realized_pnl or 0.0:+,.2f})")
        else:
            print("No open positions to liquidate. Portfolio is already 100% Cash.")

        final_cash = broker.get_cash_balance()
        print(f"Final Settled Cash Balance: ${final_cash:,.2f}\n")

        # Notify Discord
        notifier = DiscordNotifier()
        notifier.notify_emergency_stop(
            reason=reason,
            flattened_count=flattened_count,
            cash_balance=final_cash,
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Emergency Kill Switch and Position Flatten Tool")
    parser.add_argument(
        "action",
        choices=["stop", "reset", "status"],
        help="'stop' to halt & flatten; 'reset' to re-enable; 'status' to check state",
    )
    parser.add_argument("--reason", default="Manual CLI Stop", help="Reason for emergency stop")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    handle_emergency(action=args.action, reason=args.reason)
