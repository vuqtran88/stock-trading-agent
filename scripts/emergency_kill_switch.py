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

from risk.risk_manager import RiskManager
from execution.paper_broker import PaperBroker

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EmergencyStop")


def handle_emergency(action: str, reason: str = "Manual Emergency Stop"):
    risk_mgr = RiskManager()
    broker = PaperBroker()

    if action == "status":
        active = risk_mgr.is_kill_switch_active()
        status_str = "ACTIVE (TRADING HALTED)" if active else "INACTIVE (NORMAL)"
        print(f"\nKill Switch Status: {status_str}")
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
        if positions:
            print(f"Liquidating {len(positions)} open positions immediately to CASH...")
            reports = broker.flatten_all_positions()
            for r in reports:
                print(f"  SOLD {r.shares} {r.ticker} @ ${r.fill_price:.2f} (P&L: ${r.realized_pnl:+,.2f})")
        else:
            print("No open positions to liquidate. Portfolio is already 100% Cash.")

        print(f"Final Settled Cash Balance: ${broker.get_cash_balance():,.2f}\n")


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
