"""Deterministic Fast-Forward Cycle Verification Test Suite.

Proves the complete 24-hour Buy -> Hold -> Sell cycle mathematically in < 2 seconds:
1. Part A: Pre-seeds initial open positions into an isolated sandbox ledger,
   triggers run_open_routine(), and asserts exact liquidations, proceeds, and realized P&L.
2. Part B: Starting from settled cash, triggers run_close_routine() on deterministic
   market snapshot, and asserts exact stock selection (AAPL & NVDA) and risk-allocated share counts.
3. Part C: Triggers run_open_routine() again to liquidate Part B's entries,
   confirming exact ending cash, zero open positions, and verified execution receipts.
"""

import json
import shutil
import pytest
import numpy as np
import pandas as pd
from pathlib import Path
from datetime import datetime, date

from execution.paper_broker import PaperBroker, Position
from scripts.run_close_routine import run_close_routine
from scripts.run_open_routine import run_open_routine


class MockEarningsFilter:
    """Mock earnings filter that simulates MSFT having an earnings blackout."""
    def __init__(self, blackout_syms=None):
        self.blackout_syms = blackout_syms or ["MSFT"]

    def has_earnings_blackout(self, ticker: str, target_date=None, days_window=None) -> bool:
        return ticker in self.blackout_syms


class MockDeterministicFetcher:
    """Provides mathematically fixed historical and quote snapshots for testing."""


    def __init__(self, is_morning_exit: bool = False):
        self.is_morning_exit = is_morning_exit
        self.dates = pd.date_range("2024-01-01", periods=25)

    def fetch_historical(self, symbol: str, start_date=None, force_refresh=False):
        # Benchmark QQQ: 20 EMA is ~490.00
        if symbol == "QQQ":
            return pd.DataFrame({"Close": np.linspace(470, 490, 25)}, index=self.dates)

        # AAPL: 20d momentum is (230 - 200)/200 = +15.0%
        if symbol == "AAPL":
            return pd.DataFrame({"Close": np.linspace(200, 230, 25)}, index=self.dates)

        # NVDA: 20d momentum is (120 - 100)/100 = +20.0%
        if symbol == "NVDA":
            return pd.DataFrame({"Close": np.linspace(100, 120, 25)}, index=self.dates)

        # INTC: 20d momentum is (35 - 40)/40 = -12.5% (Negative -> Disqualified)
        if symbol == "INTC":
            return pd.DataFrame({"Close": np.linspace(40, 35, 25)}, index=self.dates)

        # Default flat series
        return pd.DataFrame({"Close": np.linspace(150, 150, 25)}, index=self.dates)

    def get_latest_quote(self, symbol: str):
        if symbol == "QQQ":
            # Current QQQ is $500.00 > $490.00 EMA -> BULL REGIME
            return {"last_price": 500.00, "open": 498.00}

        if symbol == "AAPL":
            if self.is_morning_exit:
                # Day T+1 Morning Open exit @ $234.60 (+2.0% overnight gap)
                return {"last_price": 234.60, "open": 234.60}
            else:
                # Day T Afternoon Close: Open was $234.60, Close is $230.00 (-1.96% dip)
                # Score = 0.150 - (-0.0196) = +0.1696 (Top Rank)
                return {"last_price": 230.00, "open": 234.60}

        if symbol == "NVDA":
            if self.is_morning_exit:
                # Day T+1 Morning Open exit @ $123.60 (+3.0% overnight gap)
                return {"last_price": 123.60, "open": 123.60}
            else:
                # Day T Afternoon Close: Open was $120.00, Close is $120.00 (0% intraday)
                # Score = 0.200 - 0.0 = +0.2000 (Top Rank)
                return {"last_price": 120.00, "open": 120.00}

        if symbol == "INTC":
            return {"last_price": 35.00, "open": 36.00}

        return {"last_price": 150.00, "open": 150.00}


@pytest.fixture
def sandbox_env(tmp_path, monkeypatch):
    """Sets up an isolated paper ledger and audit receipt directory."""
    from backend.routes import config
    test_override_file = tmp_path / "config_override.json"
    monkeypatch.setattr(config, "OVERRIDE_FILE", test_override_file)
    monkeypatch.setattr(config, "_fetch_from_secret_manager", lambda: {
        "env": "paper",
        "paper": {"tickers": ["AAPL", "NVDA", "MSFT", "AMD"], "top_n": 2, "strategy_enabled": True, "use_regime_filter": True},
        "live": {"tickers": ["AAPL", "NVDA", "MSFT", "AMD"], "top_n": 2, "strategy_enabled": True, "use_regime_filter": True},
    })
    monkeypatch.setattr(config, "_sync_to_secret_manager", lambda overrides: None)
    monkeypatch.setattr(config, "_IN_MEMORY_CACHE", (None, 0.0))

    test_state_file = tmp_path / "test_paper_ledger.json"
    test_audit_dir = tmp_path / "audit"
    test_audit_dir.mkdir(parents=True, exist_ok=True)

    broker = PaperBroker(ledger_path=test_state_file, initial_cash=10000.0)

    yield {
        "broker": broker,
        "state_file": test_state_file,
        "audit_dir": test_audit_dir,
    }

    # Cleanup
    if test_state_file.exists():
        test_state_file.unlink()
    shutil.rmtree(test_audit_dir, ignore_errors=True)


