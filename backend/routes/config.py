"""Configuration & Universe settings API routes."""

import json
from pathlib import Path
from typing import Dict, Optional
from fastapi import APIRouter, Depends, HTTPException

import logging
from config.settings import settings
from backend.models import ConfigUpdateRequest
from backend.routes.auth import get_current_user
from strategies.registry import list_available_strategies, AVAILABLE_STRATEGIES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

OVERRIDE_FILE = settings.DATA_DIR / "config_override.json"
GCP_CONFIG_SECRET_NAME = "projects/stock-trading-agent-249477/secrets/strategy-runtime-config"


def _fetch_from_secret_manager() -> Optional[Dict]:
    """Fetch persistent configuration from GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        name = f"{GCP_CONFIG_SECRET_NAME}/versions/latest"
        resp = client.access_secret_version(name=name)
        payload = resp.payload.data.decode("utf-8")
        if payload:
            data = json.loads(payload)
            logger.info("Loaded persistent configuration from GCP Secret Manager.")
            return data
    except Exception as e:
        logger.debug(f"Secret Manager config access skipped or failed: {e}")
    return None


def _sync_to_secret_manager(overrides: Dict):
    """Sync persistent configuration to GCP Secret Manager."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        payload_bytes = json.dumps(overrides, indent=2).encode("utf-8")
        client.add_secret_version(
            parent=GCP_CONFIG_SECRET_NAME,
            payload={"data": payload_bytes},
        )
        logger.info("Persisted updated configuration to GCP Secret Manager.")
    except Exception as e:
        logger.warning(f"Could not persist config to Secret Manager: {e}")


def get_active_overrides() -> Dict:
    """Load user overrides saved from web dashboard (from local file or Secret Manager)."""
    # 1. Try local disk cache
    if OVERRIDE_FILE.exists():
        try:
            with open(OVERRIDE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass

    # 2. Fallback to GCP Secret Manager (across container cold starts / redeployments)
    remote_cfg = _fetch_from_secret_manager()
    if remote_cfg:
        # Cache locally to container
        try:
            OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OVERRIDE_FILE, "w") as f:
                json.dump(remote_cfg, f, indent=2)
        except Exception:
            pass
        return remote_cfg

    return {}


def save_active_overrides(overrides: Dict):
    """Persist user overrides to both local disk and GCP Secret Manager."""
    OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OVERRIDE_FILE, "w") as f:
        json.dump(overrides, f, indent=2)

    # Persist to GCP Secret Manager so redeployments never wipe settings
    _sync_to_secret_manager(overrides)


@router.get("")
def get_config(user: str = Depends(get_current_user)):
    """Fetch current configuration and target stock universe."""
    overrides = get_active_overrides()
    
    current_tickers = overrides.get("tickers") or settings.ticker_list
    current_env = overrides.get("env") or settings.ENV
    max_pos = overrides.get("max_position_size_usd", settings.MAX_POSITION_SIZE_USD)
    pilot_budget = overrides.get("live_pilot_budget_usd", settings.LIVE_PILOT_BUDGET_USD)
    regime_ema = overrides.get("regime_ema_period", settings.REGIME_EMA_PERIOD)
    top_n = overrides.get("top_n", 2)
    active_strategy = overrides.get("active_strategy", "overnight_drift")
    strategy_enabled = overrides.get("strategy_enabled", True)
    use_regime_filter = overrides.get("use_regime_filter", True)
    close_routine_time = overrides.get("close_routine_time", "15:50")
    open_routine_time = overrides.get("open_routine_time", "09:28")

    return {
        "env": current_env,
        "tickers": current_tickers,
        "benchmark": settings.BENCHMARK_TICKER,
        "max_position_size_usd": max_pos,
        "live_pilot_budget_usd": pilot_budget,
        "regime_ema_period": regime_ema,
        "top_n": top_n,
        "active_strategy": active_strategy,
        "strategy_enabled": strategy_enabled,
        "use_regime_filter": use_regime_filter,
        "close_routine_time": close_routine_time,
        "open_routine_time": open_routine_time,
        "available_strategies": list_available_strategies(),
        "discord_configured": bool(settings.DISCORD_WEBHOOK_URL),
        "schwab_configured": bool(settings.SCHWAB_APP_KEY and settings.SCHWAB_APP_SECRET),
    }


@router.post("")
def update_config(req: ConfigUpdateRequest, user: str = Depends(get_current_user)):
    """Update strategy universe and parameters dynamically."""
    overrides = get_active_overrides()

    if req.tickers is not None:
        clean = [t.strip().upper() for t in req.tickers if t.strip()]
        if not clean:
            raise HTTPException(status_code=400, detail="Target universe cannot be empty.")
        overrides["tickers"] = clean

    if req.env is not None:
        if req.env not in ("paper", "live"):
            raise HTTPException(status_code=400, detail="Environment must be 'paper' or 'live'")
        overrides["env"] = req.env

    if req.max_position_size_usd is not None:
        if req.max_position_size_usd <= 0:
            raise HTTPException(status_code=400, detail="Position size must be positive")
        overrides["max_position_size_usd"] = req.max_position_size_usd

    if req.live_pilot_budget_usd is not None:
        overrides["live_pilot_budget_usd"] = req.live_pilot_budget_usd

    if req.regime_ema_period is not None:
        overrides["regime_ema_period"] = req.regime_ema_period

    if req.top_n is not None:
        overrides["top_n"] = max(1, req.top_n)

    if req.active_strategy is not None:
        if req.active_strategy not in AVAILABLE_STRATEGIES:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown strategy '{req.active_strategy}'. Available: {list(AVAILABLE_STRATEGIES.keys())}"
            )
        overrides["active_strategy"] = req.active_strategy

    if req.strategy_enabled is not None:
        overrides["strategy_enabled"] = bool(req.strategy_enabled)

    if req.use_regime_filter is not None:
        overrides["use_regime_filter"] = bool(req.use_regime_filter)

    if req.close_routine_time is not None:
        # Validate HH:MM format
        parts = req.close_routine_time.strip().split(":")
        if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
            raise HTTPException(status_code=400, detail="close_routine_time must be in 'HH:MM' 24-hour format")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise HTTPException(status_code=400, detail="close_routine_time contains invalid hour or minute")
        overrides["close_routine_time"] = f"{h:02d}:{m:02d}"

    if req.open_routine_time is not None:
        # Validate HH:MM format
        parts = req.open_routine_time.strip().split(":")
        if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
            raise HTTPException(status_code=400, detail="open_routine_time must be in 'HH:MM' 24-hour format")
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise HTTPException(status_code=400, detail="open_routine_time contains invalid hour or minute")
        overrides["open_routine_time"] = f"{h:02d}:{m:02d}"

    save_active_overrides(overrides)
    return {"success": True, "message": "Configuration updated successfully", "config": overrides}
