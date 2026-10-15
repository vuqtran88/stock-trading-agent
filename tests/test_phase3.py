"""Unit tests for Phase 3 Risk Engine and Paper Broker."""

import pytest
from datetime import date
from unittest.mock import patch, MagicMock

from risk.risk_manager import RiskManager, OrderProposal
from execution.paper_broker import PaperBroker


def test_risk_manager_kill_switch(tmp_path):
    kill_file = tmp_path / ".kill_switch"
    risk_mgr = RiskManager(kill_switch_path=kill_file)

    assert not risk_mgr.is_kill_switch_active()

    # Activate
    risk_mgr.activate_kill_switch("Test Halt")
    assert risk_mgr.is_kill_switch_active()

    # Rejection check
    proposals = [OrderProposal(ticker="AAPL", target_usd=1000.0, current_price=150.0)]
    approved, rejections = risk_mgr.evaluate_proposals(
        proposals=proposals, available_cash=10000.0, current_portfolio_exposure=0.0
    )
    assert len(approved) == 0
    assert "KILL SWITCH IS ACTIVE" in rejections[0]

    # Deactivate
    risk_mgr.deactivate_kill_switch()
    assert not risk_mgr.is_kill_switch_active()


def test_risk_manager_position_and_exposure_caps(tmp_path):
    risk_mgr = RiskManager(
        max_position_size_usd=1000.0,
        max_portfolio_exposure_usd=1500.0,
        kill_switch_path=tmp_path / ".kill_switch",
    )

    # Mock earnings to avoid external network
    with patch.object(risk_mgr.earnings_filter, "has_earnings_blackout", return_value=False):
        # Proposal 1: requests $2000 in NVDA @ $100 -> capped at $1,000 (10 shares)
        # Proposal 2: requests $1000 in AAPL @ $100 -> only $500 room left in exposure -> capped at 5 shares
        proposals = [
            OrderProposal(ticker="NVDA", target_usd=2000.0, current_price=100.0),
            OrderProposal(ticker="AAPL", target_usd=1000.0, current_price=100.0),
        ]
        approved, rejections = risk_mgr.evaluate_proposals(
            proposals=proposals, available_cash=5000.0, current_portfolio_exposure=0.0
        )
        assert len(approved) == 2
        assert approved[0].quantity == 10  # $1,000 max pos
        assert approved[1].quantity == 5   # $500 remaining room


def test_paper_broker_buy_sell_accounting(tmp_path):
    ledger_file = tmp_path / "paper_ledger.json"
    broker = PaperBroker(ledger_path=ledger_file, initial_cash=10000.0)

    assert broker.get_cash_balance() == 10000.0
    assert len(broker.get_positions()) == 0

    # Execute Buy: 5 shares @ $200 = $1,000
    buy_rep = broker.buy("AAPL", shares=5, target_price=200.0)
    assert buy_rep.status == "FILLED"
    assert broker.get_cash_balance() == 9000.0
    assert broker.get_positions()["AAPL"].shares == 5
    assert broker.get_portfolio_exposure() == 1000.0

    # Execute Sell: 5 shares @ $210 = $1,050 (Profit: +$50)
    sell_rep = broker.sell("AAPL", shares=5, target_price=210.0)
    assert sell_rep.status == "FILLED"
    assert sell_rep.realized_pnl == 50.0
    assert broker.get_cash_balance() == 10050.0
    assert len(broker.get_positions()) == 0
    assert broker.get_portfolio_exposure() == 0.0
