"""Pydantic request and response models for the web dashboard."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    token: Optional[str] = None


class ConfigUpdateRequest(BaseModel):
    tickers: Optional[List[str]] = None
    env: Optional[str] = None  # "paper" or "live"
    max_position_size_usd: Optional[float] = None
    live_pilot_budget_usd: Optional[float] = None
    regime_ema_period: Optional[int] = None
    top_n: Optional[int] = None
    active_strategy: Optional[str] = None  # e.g. "overnight_drift"
    strategy_enabled: Optional[bool] = None  # Automated execution control (True = running, False = paused)
    close_routine_time: Optional[str] = None  # "HH:MM" e.g. "15:50"
    open_routine_time: Optional[str] = None  # "HH:MM" e.g. "09:28"


class ManualOrderRequest(BaseModel):
    ticker: str
    shares: int
    side: str = "BUY"  # "BUY" or "SELL"


class PositionItem(BaseModel):
    ticker: str
    shares: int
    entry_price: float
    current_price: float
    market_value: float
    unrealized_pnl: float
    unrealized_pnl_pct: float


class PortfolioResponse(BaseModel):
    env: str
    cash: float
    total_market_value: float
    total_portfolio_value: float
    total_exposure: float
    positions: List[PositionItem]
    kill_switch_active: bool
    regime_status: str  # "BULL" or "BEAR"
    qqq_price: float
    qqq_ema20: float


class BacktestRequest(BaseModel):
    start_date: str = "2023-01-01"
    end_date: Optional[str] = None
    top_n: int = 2
    regime_ema_period: int = 20
    use_regime_filter: bool = True
    use_earnings_filter: bool = True
    initial_capital: float = 10000.0


class TradeAuditItem(BaseModel):
    date: str
    ticker: str
    entry_close: float
    exit_date: str
    exit_open: float
    return_pct: float
    pnl_usd: float


class BacktestResponse(BaseModel):
    metrics: Dict[str, float]
    equity_curve: List[Dict[str, Any]]  # [{"date": "2023-01-03", "strategy": 10000.0, "benchmark": 10000.0}]
    trade_history: List[TradeAuditItem]

