"""CLI Tool to reset paper ledgers and test artifacts back to a clean state.

Usage:
    # Reset both live paper ledger and sandbox ledger to $10,000 cash with 0 positions
    python3 scripts/reset_test_data.py

    # Reset with custom initial cash balance
    python3 scripts/reset_test_data.py --cash 25000

    # Also wipe temporary audit dossiers (keeps .gitkeep)
    python3 scripts/reset_test_data.py --clear-audit
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

DATA_DIR = ROOT_DIR / "data_cache"
PAPER_LEDGER = DATA_DIR / "paper_ledger.json"
SANDBOX_LEDGER = DATA_DIR / "sandbox_ledger.json"
AUDIT_DIR = DATA_DIR / "audit"


def reset_ledger(filepath: Path, cash_amount: float):
    """Reset a specific ledger file to initial state."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    clean_payload = {
        "cash": float(cash_amount),
        "positions": {},
        "trade_history": [],
        "last_updated": datetime.now().isoformat(),
    }
    with open(filepath, "w") as f:
        json.dump(clean_payload, f, indent=2)
    print(f"✅ Reset {filepath.name:<20} -> Cash: ${cash_amount:,.2f} | Positions: 0 | History: 0 trades")


def clear_audit_dossiers():
    """Clear generated audit dossiers in data_cache/audit/."""
    if not AUDIT_DIR.exists():
        return
    count = 0
    for f in AUDIT_DIR.glob("*.json"):
        f.unlink()
        count += 1
    print(f"🧹 Cleared {count} temporary audit dossier JSON file(s) in data_cache/audit/")


def main():
    parser = argparse.ArgumentParser(description="Reset Paper Trading & Test Data")
    parser.add_argument("--cash", type=float, default=10000.0, help="Initial cash balance to reset to (default: 10000.0)")
    parser.add_argument("--clear-audit", action="store_true", help="Also remove all generated dossier JSON files in data_cache/audit/")
    parser.add_argument("--only-sandbox", action="store_true", help="Only reset sandbox_ledger.json without touching paper_ledger.json")
    parser.add_argument("--only-paper", action="store_true", help="Only reset paper_ledger.json without touching sandbox_ledger.json")
    args = parser.parse_args()

    print("\n" + "=" * 75)
    print("🔄 TRADING LEDGER & TEST DATA RESET")
    print("=" * 75)

    if not args.only_sandbox:
        reset_ledger(PAPER_LEDGER, args.cash)

    if not args.only_paper:
        reset_ledger(SANDBOX_LEDGER, args.cash)

    if args.clear_audit:
        clear_audit_dossiers()

    print("=" * 75)
    print("🎉 System restored to clean initial baseline.\n")


if __name__ == "__main__":
    main()