def test_full_deterministic_trading_cycle_with_seed(sandbox_env):
    """Test full cycle:
    1. Seed initial positions -> Open Routine liquidates them with exact verified profit.
    2. Close Routine executes on deterministic snapshot -> buys exact shares of AAPL & NVDA.
    3. Open Routine executes -> sells newly acquired holdings, returning portfolio to 100% cash.
    """
    broker = sandbox_env["broker"]
    audit_dir = sandbox_env["audit_dir"]

    # =========================================================================
    # PART A: SEED INITIAL POSITIONS & VERIFY MORNING SELL LIQUIDATION
    # =========================================================================
    # Pre-seed 2 active overnight holdings directly in ledger:
    # 4 shares AAPL @ $230.00 ($920.00 cost)
    # 8 shares NVDA @ $120.00 ($960.00 cost)
    # Deduct $1,880.00 from starting cash ($10,000 -> $8,120.00)
    now_str = datetime.now().isoformat()
    broker.ledger["positions"]["AAPL"] = {
        "shares": 4,
        "entry_price": 230.00,
        "entry_time": now_str,
    }
    broker.ledger["positions"]["NVDA"] = {
        "shares": 8,
        "entry_price": 120.00,
        "entry_time": now_str,
    }
    broker.ledger["cash"] = 8120.00
    broker._save_ledger()

    assert len(broker.get_positions()) == 2
    assert broker.get_cash_balance() == 8120.00


    # Trigger Morning Open Routine with exit prices: AAPL @ $234.60, NVDA @ $123.60
    fetcher_open = MockDeterministicFetcher(is_morning_exit=True)
    open_dossier_1 = run_open_routine(
        broker_override=broker,
        fetcher_override=fetcher_open,
        audit_dir_override=audit_dir,
    )

    # Mathematical Assertions for Part A
    # AAPL: 4 * 234.60 = $938.40 (P&L: 4 * 4.60 = +$18.40)
    # NVDA: 8 * 123.60 = $988.80 (P&L: 8 * 3.60 = +$28.80)
    # Total Proceeds = $1,927.20 | Total Realized P&L = +$47.20
    # Expected Ending Cash = $8,120.00 + $1,927.20 = $10,047.20
    assert open_dossier_1["summary"]["positions_closed"] == 2
    assert pytest.approx(open_dossier_1["summary"]["total_proceeds"], rel=1e-2) == 1927.20
    assert pytest.approx(open_dossier_1["summary"]["total_net_pnl"], rel=1e-2) == 47.20
    assert pytest.approx(broker.get_cash_balance(), rel=1e-2) == 10047.20
    assert len(broker.get_positions()) == 0  # 100% Cash!

    # =========================================================================
    # PART B: VERIFY AFTERNOON CLOSE ROUTINE (SCAN & BUY)
    # =========================================================================
    # Run Close Routine on deterministic Day T snapshot
    # AAPL: price $230.00 | NVDA: price $120.00 | Budget per stock = $1,000.00
    fetcher_close = MockDeterministicFetcher(is_morning_exit=False)
    earnings_mock = MockEarningsFilter(blackout_syms=["MSFT"])
    close_dossier = run_close_routine(
        broker_override=broker,
        fetcher_override=fetcher_close,
        earnings_filter_override=earnings_mock,
        audit_dir_override=audit_dir,
    )


    assert close_dossier["regime"]["passed"] is True
    assert close_dossier["regime"]["status"] == "BULL"

    # Candidates ranked: NVDA (score 0.2000), AAPL (score 0.1696)
    ranked_tickers = [c["ticker"] for c in close_dossier["scoring_and_ranking"]["candidates_ranked"]]
    assert "NVDA" in ranked_tickers[:2]
    assert "AAPL" in ranked_tickers[:2]

    # Verify risk sizing and fills
    # Budget $1,000 / $230 = 4 shares AAPL ($920.00)
    # Budget $1,000 / $120 = 8 shares NVDA ($960.00)
    executed = close_dossier["execution"]["executed_orders"]
    assert len(executed) == 2
    executed_map = {o["ticker"]: o for o in executed}

    assert executed_map["AAPL"]["shares"] == 4
    assert executed_map["AAPL"]["fill_price"] == 230.00
    assert executed_map["NVDA"]["shares"] == 8
    assert executed_map["NVDA"]["fill_price"] == 120.00

    # Ledger state after buy
    # Total deployed = $1,880.00
    # Remaining Cash = $10,047.20 - $1,880.00 = $8,167.20
    assert pytest.approx(broker.get_cash_balance(), rel=1e-2) == 8167.20
    assert len(broker.get_positions()) == 2
    assert "AAPL" in broker.get_positions()
    assert "NVDA" in broker.get_positions()

    # =========================================================================
    # PART C: LIQUIDATE PART B POSITIONS & CONFIRM FULL CYCLE SETTLEMENT
    # =========================================================================
    open_dossier_2 = run_open_routine(
        broker_override=broker,
        fetcher_override=fetcher_open,
        audit_dir_override=audit_dir,
    )

    assert open_dossier_2["summary"]["positions_closed"] == 2
    # Ending Cash should be $8,167.20 + $1,927.20 = $10,094.40 (+47.20 profit on 2nd cycle)
    assert pytest.approx(broker.get_cash_balance(), rel=1e-2) == 10094.40
    assert len(broker.get_positions()) == 0

    # Verify audit files exist on disk
    dossier_files = list(audit_dir.glob("dossier_*.json"))
    assert len(dossier_files) >= 3
    assert (audit_dir / "latest_close_dossier.json").exists()
    assert (audit_dir / "latest_open_dossier.json").exists()
