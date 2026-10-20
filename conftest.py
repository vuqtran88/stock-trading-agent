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
    
    # Point test override file to temporary directory
    test_override_file = tmp_path / "config_override.json"
    monkeypatch.setattr(config_module, "OVERRIDE_FILE", test_override_file)
