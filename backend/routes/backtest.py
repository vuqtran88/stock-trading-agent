"""Backtesting and trade audit API router."""

from datetime import datetime, timedelta
from typing import Dict, List
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from config.settings import settings
from data.fetcher import MarketDataFetcher
from data.earnings import EarningsFilter
from strategies.overnight_strategy import OvernightDriftStrategy
from backtesting.engine import BacktestEngine
from backend.models import BacktestRequest, BacktestResponse, TradeAuditItem
from backend.routes.auth import get_current_user
from backend.routes.config import get_active_overrides

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

fetcher = MarketDataFetcher()
earnings_filter = EarningsFilter()


@router.post("", response_model=BacktestResponse)
def run_custom_backtest(req: BacktestRequest, user: str = Depends(get_current_user)):
    """Run an on-demand backtest simulation across a custom date window."""
    if req.tickers and len(req.tickers) > 0:
        # User specified an isolated universe specifically for this backtest
        tickers = [t.strip().upper() for t in req.tickers if t.strip()]
    else:
        overrides = get_active_overrides()
        tickers = overrides.get("tickers") or settings.ticker_list
    bench_symbol = settings.BENCHMARK_TICKER

    # 1. Fetch data
    bench_df = fetcher.fetch_historical(bench_symbol, start_date=req.start_date, end_date=req.end_date)
    if bench_df.empty:
        raise HTTPException(status_code=400, detail=f"No data found for benchmark {bench_symbol} in range.")

    market_data = {}
    earnings_dates = {}
    for sym in tickers:
        df = fetcher.fetch_historical(sym, start_date=req.start_date, end_date=req.end_date)
        if not df.empty:
            market_data[sym] = df
            earnings_dates[sym] = earnings_filter.get_upcoming_earnings_dates(sym)

    if not market_data:
        raise HTTPException(status_code=400, detail="No valid historical data found for target stocks.")

    # 2. Run Strategy
    strategy = OvernightDriftStrategy(
        regime_ema_period=req.regime_ema_period,
        momentum_period=20,
        top_n=req.top_n,
        use_regime_filter=req.use_regime_filter,
        use_earnings_filter=req.use_earnings_filter,
    )

    engine = BacktestEngine(initial_capital=req.initial_capital, slippage_bps=3.0)
    results = engine.run(
        strategy=strategy,
        market_data=market_data,
        benchmark_data=bench_df,
        earnings_dates=earnings_dates,
    )

    # 3. Format equity curve for frontend chart
    equity_curve_data = []
    strat_eq = results["equity_curve"]
    bench_eq = results["benchmark_equity"]

    for dt, val in strat_eq.items():
        dt_str = dt.strftime("%Y-%m-%d")
        b_val = float(bench_eq.get(dt, req.initial_capital))
        equity_curve_data.append({
            "date": dt_str,
            "strategy": round(float(val), 2),
            "benchmark": round(b_val, 2),
        })

    # 4. Extract trade-by-trade audit items
    weights_df = results["weights"]
    common_dates = bench_df.index
    trade_items: List[TradeAuditItem] = []

    for i in range(len(common_dates) - 1):
        dt = common_dates[i]
        next_dt = common_dates[i + 1]

        row_w = weights_df.loc[dt]
        active = row_w[row_w > 0].index.tolist()

        for sym in active:
            if sym in market_data and dt in market_data[sym].index and next_dt in market_data[sym].index:
                c_p = float(market_data[sym].loc[dt, "Close"])
                o_p = float(market_data[sym].loc[next_dt, "Open"])
                ret_pct = ((o_p - c_p) / c_p) * 100.0
                dollar_pnl = (req.initial_capital * (1.0 / len(active))) * (ret_pct / 100.0)

                trade_items.append(
                    TradeAuditItem(
                        date=dt.strftime("%Y-%m-%d"),
                        ticker=sym,
                        entry_close=round(c_p, 2),
                        exit_date=next_dt.strftime("%Y-%m-%d"),
                        exit_open=round(o_p, 2),
                        return_pct=round(ret_pct, 2),
                        pnl_usd=round(dollar_pnl, 2),
                    )
                )

    return BacktestResponse(
        metrics=results["metrics"],
        equity_curve=equity_curve_data,
        trade_history=list(reversed(trade_items)),  # latest first
    )
