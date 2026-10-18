"""CLI Tool to run the Fast-Forward 24H Full-Cycle Simulation.

Usage:
    python3 scripts/test_deterministic_cycle.py
    python3 scripts/test_deterministic_cycle.py --seed-only
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from execution.paper_broker import PaperBroker
from scripts.run_close_routine import run_close_routine
from scripts.run_open_routine import run_open_routine
from tests.test_deterministic_cycle import MockDeterministicFetcher, MockEarningsFilter


def main():
    parser = argparse.ArgumentParser(description="Deterministic 24H Fast-Forward Simulator")
    parser.add_argument("--seed-only", action="store_true", help="Only seed test open positions without running routines")
    parser.add_argument("--live-paper", action="store_true", help="Use real paper ledger instead of isolated sandbox")
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("🚀 FAST-FORWARD 24-HOUR TRADING CYCLE SIMULATOR")
    print("=" * 80)

    if args.live_paper:
        broker = PaperBroker()
        audit_dir = ROOT_DIR / "data_cache" / "audit"
        print("Using LIVE paper ledger: data_cache/paper_ledger.json")
    else:
        test_state = ROOT_DIR / "data_cache" / "sandbox_ledger.json"
        audit_dir = ROOT_DIR / "data_cache" / "audit"
        broker = PaperBroker(ledger_path=test_state, initial_cash=10000.0)
        print(f"Using isolated sandbox ledger: {test_state.name}")

    now_str = datetime.now().isoformat()

    if args.seed_only:
        broker.ledger["positions"]["AAPL"] = {"shares": 4, "entry_price": 230.00, "entry_time": now_str}
        broker.ledger["positions"]["NVDA"] = {"shares": 8, "entry_price": 120.00, "entry_time": now_str}
        broker.ledger["cash"] = 8120.00
        broker._save_ledger()
        print("\n✅ Successfully seeded 2 active open positions in ledger:")
        print("   - 4 shares of AAPL @ $230.00 (Cost: $920.00)")
        print("   - 8 shares of NVDA @ $120.00 (Cost: $960.00)")
        print(f"   - Settled Cash: ${broker.get_cash_balance():,.2f}")
        print("\nYou can now open the Web Dashboard and click 'Run Morning Sell Routine' to test liquidation.")
        return

    # Seed positions for Part A
    broker.ledger["positions"]["AAPL"] = {"shares": 4, "entry_price": 230.00, "entry_time": now_str}
    broker.ledger["positions"]["NVDA"] = {"shares": 8, "entry_price": 120.00, "entry_time": now_str}
    broker.ledger["cash"] = 8120.00
    broker._save_ledger()

    print("\n[PART 1] PRE-SEEDED OPEN OVERNIGHT POSITIONS:")
    print(f"  Holdings: AAPL (4 sh @ $230), NVDA (8 sh @ $120) | Cash: ${broker.get_cash_balance():,.2f}")

    # 1. Run Morning Open Sell
    print("\n[PART 2] EXECUTING 9:28 AM MORNING SELL ROUTINE...")
    fetcher_open = MockDeterministicFetcher(is_morning_exit=True)
    open_dossier = run_open_routine(broker_override=broker, fetcher_override=fetcher_open, audit_dir_override=audit_dir)

    # 2. Run Afternoon Close Buy
    print("\n[PART 3] EXECUTING 3:50 PM AFTERNOON BUY SCAN...")
    fetcher_close = MockDeterministicFetcher(is_morning_exit=False)
    earnings_mock = MockEarningsFilter(blackout_syms=["MSFT"])
    close_dossier = run_close_routine(
        broker_override=broker,
        fetcher_override=fetcher_close,
        earnings_filter_override=earnings_mock,
        audit_dir_override=audit_dir,
    )

    # 3. Final Liquidation
    print("\n[PART 4] EXECUTING NEXT-DAY MORNING EXIT...")
    final_open_dossier = run_open_routine(broker_override=broker, fetcher_override=fetcher_open, audit_dir_override=audit_dir)

    print("\n" + "=" * 80)
    print("🎯 FAST-FORWARD CYCLE COMPLETE!")
    print(f"Final Ending Cash: ${broker.get_cash_balance():,.2f}")
    print(f"Active Holdings Remaining: {len(broker.get_positions())} (100% Cash)")
    print(f"Audit Dossiers Written To: {audit_dir}/")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
