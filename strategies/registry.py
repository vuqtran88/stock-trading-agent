"""Strategy registry for pluggable quantitative trading strategies.

Provides metadata and factory constructors for both live/paper automated routines
and historical backtesting engines.
"""

from typing import Dict, List, Any
from strategies.base import BaseStrategy
from strategies.overnight_strategy import OvernightDriftStrategy


AVAILABLE_STRATEGIES: Dict[str, Dict[str, Any]] = {
    "overnight_drift": {
        "id": "overnight_drift",
        "name": "Overnight Drift Anomaly",
        "description": "Enters high-momentum dips at Market Close (3:50 PM ET) and exits at Market Open (9:28 AM ET). Captures the structural overnight market drift.",
        "author": "System Built-in",
        "status": "active",  # active, beta, coming_soon
        "schedule_type": "two_phase",  # open & close routine scans
        "default_open_time": "09:28",
        "default_close_time": "15:50",
    },
    "intraday_momentum": {
        "id": "intraday_momentum",
        "name": "Intraday Momentum Breakout",
        "description": "Scans morning opening ranges (ORB) and rides intraday trend breakouts, closing before market settlement.",
        "author": "System Built-in",
        "status": "coming_soon",
        "schedule_type": "intraday",
        "default_open_time": "09:45",
        "default_close_time": "15:45",
    },
    "mean_reversion": {
        "id": "mean_reversion",
        "name": "Bollinger Mean Reversion",
        "description": "Identifies extreme 2-standard-deviation oversold conditions during market sessions with dynamic profit targets.",
        "author": "System Built-in",
        "status": "coming_soon",
        "schedule_type": "swing",
        "default_open_time": "10:00",
        "default_close_time": "15:30",
    },
}


def list_available_strategies() -> List[Dict[str, Any]]:
    """Return catalog of available strategies for UI selection and configuration."""
    return list(AVAILABLE_STRATEGIES.values())


def get_strategy_instance(strategy_id: str, **kwargs) -> BaseStrategy:
    """Instantiate a strategy by ID with optional parameters."""
    if strategy_id == "overnight_drift":
        return OvernightDriftStrategy(
            regime_ema_period=kwargs.get("regime_ema_period", 20),
            top_n=kwargs.get("top_n", 2),
            use_regime_filter=kwargs.get("use_regime_filter", True),
            use_earnings_filter=kwargs.get("use_earnings_filter", True),
        )
    else:
        raise ValueError(f"Strategy '{strategy_id}' is not yet implemented or available for live execution.")
