"""Phase 1 Verification Script.

Tests data downloading, parquet caching, fast quotes, and earnings calendar blackout filters.
"""

import sys
import logging
from pathlib import Path
from datetime import date

# Ensure project root is on sys.path even when run directly as python3 scripts/verify_phase1.py
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config.settings import settings
from data.fetcher import MarketDataFetcher
from data.earnings import EarningsFilter

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Phase1Verification")


def run_verification():
    logger.info("=" * 60)
    logger.info("PHASE 1 VERIFICATION GATE: DATA PIPELINE & EARNINGS FILTER")
    logger.info("=" * 60)

    # 1. Config Validation
    logger.info(f"Loaded Settings - Environment: {settings.ENV}")
    logger.info(f"Target Universe ({len(settings.ticker_list)} stocks): {settings.ticker_list}")
    logger.info(f"Benchmark: {settings.BENCHMARK_TICKER}")
    logger.info(f"Data Cache Directory: {settings.DATA_DIR}")

    # 2. Market Data Fetcher & Parquet Caching
    fetcher = MarketDataFetcher()
    test_tickers = [settings.BENCHMARK_TICKER, "AAPL"]

    logger.info("\n--- 1. Testing Historical Data Downloader & Parquet Cache ---")
    for sym in test_tickers:
        logger.info(f"Downloading historical daily data for {sym} (2023 to present)...")
        df = fetcher.fetch_historical(sym, start_date="2023-01-01")
        if df.empty:
            logger.error(f"FAILED: No historical data returned for {sym}!")
            sys.exit(1)
        logger.info(
            f"SUCCESS: {sym} returned {len(df)} bars. "
            f"Date range: {df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}. "
            f"Latest Close: ${df['Close'].iloc[-1]:.2f}"
        )

        # Check Cache File
        cache_path = fetcher._get_cache_filepath(sym, "1d")
        if cache_path.exists():
            logger.info(f"Parquet cache confirmed on disk: {cache_path} ({cache_path.stat().st_size / 1024:.1f} KB)")
        else:
            logger.error(f"FAILED: Cache file {cache_path} was not created!")
            sys.exit(1)

    logger.info("\n--- 2. Testing Real-Time Fast Quote ---")
    quote = fetcher.get_latest_quote("AAPL")
    logger.info(f"AAPL Live Snapshot: {quote}")
    assert quote.get("last_price", 0) > 0, "Last price must be positive!"

    # 3. Earnings Filter
    logger.info("\n--- 3. Testing Earnings Calendar & Blackout Filter ---")
    earnings_filter = EarningsFilter(blackout_days=1)
    universe = settings.ticker_list

    logger.info(f"Scanning earnings calendar across universe for reference date {date.today()}...")
    scan_results = earnings_filter.scan_universe_blackouts(universe)

    print("\n" + "=" * 65)
    print(f"{'Ticker':<8} | {'Blackout Tonight/Tmrw?':<24} | {'Next Known Earnings':<25}")
    print("-" * 65)

    for ticker, res in scan_results.items():
        is_blk = "YES (HOLD / SKIP)" if res["is_blackout"] else "NO (CLEAR)"
        upcoming = res["upcoming_earnings"]
        next_dt = str(upcoming[0]) if upcoming else "None found"
        print(f"{ticker:<8} | {is_blk:<24} | {next_dt:<25}")

    print("=" * 65 + "\n")

    logger.info("Phase 1 verification completed successfully!")


if __name__ == "__main__":
    run_verification()
