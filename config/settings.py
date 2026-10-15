"""Configuration module for stock-trading-agent."""

from typing import List, Literal
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and trading strategy settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Runtime Environment
    ENV: Literal["backtest", "paper", "live"] = "paper"

    # Universe
    TICKERS: str = "AAPL,MSFT,NVDA,AMZN,GOOGL,META,TSLA"
    BENCHMARK_TICKER: str = "QQQ"

    # Strategy & Market Regime
    REGIME_EMA_PERIOD: int = 20

    # Risk Controls
    MAX_POSITION_SIZE_USD: float = 1000.0
    MAX_PORTFOLIO_EXPOSURE_USD: float = 5000.0
    MAX_DAILY_LOSS_USD: float = 250.0
    EARNINGS_BLACKOUT_DAYS: int = 1

    # Storage & Cache Directories
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data_cache"

    # Charles Schwab API Credentials (Phase 4)
    SCHWAB_APP_KEY: str = ""
    SCHWAB_APP_SECRET: str = ""
    SCHWAB_CALLBACK_URL: str = "https://127.0.0.1"
    SCHWAB_ACCOUNT_HASH: str = ""

    @property
    def ticker_list(self) -> List[str]:
        """Returns list of tickers stripped of whitespace."""
        return [t.strip().upper() for t in self.TICKERS.split(",") if t.strip()]

    @property
    def all_tickers(self) -> List[str]:
        """Returns strategy tickers plus benchmark ticker."""
        symbols = self.ticker_list
        bench = self.BENCHMARK_TICKER.strip().upper()
        if bench not in symbols:
            symbols = [bench] + symbols
        return symbols


settings = Settings()
