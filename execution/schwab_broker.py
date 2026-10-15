"""Charles Schwab Trader REST API Broker implementation.

Implements BaseBroker interface for live account balance, position polling,
and market order execution.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
import requests

from config.settings import settings
from execution.base_broker import BaseBroker, Position, ExecutionReport
from execution.schwab_auth import SchwabAuth

logger = logging.getLogger(__name__)

SCHWAB_API_BASE = "https://api.schwabapi.com/trader/v1"


class SchwabBroker(BaseBroker):
    """Live Charles Schwab Brokerage connection using official Trader API."""

    def __init__(
        self,
        auth: Optional[SchwabAuth] = None,
        account_hash: Optional[str] = None,
    ):
        self.auth = auth or SchwabAuth()
        self.account_hash = account_hash or settings.SCHWAB_ACCOUNT_HASH
        if not self.account_hash:
            self._auto_detect_account_hash()

    def _get_headers(self) -> Dict[str, str]:
        token = self.auth.get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _auto_detect_account_hash(self):
        """Fetch account numbers and select the first available account hash."""
        url = f"{SCHWAB_API_BASE}/accounts/accountNumbers"
        try:
            resp = requests.get(url, headers=self._get_headers(), timeout=10)
            if resp.status_code == 200:
                accounts = resp.json()
                if accounts:
                    self.account_hash = accounts[0]["hashValue"]
                    logger.info(f"Auto-selected Schwab account hash: {self.account_hash}")
                else:
                    logger.warning("No linked Schwab accounts found.")
            else:
                logger.warning(f"Failed to fetch account numbers: {resp.text}")
        except Exception as e:
            logger.warning(f"Could not auto-detect account hash: {e}")

    def get_cash_balance(self) -> float:
        """Fetch settled cash from Schwab account."""
        if not self.account_hash:
            raise RuntimeError("SCHWAB_ACCOUNT_HASH is not set and could not be detected.")

        url = f"{SCHWAB_API_BASE}/accounts/{self.account_hash}?fields=positions"
        resp = requests.get(url, headers=self._get_headers(), timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Schwab get_cash_balance error ({resp.status_code}): {resp.text}")

        data = resp.json()
        securities_acc = data.get("securitiesAccount", {})
        balances = securities_acc.get("currentBalances", {})
        # Settled cash or cash balance
        cash = (
            balances.get("cashBalance")
            or balances.get("availableFunds")
            or balances.get("settledFunds")
            or 0.0
        )
        return float(cash)

    def get_positions(self) -> Dict[str, Position]:
        """Fetch active positions from Schwab account."""
        if not self.account_hash:
            raise RuntimeError("SCHWAB_ACCOUNT_HASH is not set.")

        url = f"{SCHWAB_API_BASE}/accounts/{self.account_hash}?fields=positions"
        resp = requests.get(url, headers=self._get_headers(), timeout=10)
        if resp.status_code != 200:
            raise RuntimeError(f"Schwab get_positions error: {resp.text}")

        data = resp.json()
        positions_raw = data.get("securitiesAccount", {}).get("positions", [])
        result = {}

        for p in positions_raw:
            instrument = p.get("instrument", {})
            sym = instrument.get("symbol", "").upper()
            long_qty = int(p.get("longQuantity", 0))
            cost_basis = float(p.get("averagePrice", 0.0))
            mkt_val = float(p.get("marketValue", 0.0))

            if long_qty > 0 and sym:
                result[sym] = Position(
                    ticker=sym,
                    shares=long_qty,
                    entry_price=cost_basis,
                    entry_time=datetime.now().isoformat(),
                    current_price=(mkt_val / long_qty) if long_qty > 0 else cost_basis,
                )

        return result

    def _place_order(self, ticker: str, shares: int, instruction: str) -> ExecutionReport:
        """Construct and send order payload to Schwab."""
        if not self.account_hash:
            raise RuntimeError("SCHWAB_ACCOUNT_HASH is not set.")

        url = f"{SCHWAB_API_BASE}/accounts/{self.account_hash}/orders"
        order_payload = {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [
                {
                    "instruction": instruction,  # "BUY" or "SELL"
                    "quantity": shares,
                    "instrument": {
                        "symbol": ticker.upper(),
                        "assetType": "EQUITY",
                    },
                }
            ],
        }

        resp = requests.post(url, headers=self._get_headers(), json=order_payload, timeout=15)
        now_str = datetime.now().isoformat()

        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Schwab order placement failed ({resp.status_code}): {resp.text}")

        # In Schwab REST API, order location header contains order ID:
        # e.g., 'Location': 'https://api.schwabapi.com/trader/v1/accounts/.../orders/12345678'
        location = resp.headers.get("Location", "")
        order_id = location.split("/")[-1] if location else "Submitted"
        logger.info(f"Schwab Order Placed: {instruction} {shares} {ticker} (Order ID: {order_id})")

        return ExecutionReport(
            ticker=ticker,
            side=instruction,
            shares=shares,
            fill_price=0.0,  # Fill price will be updated upon order execution confirmation
            total_value=0.0,
            timestamp=now_str,
            status="SUBMITTED",
        )

    def buy(self, ticker: str, shares: int, target_price: Optional[float] = None) -> ExecutionReport:
        """Place live Market Buy order."""
        return self._place_order(ticker=ticker, shares=shares, instruction="BUY")

    def sell(self, ticker: str, shares: int, target_price: Optional[float] = None) -> ExecutionReport:
        """Place live Market Sell order."""
        return self._place_order(ticker=ticker, shares=shares, instruction="SELL")

    def flatten_all_positions(self) -> List[ExecutionReport]:
        """Query all open positions on Schwab and submit market sell orders."""
        positions = self.get_positions()
        reports = []
        for sym, pos in positions.items():
            rep = self.sell(ticker=sym, shares=pos.shares)
            reports.append(rep)
        return reports
