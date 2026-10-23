"""Capital and cash flow ledger manager.

Tracks external cash deposits/withdrawals and calculates true strategy dollar profit
and Time-Weighted Return (TWR) independent of external bank transfers.
Synchronized persistently with GCP Secret Manager ('strategy-capital-ledger')
and cached locally to disk.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

LEDGER_FILE = settings.DATA_DIR / "capital_ledger.json"
GCP_CAPITAL_SECRET_NAME = "projects/stock-trading-agent-249477/secrets/strategy-capital-ledger"


def _fetch_capital_ledger_from_secret() -> Optional[Dict]:
    """Fetch capital ledger from GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"{GCP_CAPITAL_SECRET_NAME}/versions/latest"
        resp = client.access_secret_version(name=name)
        payload = resp.payload.data.decode("utf-8")
        if payload:
            return json.loads(payload)
    except Exception as e:
        logger.debug(f"Secret Manager capital ledger access skipped or failed: {e}")
    return None


def _sync_capital_ledger_to_secret(ledger: Dict):
    """Persist capital ledger to GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        payload_bytes = json.dumps(ledger, indent=2).encode("utf-8")
        client.add_secret_version(
            parent=GCP_CAPITAL_SECRET_NAME,
            payload={"data": payload_bytes},
        )
        logger.info("Persisted updated capital ledger to GCP Secret Manager.")
    except Exception as e:
        logger.warning(f"Could not persist capital ledger to Secret Manager: {e}")


class CapitalLedgerManager:
    """Manages cash flows (deposits/withdrawals), net capital base, and true strategy P&L."""

    def __init__(self, env: str = "paper"):
        self.env = env
        self.ledger_file = settings.DATA_DIR / f"capital_ledger_{env}.json"
        self._load()

    def _default_ledger(self) -> Dict:
        now_str = datetime.now(timezone.utc).isoformat()
        if self.env == "paper":
            initial_cap = 10000.0
            return {
                "environment": self.env,
                "last_synced_utc": now_str,
                "initial_capital": initial_cap,
                "cash_flows": [
                    {
                        "id": f"paper-init-{int(datetime.now().timestamp())}",
                        "date": now_str,
                        "type": "INITIAL_DEPOSIT",
                        "amount": initial_cap,
                        "description": "Paper Starting Capital",
                    }
                ],
                "unit_nav": 10.0,
                "total_units": initial_cap / 10.0,
            }
        else:
            return {
                "environment": self.env,
                "last_synced_utc": now_str,
                "initial_capital": 0.0,
                "cash_flows": [],
                "unit_nav": 10.0,
                "total_units": 0.0,
            }

    def _load(self):
        """Load ledger from local disk cache, falling back to GCP Secret Manager for live env."""
        if self.ledger_file.exists():
            try:
                with open(self.ledger_file, "r") as f:
                    self.data = json.load(f)
                    return
            except Exception:
                pass

        if self.env == "live":
            remote = _fetch_capital_ledger_from_secret()
            if remote:
                self.data = remote
                self._save_local()
                return

        self.data = self._default_ledger()
        self._save()

    def _save_local(self):
        try:
            self.ledger_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.ledger_file, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving local capital ledger: {e}")

    def _save(self):
        self._save_local()
        if self.env == "live":
            _sync_capital_ledger_to_secret(self.data)

    def sync_schwab_transactions(self, raw_transactions: List[Dict], current_equity: float):
        """Auto-ingest bank deposits and withdrawals directly from Schwab API transactions."""
        if self.env != "live" or not raw_transactions:
            return

        # 1. Filter out internal margin/cash sweeps (e.g. TRF FUNDS FRM TYPE 1 / TO TYPE 2)
        valid_txs = []
        for tx in raw_transactions:
            tx_type = (tx.get("type") or "").upper()
            net_amt = float(tx.get("netAmount") or 0.0)
            desc = (tx.get("description") or "").upper()

            if "TYPE 1" in desc or "TYPE 2" in desc or "SWEEP" in desc:
                continue

            # Identify external funding transfers (ACH, Journal from Schwab Bank, Wires)
            is_deposit = (
                (tx_type == "JOURNAL" and "FROM SCHWAB BANK" in desc and net_amt > 0)
                or (tx_type in ("ACH_RECEIPT", "CASH_RECEIPT", "WIRE_IN") and net_amt > 0)
            )
            is_withdrawal = (
                (tx_type == "JOURNAL" and "TO SCHWAB BANK" in desc and net_amt < 0)
                or (tx_type in ("ACH_DISBURSEMENT", "CASH_DISBURSEMENT", "WIRE_OUT") and net_amt < 0)
            )

            if is_deposit or is_withdrawal:
                valid_txs.append((tx, is_deposit, abs(net_amt)))

        # 2. Sort chronologically so earliest bank transfer naturally establishes initial capital
        valid_txs.sort(key=lambda item: item[0].get("time") or item[0].get("transactionDate") or "")

        existing_ids = {cf.get("id") for cf in self.data.get("cash_flows", [])}
        has_initial = any(cf.get("type") == "INITIAL_DEPOSIT" for cf in self.data.get("cash_flows", []))
        updated = False

        for tx, is_deposit, amount in valid_txs:
            activity_id = str(tx.get("activityId") or tx.get("transactionId") or f"{tx.get('time')}-{amount}")
            if activity_id in existing_ids:
                continue

            tx_time = tx.get("time") or tx.get("transactionDate") or datetime.now(timezone.utc).isoformat()

            # Earliest discovered deposit becomes the baseline starting capital
            if is_deposit and not has_initial:
                cf_type = "INITIAL_DEPOSIT"
                has_initial = True
                self.data["initial_capital"] = round(amount, 2)
                self.data["total_units"] = round(amount / 10.0, 4)
            else:
                cf_type = "DEPOSIT" if is_deposit else "WITHDRAWAL"
                # Update Unit NAV before applying deposit (Time-Weighted Return preservation)
                curr_units = self.data.get("total_units", 100.0)
                curr_nav = (current_equity / curr_units) if curr_units > 0 else 10.0
                new_units = (amount / curr_nav) if curr_nav > 0 else amount

                if is_deposit:
                    self.data["total_units"] = curr_units + new_units
                else:
                    self.data["total_units"] = max(1.0, curr_units - new_units)

            self.data.setdefault("cash_flows", []).append({
                "id": activity_id,
                "date": tx_time,
                "type": cf_type,
                "amount": round(amount, 2),
                "description": tx.get("description") or f"Schwab Bank {cf_type.capitalize()}",
            })
            existing_ids.add(activity_id)
            updated = True

        if updated:
            self.data["last_synced_utc"] = datetime.now(timezone.utc).isoformat()
            self._save()

    def get_metrics(self, current_total_equity: float) -> Dict:
        """Calculate Net Contributed Capital, True Realized Strategy Gain ($), and TWR (%)."""
        cash_flows = self.data.get("cash_flows", [])
        
        # Net contributed capital = Initial + Deposits - Withdrawals
        net_contributed = 0.0
        for cf in cash_flows:
            c_type = cf.get("type", "")
            amt = float(cf.get("amount", 0.0))
            if c_type in ("INITIAL_DEPOSIT", "DEPOSIT"):
                net_contributed += amt
            elif c_type == "WITHDRAWAL":
                net_contributed -= amt

        # True Strategy Dollar Gain
        true_net_pnl = current_total_equity - net_contributed
        true_net_pnl_pct = (true_net_pnl / net_contributed * 100.0) if net_contributed > 0 else 0.0

        # Time-Weighted Return (via Unit NAV)
        total_units = self.data.get("total_units", 100.0)
        curr_nav = (current_total_equity / total_units) if total_units > 0 else 10.0
        base_nav = self.data.get("unit_nav", 10.0)
        twr_pct = ((curr_nav - base_nav) / base_nav) * 100.0 if base_nav > 0 else 0.0

        # Sort cash flows newest first
        sorted_cfs = sorted(cash_flows, key=lambda x: str(x.get("date", "")), reverse=True)

        return {
            "net_contributed_capital": round(net_contributed, 2),
            "true_strategy_pnl": round(true_net_pnl, 2),
            "true_strategy_pnl_pct": round(true_net_pnl_pct, 2),
            "twr_pct": round(twr_pct, 2),
            "unit_nav": round(curr_nav, 4),
            "cash_flows": sorted_cfs[:50],
        }
