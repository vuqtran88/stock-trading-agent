"""Configuration & Universe settings API routes."""

import json
import os
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from fastapi import APIRouter, Depends, HTTPException

import logging
from config.settings import settings
from backend.models import ConfigUpdateRequest
from backend.routes.auth import get_current_user
from strategies.registry import list_available_strategies, AVAILABLE_STRATEGIES

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])

OVERRIDE_FILE = settings.DATA_DIR / "config_override.json"
GCP_CONFIG_SECRET_NAME = os.environ.get(
    "GCP_CONFIG_SECRET_NAME",
    "projects/stock-trading-agent-249477/secrets/strategy-runtime-config",
)
CACHE_TTL_SECONDS = 30.0

# In-memory cache: (cached_dict, timestamp)
_IN_MEMORY_CACHE: Tuple[Optional[Dict], float] = (None, 0.0)


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
    """Sync persistent configuration to GCP Secret Manager and prune obsolete versions."""
    try:
        from google.cloud import secretmanager
        client = secretmanager.SecretManagerServiceClient()
        payload_bytes = json.dumps(overrides, indent=2).encode("utf-8")
        new_ver = client.add_secret_version(
            parent=GCP_CONFIG_SECRET_NAME,
            payload={"data": payload_bytes},
        )
        logger.info("Persisted updated configuration to GCP Secret Manager.")
        try:
            for ver in client.list_secret_versions(request={"parent": GCP_CONFIG_SECRET_NAME}):
                if ver.name != new_ver.name and ver.state != secretmanager.SecretVersion.State.DESTROYED:
                    client.destroy_secret_version(request={"name": ver.name})
        except Exception as cleanup_err:
            logger.debug(f"Could not prune older config secret versions: {cleanup_err}")
    except Exception as e:
        logger.warning(f"Could not persist config to Secret Manager: {e}")


def _get_default_settings() -> Dict:
    """Return default strategy settings baseline from settings."""
    return {
        "tickers": list(settings.ticker_list),
        "max_position_size_usd": settings.MAX_POSITION_SIZE_USD,
        "live_pilot_budget_usd": settings.LIVE_PILOT_BUDGET_USD,
        "regime_ema_period": settings.REGIME_EMA_PERIOD,
        "top_n": 3,
        "active_strategy": "overnight_drift",
        "strategy_enabled": True,
        "use_regime_filter": True,
        "close_routine_time": "15:50",
        "open_routine_time": "09:28",
    }


def _raw_load_overrides(force_refresh: bool = False) -> Dict:
    """Load raw stored configuration mapping from Secret Manager (primary in cloud) or disk.
    
    Uses a 30-second TTL cache to prevent high-frequency Secret Manager API hits
    while guaranteeing that updates from other container instances or Secret Manager
    are picked up promptly without stale disk cache shadowing.
    """
    global _IN_MEMORY_CACHE
    now = time.time()
    cached_data, cached_ts = _IN_MEMORY_CACHE

    if not force_refresh and cached_data is not None and (now - cached_ts) < CACHE_TTL_SECONDS:
        return dict(cached_data)

    # 1. Primary: Try GCP Secret Manager first (source of truth in cloud)
    remote_cfg = _fetch_from_secret_manager()
    if remote_cfg:
        _IN_MEMORY_CACHE = (dict(remote_cfg), now)
        try:
            OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(OVERRIDE_FILE, "w") as f:
                json.dump(remote_cfg, f, indent=2)
        except Exception:
            pass
        return remote_cfg

    # 2. Fallback: Local disk cache (used in local development or if GCP unavailable)
    if OVERRIDE_FILE.exists():
        try:
            with open(OVERRIDE_FILE, "r") as f:
                disk_cfg = json.load(f)
                _IN_MEMORY_CACHE = (dict(disk_cfg), now)
                return disk_cfg
        except Exception:
            pass

    return {}


def get_active_overrides(env: Optional[str] = None) -> Dict:
    """Load user overrides for the active environment (or specific env if specified).
    
    Backward-compatible: returns a flat dictionary containing the environment's
    active settings, merged with top-level 'env'.
    """
    raw = _raw_load_overrides()
    active_env = (env or raw.get("env") or settings.ENV).lower()
    if active_env not in ("paper", "live"):
        active_env = "paper"

    # If raw already uses the separated schema {"paper": {...}, "live": {...}}
    defaults = _get_default_settings()
    if "paper" in raw or "live" in raw:
        env_cfg = dict(raw.get(active_env) or {})
        # Merge with defaults for missing keys
        resolved = {**defaults, **env_cfg}
        resolved["env"] = raw.get("env", active_env)
        return resolved

    # Legacy flat format migration: raw itself represents the current settings
    legacy_cfg = dict(raw) if raw else {}
    resolved = {**defaults, **legacy_cfg}
    resolved["env"] = legacy_cfg.get("env", active_env)
    return resolved


def get_all_environment_configs() -> Dict:
    """Return raw configuration dictionary containing active env and separate paper & live sections."""
    raw = _raw_load_overrides()
    active_env = (raw.get("env") or settings.ENV).lower()
    if active_env not in ("paper", "live"):
        active_env = "paper"

    defaults = _get_default_settings()

    if "paper" in raw or "live" in raw:
        paper_cfg = {**defaults, **(raw.get("paper") or {})}
        live_cfg = {**defaults, **(raw.get("live") or {})}
    else:
        # Migrate flat config into both paper and live
        base_overrides = {k: v for k, v in raw.items() if k != "env"}
        paper_cfg = {**defaults, **base_overrides}
        live_cfg = {**defaults, **base_overrides}

    return {
        "env": active_env,
        "paper": paper_cfg,
        "live": live_cfg,
    }


