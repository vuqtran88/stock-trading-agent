"""Global pytest configuration and fixtures for hermetic test execution."""

import pytest


@pytest.fixture(autouse=True)
def isolate_test_environment(monkeypatch, tmp_path):
    """Ensure automated tests run in a completely isolated environment:
    1. Prevent any write/sync to production GCP Secret Manager.
    2. Prevent reading production GCP Secret Manager during test sessions.
    3. Redirect OVERRIDE_FILE to temporary isolated file for testing config updates.
    """
    import backend.routes.config as config_module

    # Mock secret manager read & sync during test sessions
    monkeypatch.setattr(config_module, "_sync_to_secret_manager", lambda overrides: None)
    monkeypatch.setattr(config_module, "_fetch_from_secret_manager", lambda: None)
    
    # Point test override file to temporary directory and write default paper test config
    test_override_file = tmp_path / "config_override.json"
    import json
    with open(test_override_file, "w") as f:
        json.dump({"env": "paper", "tickers": ["AAPL", "NVDA"]}, f)
    monkeypatch.setattr(config_module, "OVERRIDE_FILE", test_override_file)

    # Mock capital ledger secret manager operations
    import data.capital_ledger as cap_module
    monkeypatch.setattr(cap_module, "_sync_capital_ledger_to_secret", lambda ledger: None)
    monkeypatch.setattr(cap_module, "_fetch_capital_ledger_from_secret", lambda: None)
    monkeypatch.setattr(cap_module, "LEDGER_FILE", tmp_path / "capital_ledger.json")

    # Isolate PaperBroker ledger to clean temporary test ledger
    import execution.paper_broker as paper_module
    orig_init = paper_module.PaperBroker.__init__
    test_paper_ledger = tmp_path / "paper_ledger.json"
    monkeypatch.setattr(
        paper_module.PaperBroker,
        "__init__",
        lambda self, ledger_path=None, initial_cash=10000.0, data_fetcher=None: orig_init(
            self, ledger_path=ledger_path or test_paper_ledger, initial_cash=initial_cash, data_fetcher=data_fetcher
        ),
    )
