"""Local Paper Trading Simulator Broker.

Maintains a persistent JSON ledger of cash, open positions, and executed fills
using real-time market snapshots without risking real money.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import settings
from data.fetcher import MarketDataFetcher
from execution.base_broker import BaseBroker, Position, ExecutionReport

logger = logging.getLogger(__name__)


class PaperBroker(BaseBroker):
    """Local simulated paper broker with persistent JSON ledger."""

    def __init__(
        self,
        ledger_path: Optional[Path] = None,
        initial_cash: float = 10000.0,
        data_fetcher: Optional[MarketDataFetcher] = None,
    ):
        self.ledger_file = ledger_path or (settings.DATA_DIR / "paper_ledger.json")
        self.fetcher = data_fetcher or MarketDataFetcher()
        self.initial_cash = initial_cash
        self._load_or_initialize_ledger()

    def _load_or_initialize_ledger(self):
        """Load state from disk or initialize fresh ledger."""
        self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        if self.ledger_file.exists():
            try:
                with open(self.ledger_file, "r") as f:
                    self.ledger = json.load(f)
                    return
            except Exception as e:
                logger.warning(f"Failed to read ledger {self.ledger_file}: {e}. Reinitializing.")

        self.ledger = {
            "cash": self.initial_cash,
            "positions": {},
            "trade_history": [],
            "last_updated": datetime.now().isoformat(),
        }
        self._save_ledger()

    def _save_ledger(self):
        """Persist current ledger to disk atomically."""
        self.ledger["last_updated"] = datetime.now().isoformat()
        temp_file = self.ledger_file.with_suffix(".tmp")
        with open(temp_file, "w") as f:
            json.dump(self.ledger, f, indent=2)
        temp_file.replace(self.ledger_file)

    def get_cash_balance(self) -> float:
        """Get current settled cash balance."""
        return float(self.ledger.get("cash", 0.0))

    def get_positions(self) -> Dict[str, Position]:
        """Get active open positions."""
        res = {}
        for sym, pos_data in self.ledger.get("positions", {}).items():
            res[sym] = Position(
                ticker=sym,
                shares=int(pos_data["shares"]),
                entry_price=float(pos_data["entry_price"]),
                entry_time=str(pos_data["entry_time"]),
            )
        return res

    def get_portfolio_exposure(self) -> float:
        """Total dollars currently committed to open positions (at entry cost)."""
        exposure = 0.0
        for pos_data in self.ledger.get("positions", {}).values():
            exposure += pos_data["shares"] * pos_data["entry_price"]
        return float(exposure)

    def buy(self, ticker: str, shares: int, target_price: Optional[float] = None) -> ExecutionReport:
        """Execute simulated market buy order."""
        sym = ticker.upper().strip()
        if shares <= 0:
            raise ValueError(f"Buy shares must be positive, got {shares}")

        # Get fill price
        if target_price and target_price > 0:
            fill_price = target_price
        else:
            quote = self.fetcher.get_latest_quote(sym)
            fill_price = quote.get("last_price", 0.0)
            if fill_price <= 0:
                raise RuntimeError(f"Could not retrieve valid live price for {sym}")

        cost = shares * fill_price
        cash = self.get_cash_balance()

        if cost > cash:
            raise RuntimeError(
                f"Insufficient funds: cost ${cost:,.2f} exceeds cash ${cash:,.2f}"
            )

        # Deduct cash
        self.ledger["cash"] -= cost

        # Update position
        now_str = datetime.now().isoformat()
        if sym in self.ledger["positions"]:
            existing = self.ledger["positions"][sym]
            new_shares = existing["shares"] + shares
            # Average entry price
            avg_entry = ((existing["shares"] * existing["entry_price"]) + cost) / new_shares
            self.ledger["positions"][sym] = {
                "shares": new_shares,
                "entry_price": avg_entry,
                "entry_time": existing["entry_time"],
            }
        else:
            self.ledger["positions"][sym] = {
                "shares": shares,
                "entry_price": fill_price,
                "entry_time": now_str,
            }

        report = ExecutionReport(
            ticker=sym,
            side="BUY",
            shares=shares,
            fill_price=fill_price,
            total_value=cost,
            timestamp=now_str,
            status="FILLED",
        )

        self.ledger["trade_history"].append(report.model_dump())
        self._save_ledger()
        logger.info(f"PAPER BROKER FILL: BUY {shares} {sym} @ ${fill_price:.2f} (Total: ${cost:,.2f})")
        return report

    def sell(self, ticker: str, shares: int, target_price: Optional[float] = None) -> ExecutionReport:
        """Execute simulated market sell order."""
        sym = ticker.upper().strip()
        if sym not in self.ledger["positions"]:
            raise RuntimeError(f"Cannot sell {sym}: No active position found.")

        existing = self.ledger["positions"][sym]
        held_shares = existing["shares"]

        if shares > held_shares:
            raise ValueError(
                f"Cannot sell {shares} shares of {sym}: only holding {held_shares}"
            )

        # Get fill price
        if target_price and target_price > 0:
            fill_price = target_price
        else:
            quote = self.fetcher.get_latest_quote(sym)
            # If sell is called at open, prefer open quote if available
            fill_price = quote.get("open") or quote.get("last_price", 0.0)
            if fill_price <= 0:
                raise RuntimeError(f"Could not retrieve valid live price for {sym}")

        proceeds = shares * fill_price
        entry_price = existing["entry_price"]
        cost_basis = shares * entry_price
        realized_pnl = proceeds - cost_basis

        # Credit cash
        self.ledger["cash"] += proceeds

        # Update positions
        remaining = held_shares - shares
        if remaining > 0:
            self.ledger["positions"][sym]["shares"] = remaining
        else:
            del self.ledger["positions"][sym]

        now_str = datetime.now().isoformat()
        report = ExecutionReport(
            ticker=sym,
            side="SELL",
            shares=shares,
            fill_price=fill_price,
            total_value=proceeds,
            timestamp=now_str,
            status="FILLED",
            realized_pnl=realized_pnl,
        )

        self.ledger["trade_history"].append(report.model_dump())
        self._save_ledger()
        logger.info(
            f"PAPER BROKER FILL: SELL {shares} {sym} @ ${fill_price:.2f} "
            f"(P&L: ${realized_pnl:+,.2f})"
        )
        return report

    def flatten_all_positions(self) -> List[ExecutionReport]:
        """Liquidate all open positions into cash."""
        reports = []
        positions = list(self.ledger["positions"].keys())
        for sym in positions:
            shares = self.ledger["positions"][sym]["shares"]
            rep = self.sell(sym, shares=shares)
            reports.append(rep)
        return reports
