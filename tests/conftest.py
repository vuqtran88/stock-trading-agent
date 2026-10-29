"""Global pytest configuration and hermetic test isolation harness.

Enforces zero writes to production environments and transparent test isolation:
1. Intercepts and blocks ALL calls to GCP Secret Manager `add_secret_version` across the test suite,
   raising a RuntimeError if any unmocked code attempts to mutate production or test secrets.
2. Transparently rewrites GCP Secret Manager reads (`access_secret_version`) from production secret
   names (`strategy-runtime-config`, `schwab-token-data`, `strategy-capital-ledger`) to dedicated
   test secrets (`test-strategy-runtime-config`, `test-schwab-token-data`, `test-strategy-capital-ledger`).
   If GCP is unreachable or credentials are not present (e.g., in offline dev or Docker pre-flight builds),
   it gracefully falls back to synthetic in-memory fixtures.
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

# Production secret to test secret map
SECRET_NAME_REWRITE_MAP = {
    "strategy-runtime-config": "test-strategy-runtime-config",
    "schwab-token-data": "test-schwab-token-data",
    "strategy-capital-ledger": "test-strategy-capital-ledger",
}

SYNTHETIC_PAYLOAD_MAP = {
    "test-strategy-runtime-config": json.dumps(DEDICATED_TEST_RUNTIME_CONFIG).encode("utf-8"),
    "test-schwab-token-data": json.dumps(DEDICATED_TEST_SCHWAB_TOKEN).encode("utf-8"),
    "test-strategy-capital-ledger": json.dumps(DEDICATED_TEST_CAPITAL_LEDGER).encode("utf-8"),
}


@pytest.fixture(autouse=True)
def hermetic_test_isolation(tmp_path, monkeypatch):
    """Global autouse fixture protecting production from test interference.

    Guarantees:
    - Zero writes to Google Cloud Secret Manager (raises RuntimeError on unmocked calls).
    - Transparent redirect of reads from production secret names to `test-*` secrets.
    - Transparent fallback to synthetic fixtures when GCP credentials or network are absent.
    - Local `data_cache/` filesystem redirection to pytest `tmp_path`.
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

    # 2. Intercept and guard SecretManagerServiceClient
    real_sm_client_cls = None
    try:
        from google.cloud import secretmanager
        real_sm_client_cls = secretmanager.SecretManagerServiceClient
    except ImportError:
        pass

    if real_sm_client_cls:
        original_access = real_sm_client_cls.access_secret_version

        def safe_add_secret_version(self, request=None, *, parent=None, payload=None, **kwargs):
            err_msg = (
                f"CRITICAL TEST GUARD: Test attempted to call add_secret_version on GCP Secret Manager!\n"
                f"Target parent: {parent or (request.parent if request else 'unknown')}\n"
                f"Writing to production or test secrets during automated testing is strictly prohibited."
            )
            logger.critical(err_msg)
            raise RuntimeError(err_msg)

        def safe_access_secret_version(self, request=None, *, name=None, **kwargs):
            raw_name = name or (request.name if request else "")
            rewritten_name = raw_name

            # Rewrite production secret name to test secret name
            matched_test_secret = None
            for prod_name, test_name in SECRET_NAME_REWRITE_MAP.items():
                if f"/secrets/{prod_name}/" in raw_name or raw_name.endswith(f"/secrets/{prod_name}"):
                    rewritten_name = raw_name.replace(f"/secrets/{prod_name}", f"/secrets/{test_name}")
                    matched_test_secret = test_name
                    break
                elif f"/secrets/{test_name}/" in raw_name or raw_name.endswith(f"/secrets/{test_name}"):
                    matched_test_secret = test_name
                    break

            try:
                # Attempt live read from dedicated test secret in GCP
                if name:
                    return original_access(self, name=rewritten_name, **kwargs)
                else:
                    if request and hasattr(request, "name"):
                        request.name = rewritten_name
                    return original_access(self, request=request, **kwargs)
            except Exception as e:
                # If network or credentials fail, fallback gracefully to synthetic test payload
                logger.debug(f"Test Secret Manager read fell back to synthetic payload: {e}")
                if matched_test_secret and matched_test_secret in SYNTHETIC_PAYLOAD_MAP:
                    mock_resp = MagicMock()
                    mock_resp.payload.data = SYNTHETIC_PAYLOAD_MAP[matched_test_secret]
                    mock_resp.name = rewritten_name
                    return mock_resp
                raise e

        monkeypatch.setattr(
            real_sm_client_cls,
            "add_secret_version",
            safe_add_secret_version,
        )
        monkeypatch.setattr(
            real_sm_client_cls,
            "access_secret_version",
            safe_access_secret_version,
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