def save_active_overrides(overrides: Dict):
    """Persist user overrides to both local disk and GCP Secret Manager and update memory cache."""
    global _IN_MEMORY_CACHE
    _IN_MEMORY_CACHE = (dict(overrides), time.time())

    OVERRIDE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OVERRIDE_FILE, "w") as f:
        json.dump(overrides, f, indent=2)

    # Persist to GCP Secret Manager so redeployments never wipe settings
    _sync_to_secret_manager(overrides)


@router.get("")
def get_config(user: str = Depends(get_current_user)):
    """Fetch current configuration and target stock universe for active mode and both environments."""
    all_envs = get_all_environment_configs()
    current_env = all_envs["env"]
    active_cfg = all_envs[current_env]

    return {
        "env": current_env,
        "tickers": active_cfg.get("tickers") or settings.ticker_list,
        "benchmark": settings.BENCHMARK_TICKER,
        "max_position_size_usd": active_cfg.get("max_position_size_usd", settings.MAX_POSITION_SIZE_USD),
        "live_pilot_budget_usd": active_cfg.get("live_pilot_budget_usd", settings.LIVE_PILOT_BUDGET_USD),
        "regime_ema_period": active_cfg.get("regime_ema_period", settings.REGIME_EMA_PERIOD),
        "top_n": active_cfg.get("top_n", 3),
        "active_strategy": active_cfg.get("active_strategy", "overnight_drift"),
        "strategy_enabled": active_cfg.get("strategy_enabled", True),
        "use_regime_filter": active_cfg.get("use_regime_filter", True),
        "close_routine_time": active_cfg.get("close_routine_time", "15:50"),
        "open_routine_time": active_cfg.get("open_routine_time", "09:28"),
        "paper": all_envs["paper"],
        "live": all_envs["live"],
        "available_strategies": list_available_strategies(),
        "discord_configured": bool(settings.DISCORD_WEBHOOK_URL),
        "schwab_configured": bool(settings.SCHWAB_APP_KEY and settings.SCHWAB_APP_SECRET),
    }


@router.post("")
def update_config(req: ConfigUpdateRequest, user: str = Depends(get_current_user)):
    """Update strategy universe and parameters dynamically with isolated paper/live settings."""
    all_envs = get_all_environment_configs()

    # Determine which environment parameters we are editing
    # Priority: req.target_env -> req.env (if other fields present) -> active env
    target_env = req.target_env or req.env or all_envs["env"]
    if target_env not in ("paper", "live"):
        target_env = all_envs["env"]

    # If env toggle requested, update top-level active environment
    if req.env is not None:
        if req.env not in ("paper", "live"):
            raise HTTPException(status_code=400, detail="Environment must be 'paper' or 'live'")
        all_envs["env"] = req.env

    # Check if this request is updating strategy parameters
    has_param_updates = any([
        req.tickers is not None,
        req.max_position_size_usd is not None,
        req.live_pilot_budget_usd is not None,
        req.regime_ema_period is not None,
        req.top_n is not None,
        req.active_strategy is not None,
        req.strategy_enabled is not None,
        req.use_regime_filter is not None,
        req.close_routine_time is not None,
        req.open_routine_time is not None,
    ])

    if has_param_updates:
        target_cfg = all_envs[target_env]

        if req.tickers is not None:
            clean = [t.strip().upper() for t in req.tickers if t.strip()]
            if not clean:
                raise HTTPException(status_code=400, detail="Target universe cannot be empty.")
            target_cfg["tickers"] = clean

        if req.max_position_size_usd is not None:
            if req.max_position_size_usd <= 0:
                raise HTTPException(status_code=400, detail="Position size must be positive")
            target_cfg["max_position_size_usd"] = req.max_position_size_usd

        if req.live_pilot_budget_usd is not None:
            target_cfg["live_pilot_budget_usd"] = req.live_pilot_budget_usd

        if req.regime_ema_period is not None:
            target_cfg["regime_ema_period"] = req.regime_ema_period

        if req.top_n is not None:
            target_cfg["top_n"] = max(1, req.top_n)

        if req.active_strategy is not None:
            if req.active_strategy not in AVAILABLE_STRATEGIES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown strategy '{req.active_strategy}'. Available: {list(AVAILABLE_STRATEGIES.keys())}"
                )
            target_cfg["active_strategy"] = req.active_strategy

        if req.strategy_enabled is not None:
            target_cfg["strategy_enabled"] = bool(req.strategy_enabled)

        if req.use_regime_filter is not None:
            target_cfg["use_regime_filter"] = bool(req.use_regime_filter)

        if req.close_routine_time is not None:
            parts = req.close_routine_time.strip().split(":")
            if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
                raise HTTPException(status_code=400, detail="close_routine_time must be in 'HH:MM' 24-hour format")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise HTTPException(status_code=400, detail="close_routine_time contains invalid hour or minute")
            target_cfg["close_routine_time"] = f"{h:02d}:{m:02d}"

        if req.open_routine_time is not None:
            parts = req.open_routine_time.strip().split(":")
            if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()):
                raise HTTPException(status_code=400, detail="open_routine_time must be in 'HH:MM' 24-hour format")
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise HTTPException(status_code=400, detail="open_routine_time contains invalid hour or minute")
            target_cfg["open_routine_time"] = f"{h:02d}:{m:02d}"

        all_envs[target_env] = target_cfg

    save_active_overrides(all_envs)
    
    current_active = get_active_overrides()
    return {
        "success": True,
        "message": "Configuration updated successfully",
        "env": all_envs["env"],
        "target_env": target_env,
        "config": current_active,
        "all_envs": all_envs,
    }
