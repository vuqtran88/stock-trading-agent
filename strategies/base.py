"""Base strategy interface."""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import pandas as pd


class BaseStrategy(ABC):
    """Abstract base class for trading strategies."""

    @abstractmethod
    def generate_signals(
        self,
        market_data: Dict[str, pd.DataFrame],
        benchmark_data: pd.DataFrame,
        earnings_dates: Optional[Dict[str, List]] = None,
    ) -> pd.DataFrame:
        """Generate daily signals/allocations across historical data.

        Returns:
            pd.DataFrame indexed by Date with columns representing target allocations or signals.
        """
        pass
