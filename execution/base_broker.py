"""Abstract Base Broker Interface."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from pydantic import BaseModel


class Position(BaseModel):
    """Represents an open holding."""
    ticker: str
    shares: int
    entry_price: float
    entry_time: str
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None


class ExecutionReport(BaseModel):
    """Result of an executed order."""
    ticker: str
    side: str  # BUY or SELL
    shares: int
    fill_price: float
    total_value: float
    timestamp: str
    status: str = "FILLED"
    realized_pnl: Optional[float] = None


class BaseBroker(ABC):
    """Abstract interface for all brokerage connections (Paper, Schwab, etc.)."""

    @abstractmethod
    def get_cash_balance(self) -> float:
        """Returns current available settled cash."""
        pass

    @abstractmethod
    def get_positions(self) -> Dict[str, Position]:
        """Returns map of active open positions."""
        pass

    @abstractmethod
    def buy(self, ticker: str, shares: int) -> ExecutionReport:
        """Execute buy order."""
        pass

    @abstractmethod
    def sell(self, ticker: str, shares: int) -> ExecutionReport:
        """Execute sell order."""
        pass

    @abstractmethod
    def flatten_all_positions(self) -> List[ExecutionReport]:
        """Liquidate all open positions to 100% cash."""
        pass
