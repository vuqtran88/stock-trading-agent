"""Structured Decision Dossier and Audit Receipt Generator.

Generates machine-readable and human-friendly audit records explaining:
- Market Regime status (QQQ price vs 20 EMA)
- Earnings Blackout screening results
- Momentum vs Dip composite score rankings for every ticker
- Rejection reasons for excluded tickers
- Deterministic risk sizing decisions and fill executions
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
AUDIT_DIR = ROOT_DIR / "data_cache" / "audit"

logger = logging.getLogger("DecisionDossier")


class DecisionDossier:
    """Creates, logs, and persists structured execution dossiers."""

    @staticmethod
    def create_close_dossier(
        regime_status: str,
        qqq_price: float,
        qqq_ema20: float,
        scanned_tickers: List[str],
        earnings_disqualified: List[str],
        candidate_rankings: List[Dict[str, Any]],
        rejected_candidates: List[Dict[str, Any]],
        risk_proposals: List[Dict[str, Any]],
        risk_rejections: List[str],
        approved_orders: List[Dict[str, Any]],
        executed_orders: List[Dict[str, Any]],
        starting_cash: float,
        ending_cash: float,
        overnight_exposure: float,
        env: str = "paper",
        custom_audit_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Generate structured dossier for 3:50 PM ET Close Buy Routine."""
        now = datetime.now(timezone.utc)
        target_dir = custom_audit_dir or AUDIT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        dossier = {
            "dossier_type": "CLOSE_ROUTINE_BUY_SCAN",
            "timestamp_utc": now.isoformat(),
            "timestamp_et": now.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
            "environment": env,
            "regime": {
                "status": regime_status,
                "benchmark": "QQQ",
                "price": round(qqq_price, 2),
                "ema20": round(qqq_ema20, 2),
                "distance_pct": round(((qqq_price - qqq_ema20) / qqq_ema20) * 100.0, 2) if qqq_ema20 > 0 else 0.0,
                "passed": regime_status.upper() == "BULL",
            },
            "earnings_blackout": {
                "scanned_universe": scanned_tickers,
                "disqualified_tickers": earnings_disqualified,
            },
            "scoring_and_ranking": {
                "candidates_ranked": candidate_rankings,
                "disqualified_candidates": rejected_candidates,
            },
            "risk_firewall": {
                "starting_cash": round(starting_cash, 2),
                "proposals": risk_proposals,
                "rejections": risk_rejections,
                "approved_orders": approved_orders,
            },
            "execution": {
                "executed_orders": executed_orders,
                "total_invested": round(sum(o.get("total_value", 0.0) for o in executed_orders), 2),
                "ending_cash": round(ending_cash, 2),
                "overnight_exposure": round(overnight_exposure, 2),
            },
        }

        # Save to disk
        date_str = now.strftime("%Y%m%d_%H%M%S")
        filepath = target_dir / f"dossier_close_{date_str}.json"
        with open(filepath, "w") as f:
            json.dump(dossier, f, indent=2)

        # Update latest pointer
        latest_path = target_dir / "latest_close_dossier.json"
        with open(latest_path, "w") as f:
            json.dump(dossier, f, indent=2)

        DecisionDossier.print_close_dossier(dossier)
        return dossier

    @staticmethod
    def create_open_dossier(
        liquidated_positions: List[Dict[str, Any]],
        starting_cash: float,
        ending_cash: float,
        total_proceeds: float,
        total_net_pnl: float,
        env: str = "paper",
        custom_audit_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Generate structured dossier for 9:28 AM ET Open Sell Routine."""
        now = datetime.now(timezone.utc)
        target_dir = custom_audit_dir or AUDIT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)

        dossier = {
            "dossier_type": "OPEN_ROUTINE_SELL_LIQUIDATE",
            "timestamp_utc": now.isoformat(),
            "timestamp_et": now.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
            "environment": env,
            "starting_cash": round(starting_cash, 2),
            "liquidations": liquidated_positions,
            "summary": {
                "positions_closed": len(liquidated_positions),
                "total_proceeds": round(total_proceeds, 2),
                "total_net_pnl": round(total_net_pnl, 2),
                "return_on_capital_pct": round((total_net_pnl / starting_cash) * 100.0, 2) if starting_cash > 0 else 0.0,
                "ending_cash": round(ending_cash, 2),
                "open_positions_remaining": 0,
            },
        }

        date_str = now.strftime("%Y%m%d_%H%M%S")
        filepath = target_dir / f"dossier_open_{date_str}.json"
        with open(filepath, "w") as f:
            json.dump(dossier, f, indent=2)

        latest_path = target_dir / "latest_open_dossier.json"
        with open(latest_path, "w") as f:
            json.dump(dossier, f, indent=2)

        DecisionDossier.print_open_dossier(dossier)
        return dossier

    @staticmethod
    def print_close_dossier(d: Dict[str, Any]):
        """Format and print beautiful console output."""
        print("\n" + "=" * 80)
        print(f"📊 STRUCTURED DECISION DOSSIER: AFTERNOON CLOSE ROUTINE [{d['environment'].upper()}]")
        print(f"   Execution Time: {d['timestamp_et']}")
        print("=" * 80)

        reg = d["regime"]
        status_icon = "🟢" if reg["passed"] else "🔴"
        print(f"\n[1] REGIME FILTER: {status_icon} {reg['status']}")
        print(f"    Benchmark: {reg['benchmark']} @ ${reg['price']:.2f} | 20 EMA: ${reg['ema20']:.2f} ({reg['distance_pct']:+.2f}%)")
        if not reg["passed"]:
            print("    ⛔ Market regime is BEARISH. Stand down and maintain 100% Cash.")
            print("=" * 80 + "\n")
            return

        earn = d["earnings_blackout"]
        disq = earn["disqualified_tickers"]
        print(f"\n[2] EARNINGS BLACKOUT SCREENING:")
        print(f"    Scanned Universe: {', '.join(earn['scanned_universe'])}")
        if disq:
            print(f"    🚫 Blacklisted for Tonight/Tomorrow: {', '.join(disq)}")
        else:
            print("    ✅ No target stocks have pending earnings tonight or tomorrow morning.")

        print(f"\n[3] MOMENTUM & DIP RANKING TABLE:")
        print(f"    {'Rank':<5} {'Ticker':<7} {'Price':<10} {'20d Mom':<10} {'Intraday':<10} {'Score':<10} {'Decision'}")
        print("    " + "-" * 72)
        for c in d["scoring_and_ranking"]["candidates_ranked"]:
            print(
                f"    #{c['rank']:<4} {c['ticker']:<7} ${c['price']:<9.2f} "
                f"{c['mom20']*100:>+6.1f}%   {c['intraday_ret']*100:>+6.2f}%   "
                f"{c['score']:>+7.4f}   {c['decision']}"
            )
        for r in d["scoring_and_ranking"]["disqualified_candidates"]:
            print(f"    {'--':<5} {r['ticker']:<7} ${r.get('price', 0.0):<9.2f} {'--':<10} {'--':<10} {'--':<10} 🚫 {r['reason']}")

        risk = d["risk_firewall"]
        print(f"\n[4] RISK SIZING & ORDER EXECUTION:")
        print(f"    Available Cash: ${risk['starting_cash']:,.2f}")
        for o in d["execution"]["executed_orders"]:
            print(f"    ✅ BOUGHT {o['shares']} shares of {o['ticker']} @ ${o['fill_price']:.2f} (Cost: ${o['total_value']:,.2f})")
        if not d["execution"]["executed_orders"]:
            print("    ⚠️  Zero orders placed.")

        print(f"\n[5] PORTFOLIO SUMMARY:")
        print(f"    Total Invested:     ${d['execution']['total_invested']:,.2f}")
        print(f"    Remaining Cash:     ${d['execution']['ending_cash']:,.2f}")
        print(f"    Overnight Exposure: ${d['execution']['overnight_exposure']:,.2f}")
        print("=" * 80 + "\n")

    @staticmethod
    def print_open_dossier(d: Dict[str, Any]):
        """Format and print open routine liquidation output."""
        print("\n" + "=" * 80)
        print(f"🌅 STRUCTURED DECISION DOSSIER: MORNING OPEN LIQUIDATION [{d['environment'].upper()}]")
        print(f"   Execution Time: {d['timestamp_et']}")
        print("=" * 80)

        summ = d["summary"]
        print(f"\n[1] LIQUIDATIONS EXECUTED: {summ['positions_closed']} position(s)")
        print(f"    {'Ticker':<8} {'Shares':<8} {'Entry Close':<14} {'Exit Open':<14} {'Proceeds':<12} {'Net P&L'}")
        print("    " + "-" * 72)
        for p in d["liquidations"]:
            pnl_str = f"{p['pnl']:+,.2f} ({p['return_pct']:+.2f}%)"
            print(
                f"    {p['ticker']:<8} {p['shares']:<8} ${p['entry_price']:<13.2f} "
                f"${p['exit_price']:<13.2f} ${p['proceeds']:<11.2f} {pnl_str}"
            )

        print(f"\n[2] FINANCIAL SETTLEMENT:")
        print(f"    Starting Cash:     ${d['starting_cash']:,.2f}")
        print(f"    Total Proceeds:    ${summ['total_proceeds']:,.2f}")
        print(f"    Net Overnight P&L: ${summ['total_net_pnl']:+,.2f} ({summ['return_on_capital_pct']:+.2f}%)")
        print(f"    Ending Cash:       ${summ['ending_cash']:,.2f}")
        print(f"    Open Positions:    {summ['open_positions_remaining']} (100% in CASH)")
        print("=" * 80 + "\n")
