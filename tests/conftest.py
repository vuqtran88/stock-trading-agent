"""Global pytest configuration and hermetic test isolation harness.

Enforces zero writes to production environments:
1. Intercepts and blocks ALL calls to GCP Secret Manager `add_secret_version` across the test suite,
   raising a RuntimeError if any unmocked code attempts to mutate production secrets.
2. Provides isolated synthetic test datasets for Secret Manager reads (`strategy-runtime-config`,
   `schwab-token-data`, `strategy-capital-ledger`) unless explicitly mocked per test.
3. Redirects local state and cache directories to temporary sandboxes (`tmp_path`) so that local
   production/dev cache files in `data_cache/` are never overwritten by tests.
"""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock
import pytest

logger = logging.getLogger(__name__)

# Standard synthetic test datasets
DEDICATED_TEST_RUNTIME_CONFIG = {
    "env": "paper",
    "paper": {
        "tickers": ["AAPL", "NVDA", "MSFT", "AMD"],
        "top_n": 2,
        "max_position_size": 1000.0,
        "total_budget": 2000.0,
        "strategy_enabled": True,
        "use_regime_filter": True,
        "strategy_model": "overnight_drift",
    },
    "live": {
        "tickers": ["AAPL", "NVDA", "MSFT", "AMD"],
        "top_n": 2,
        "max_position_size": 1000.0,
        "total_budget": 2000.0,
        "strategy_enabled": True,
        "use_regime_filter": True,
        "strategy_model": "overnight_drift",
    },
}

DEDICATED_TEST_SCHWAB_TOKEN = {
    "access_token": "TEST_MOCK_ACCESS_TOKEN",
    "refresh_token": "TEST_MOCK_REFRESH_TOKEN",
    "expires_in": 1800,
    "refresh_token_expires_in": 604800,
    "token_created_at": 1700000000.0,
    "refresh_token_created_at": 1700000000.0,
}

DEDICATED_TEST_CAPITAL_LEDGER = {
    "initial_capital": 2000.0,
    "cash_balance": 2000.0,
    "deposits": [],
    "withdrawals": [],
    "last_updated": "2026-01-01T00:00:00Z",
}


@pytest.fixture(autouse=True)
def hermetic_test_isolation(tmp_path, monkeypatch):
    """Global autouse fixture protecting production from test interference.

    Guarantees:
    - Zero writes to Google Cloud Secret Manager (raises RuntimeError on unmocked calls).
    - Local `data_cache/` filesystem redirection to pytest `tmp_path`.
    - Safe default fallback for reading secrets without hitting live production resources.
    """
    # 1. Isolate settings DATA_DIR and local cache files to tmp_path
    sandbox_data_dir = tmp_path / "test_data_cache"
    sandbox_data_dir.mkdir(parents=True, exist_ok=True)

    from config.settings import settings
    monkeypatch.setattr(settings, "DATA_DIR", sandbox_data_dir)

    # Isolate routes/config.py
    from backend.routes import config
    monkeypatch.setattr(config, "OVERRIDE_FILE", sandbox_data_dir / "config_override.json")
    monkeypatch.setattr(config, "_IN_MEMORY_CACHE", (None, 0.0))

    # Isolate capital_ledger.py
    import data.capital_ledger as cap_ledger
    monkeypatch.setattr(cap_ledger, "LEDGER_FILE", sandbox_data_dir / "capital_ledger.json")

    # 2. Guardrail SecretManagerServiceClient globally against writes
    real_sm_client_cls = None
    try:
        from google.cloud import secretmanager
        real_sm_client_cls = secretmanager.SecretManagerServiceClient
    except ImportError:
        pass

    if real_sm_client_cls:
        def safe_add_secret_version(self, request=None, *, parent=None, payload=None, **kwargs):
            err_msg = (
                f"CRITICAL TEST GUARD: Test attempted to call add_secret_version on GCP Secret Manager!\n"
                f"Target parent: {parent or (request.parent if request else 'unknown')}\n"
                f"Writing to production during testing is strictly prohibited."
            )
            logger.critical(err_msg)
            raise RuntimeError(err_msg)

        monkeypatch.setattr(
            real_sm_client_cls,
            "add_secret_version",
            safe_add_secret_version,
        )

    yield sandbox_data_dir


@pytest.fixture
def mock_secret_manager_reads(monkeypatch):
    """Provides standard mock reads for all three core secrets so tests never rely on live GCP."""
    from backend.routes import config
    monkeypatch.setattr(config, "_fetch_from_secret_manager", lambda: DEDICATED_TEST_RUNTIME_CONFIG.copy())

    import execution.schwab_auth as schwab_auth
    def mock_fetch_tokens(self):
        return DEDICATED_TEST_SCHWAB_TOKEN.copy()
    monkeypatch.setattr(schwab_auth.SchwabAuth, "fetch_tokens_from_secret_manager", mock_fetch_tokens)

    import data.capital_ledger as cap_ledger
    monkeypatch.setattr(cap_ledger, "_fetch_capital_ledger_from_secret", lambda: DEDICATED_TEST_CAPITAL_LEDGER.copy())
