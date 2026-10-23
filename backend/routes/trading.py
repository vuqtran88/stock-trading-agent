"""Trading operations, live portfolio, manual orders, and routine trigger routes."""

import json
import logging
from datetime import datetime
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException

logger = logging.getLogger(__name__)


from config.settings import settings
from data.fetcher import MarketDataFetcher
from data.capital_ledger import CapitalLedgerManager
from risk.risk_manager import RiskManager
from execution.paper_broker import PaperBroker
from execution.schwab_broker import SchwabBroker
from backend.models import (
    PortfolioResponse,
    PositionItem,
    ManualOrderRequest,
)
from backend.routes.auth import get_current_user
from backend.routes.config import get_active_overrides

router = APIRouter(prefix="/api/trading", tags=["trading"])

fetcher = MarketDataFetcher()
risk_mgr = RiskManager()

# Throttle external Schwab transaction queries so 6-second dashboard polls don't bottleneck
_LAST_SCHWAB_TX_SYNC: float = 0.0
SCHWAB_TX_SYNC_INTERVAL_SEC: float = 300.0  # Check external bank transfers at most every 5 minutes


def record_server_activity(text: str, event_type: str = "info", source: str = "SCHEDULED"):
    """Persist an execution activity to disk so web dashboard can display both scheduled & manual events."""
    try:
        settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
        logs = []
        if ACTIVITY_LOG_FILE.exists():
            with open(ACTIVITY_LOG_FILE, "r") as f:
                logs = json.load(f)
        
        now = datetime.now()
        time_str = now.strftime("%I:%M:%S %p")
        badge = "[CRON]" if source.upper() == "SCHEDULED" else "[MANUAL]"
        entry = {
            "id": f"{int(now.timestamp() * 1000)}-{len(logs)}",
            "time": time_str,
            "text": f"{badge} {text}",
            "type": event_type,
            "source": source.upper(),
            "timestamp": now.isoformat(),
        }
        # Prepend new entry, retain up to 300 activities
        logs = [entry] + logs[:299]
        with open(ACTIVITY_LOG_FILE, "w") as f:
            json.dump(logs, f, indent=2)
    except Exception as e:
        print(f"Error persisting server activity log: {e}")


def get_current_broker():
    """Instantiate active broker based on overrides or settings."""
    overrides = get_active_overrides()
    env = overrides.get("env") or settings.ENV
    if env == "live":
        return SchwabBroker()
    return PaperBroker()


@router.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(user: str = Depends(get_current_user)):
    """Fetch live account balance, active holdings, market regime, and P&L."""
    overrides = get_active_overrides()
    env = overrides.get("env") or settings.ENV
    broker = get_current_broker()

    try:
        cash = broker.get_cash_balance()
        positions_map = broker.get_positions()
    except Exception as e:
        logger.error(f"Failed to fetch live balance/positions from {broker.__class__.__name__}: {e}")
        cash = 0.0
        positions_map = {}

    # Calculate live current prices & unrealized P&L
    position_items: List[PositionItem] = []
    total_market_val = 0.0

    for sym, pos in positions_map.items():
        quote = fetcher.get_latest_quote(sym)
        last_price = quote.get("last_price") or pos.entry_price
        mkt_val = pos.shares * last_price
        cost_basis = pos.shares * pos.entry_price
        unrealized = mkt_val - cost_basis
        unrealized_pct = (unrealized / cost_basis * 100.0) if cost_basis > 0 else 0.0

        total_market_val += mkt_val
        position_items.append(
            PositionItem(
                ticker=sym,
                shares=pos.shares,
                entry_price=pos.entry_price,
                current_price=last_price,
                market_value=mkt_val,
                unrealized_pnl=unrealized,
                unrealized_pnl_pct=unrealized_pct,
            )
        )

    # Market Regime check on QQQ
    bench_sym = settings.BENCHMARK_TICKER
    bench_hist = fetcher.fetch_historical(bench_sym, start_date="2024-01-01")
    bench_quote = fetcher.get_latest_quote(bench_sym)
    
    qqq_p = float(bench_quote.get("last_price", 0.0))
    ema_period = overrides.get("regime_ema_period", settings.REGIME_EMA_PERIOD)
    qqq_ema = 0.0
    if not bench_hist.empty:
        qqq_ema = float(bench_hist["Close"].ewm(span=ema_period, adjust=False).mean().iloc[-1])

    regime_status = "BULL" if qqq_p >= qqq_ema else "BEAR"

    if hasattr(broker, "get_portfolio_exposure"):
        exposure = broker.get_portfolio_exposure()
    else:
        exposure = sum(p.shares * p.entry_price for p in positions_map.values())

    use_regime_filter = overrides.get("use_regime_filter", True)

    # 4. Ingest Cash Flows & Compute True Strategy P&L (Throttled & Incremental)
    global _LAST_SCHWAB_TX_SYNC
    total_equity = cash + total_market_val
    ledger_mgr = CapitalLedgerManager(env=env)

    if env == "live" and isinstance(broker, SchwabBroker):
        now_ts = datetime.now().timestamp()
        has_cash_flows = bool(ledger_mgr.data.get("cash_flows"))
        time_elapsed = now_ts - _LAST_SCHWAB_TX_SYNC

        # Only query Schwab external transfers if throttled interval elapsed or ledger is completely uninitialized
        if (not has_cash_flows) or (time_elapsed >= SCHWAB_TX_SYNC_INTERVAL_SEC):
            try:
                start_dt = ledger_mgr.get_sync_start_date()
                txs = broker.get_transactions(start_date=start_dt, types="JOURNAL,ACH_RECEIPT,ACH_DISBURSEMENT,WIRE_IN,WIRE_OUT")
                if txs:
                    ledger_mgr.sync_schwab_transactions(txs, current_equity=total_equity)
                _LAST_SCHWAB_TX_SYNC = now_ts
            except Exception as e:
                logger.warning(f"Error during incremental Schwab transaction sync: {e}")

    cap_metrics = ledger_mgr.get_metrics(current_total_equity=total_equity)

    return PortfolioResponse(
        env=env,
        cash=cash,
        total_market_value=total_market_val,
        total_portfolio_value=total_equity,
        total_exposure=exposure,
        positions=position_items,
        kill_switch_active=risk_mgr.is_kill_switch_active(),
        regime_status=regime_status,
        qqq_price=qqq_p,
        qqq_ema20=qqq_ema,
        regime_ema_period=ema_period,
        use_regime_filter=use_regime_filter,
        net_contributed_capital=cap_metrics["net_contributed_capital"],
        true_strategy_pnl=cap_metrics["true_strategy_pnl"],
        true_strategy_pnl_pct=cap_metrics["true_strategy_pnl_pct"],
        twr_pct=cap_metrics["twr_pct"],
        cash_flows=cap_metrics["cash_flows"],
    )


@router.post("/order")
def execute_manual_order(req: ManualOrderRequest, user: str = Depends(get_current_user)):
    """Manually place a custom Buy or Sell order (Paper mode only for safety)."""
    overrides = get_active_overrides()
    env = overrides.get("env") or settings.ENV

    if env == "live":
        raise HTTPException(status_code=400, detail="Manual custom orders are restricted to Paper mode for safety.")

    broker = PaperBroker()
    ticker = req.ticker.upper().strip()

    if req.side.upper() == "BUY":
        try:
            report = broker.buy(ticker=ticker, shares=req.shares)
            return {"success": True, "report": report.model_dump()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif req.side.upper() == "SELL":
        try:
            report = broker.sell(ticker=ticker, shares=req.shares)
            return {"success": True, "report": report.model_dump()}
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    else:
        raise HTTPException(status_code=400, detail="Side must be 'BUY' or 'SELL'")


@router.post("/run-close-routine")
def trigger_close_routine(user: str = Depends(get_current_user)):
    """Trigger the 3:50 PM ET afternoon buy routine scan and execution."""
    from scripts.run_close_routine import run_close_routine
    source = "SCHEDULED" if user == "cron-scheduler" else "MANUAL"
    try:
        dossier = run_close_routine(trigger_source=source)
        regime = dossier.get("regime", {}).get("status", "BULL") if dossier else "BULL"
        orders = dossier.get("execution", {}).get("executed_orders", []) if dossier else []
        orders_count = len(orders)
        
        if orders_count > 0:
            order_summary = ", ".join(f"{o.get('shares')} {o.get('ticker')}" for o in orders)
            activity_msg = f"Afternoon Close Routine ({regime}): {orders_count} buy order(s) placed ({order_summary})."
            event_type = "success"
        else:
            activity_msg = f"Afternoon Close Routine ({regime}): 0 buy order(s) placed (Account 100% Cash)."
            event_type = "info"

        record_server_activity(
            activity_msg,
            event_type=event_type,
            source=source,
        )
        return {"success": True, "message": activity_msg, "dossier": dossier}
    except Exception as e:
        record_server_activity(f"Afternoon Close Routine Failed: {e}", event_type="error", source=source)
        raise HTTPException(status_code=500, detail=f"Error executing close routine: {e}")


@router.post("/run-open-routine")
def trigger_open_routine(user: str = Depends(get_current_user)):
    """Trigger the 9:28 AM ET morning sell routine to liquidate overnight holdings."""
    from scripts.run_open_routine import run_open_routine
    source = "SCHEDULED" if user == "cron-scheduler" else "MANUAL"
    try:
        dossier = run_open_routine(trigger_source=source)
        liquidations = len(dossier.get("liquidated_positions", [])) if dossier else 0
        pnl = dossier.get("total_net_pnl", 0.0) if dossier else 0.0
        msg = f"Morning Open Routine: Liquidated {liquidations} position(s). P&L: ${pnl:+,.2f}." if liquidations > 0 else "Morning Open Routine: 0 positions to liquidate (Account 100% Cash)."
        record_server_activity(
            msg,
            event_type="success" if liquidations > 0 else "info",
            source=source,
        )
        return {"success": True, "message": "Open routine executed successfully.", "dossier": dossier}
    except Exception as e:
        record_server_activity(f"Morning Open Routine Failed: {e}", event_type="error", source=source)
        raise HTTPException(status_code=500, detail=f"Error executing open routine: {e}")


@router.post("/seed-test-positions")
def seed_test_positions(user: str = Depends(get_current_user)):
    """Seed test holdings into paper ledger for testing morning liquidations."""
    from datetime import datetime
    broker = get_current_broker()
    if not isinstance(broker, PaperBroker):
        raise HTTPException(status_code=400, detail="Seeding only permitted in PAPER trading mode.")

    now_str = datetime.now().isoformat()
    broker.ledger["positions"]["AAPL"] = {"shares": 4, "entry_price": 230.00, "entry_time": now_str}
    broker.ledger["positions"]["NVDA"] = {"shares": 8, "entry_price": 120.00, "entry_time": now_str}
    broker.ledger["cash"] = 8120.00
    broker._save_ledger()

    return {
        "success": True,
        "message": "Seeded 4 shares AAPL ($230.00) & 8 shares NVDA ($120.00) into paper portfolio.",
        "positions": list(broker.ledger["positions"].keys()),
        "cash": broker.get_cash_balance(),
    }


@router.post("/reset-paper-ledger")
def reset_paper_ledger(user: str = Depends(get_current_user)):
    """Reset the paper ledger back to initial state ($10,000 cash, 0 positions, 0 history)."""
    broker = get_current_broker()
    if not isinstance(broker, PaperBroker):
        raise HTTPException(status_code=400, detail="Reset only permitted in PAPER trading mode.")

    broker.ledger = {
        "cash": 10000.0,
        "positions": {},
        "trade_history": [],
        "last_updated": datetime.now().isoformat(),
    }
    broker._save_ledger()

    return {
        "success": True,
        "message": "Paper portfolio reset to clean state ($10,000.00 cash, 0 positions).",
        "cash": 10000.0,
        "positions": {},
    }



@router.post("/run-fast-forward-cycle")
def run_fast_forward_cycle(user: str = Depends(get_current_user)):
    """Execute complete 24H fast-forward simulation (Seed -> Open Sell -> Close Buy -> Open Settle)."""
    from scripts.run_close_routine import run_close_routine
    from scripts.run_open_routine import run_open_routine
    from tests.test_deterministic_cycle import MockDeterministicFetcher, MockEarningsFilter
    from datetime import datetime

    broker = get_current_broker()
    if not isinstance(broker, PaperBroker):
        raise HTTPException(status_code=400, detail="Fast-forward cycle only permitted in PAPER mode.")


    # 1. Seed initial
    now_str = datetime.now().isoformat()
    broker.ledger["positions"]["AAPL"] = {"shares": 4, "entry_price": 230.00, "entry_time": now_str}
    broker.ledger["positions"]["NVDA"] = {"shares": 8, "entry_price": 120.00, "entry_time": now_str}
    broker.ledger["cash"] = 8120.00
    broker._save_ledger()

    fetcher_open = MockDeterministicFetcher(is_morning_exit=True)
    fetcher_close = MockDeterministicFetcher(is_morning_exit=False)
    earnings_mock = MockEarningsFilter(blackout_syms=["MSFT"])

    # 2. Open Sell
    d1 = run_open_routine(broker_override=broker, fetcher_override=fetcher_open)
    # 3. Close Buy
    d2 = run_close_routine(broker_override=broker, fetcher_override=fetcher_close, earnings_filter_override=earnings_mock)
    # 4. Open Settle
    d3 = run_open_routine(broker_override=broker, fetcher_override=fetcher_open)

    return {
        "success": True,
        "message": "24-Hour Fast-Forward Cycle Completed: Seed -> Liquidate (+$47.20) -> Buy -> Liquidate (+$47.20).",
        "ending_cash": broker.get_cash_balance(),
        "open_positions": len(broker.get_positions()),
        "dossiers": {"open_1": d1, "close": d2, "open_2": d3},
    }


@router.get("/latest-dossiers")
def get_latest_dossiers(user: str = Depends(get_current_user)):
    """Retrieve latest Close and Open structured decision dossiers."""
    import json
    from execution.dossier import AUDIT_DIR
    res = {}
    close_f = AUDIT_DIR / "latest_close_dossier.json"
    open_f = AUDIT_DIR / "latest_open_dossier.json"

    if close_f.exists():
        try:
            with open(close_f) as f:
                res["latest_close"] = json.load(f)
        except Exception:
            pass

    if open_f.exists():
        try:
            with open(open_f) as f:
                res["latest_open"] = json.load(f)
        except Exception:
            pass

    return res


@router.get("/daemon-status")
def get_daemon_status(user: str = Depends(get_current_user)):
    """Retrieve autonomous trading daemon heartbeat status and next scheduled event."""
    import json
    daemon_file = settings.DATA_DIR / "daemon_status.json"
    if daemon_file.exists():
        try:
            with open(daemon_file, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "status": "NOT_RUNNING",
        "next_scheduled_event": "Daemon process is not currently running locally or on Cloud Run.",
        "last_heartbeat_et": "N/A",
    }



@router.post("/emergency-stop")
def trigger_emergency_stop(user: str = Depends(get_current_user)):
    """Instantly activate kill switch and liquidate all open positions."""
    from scripts.emergency_kill_switch import handle_emergency
    try:
        handle_emergency(action="stop", reason="Web Dashboard Emergency Halt")
        return {"success": True, "message": "Emergency Stop activated and all positions flattened."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during emergency halt: {e}")


@router.post("/emergency-reset")
def trigger_emergency_reset(user: str = Depends(get_current_user)):
    """Reset emergency kill switch to allow trading."""
    risk_mgr.deactivate_kill_switch()
    return {"success": True, "message": "Emergency kill switch deactivated. Normal trading resumed."}


@router.get("/trade-history")
def get_trade_history(user: str = Depends(get_current_user)):
    """Get list of past executed trades from the paper ledger."""
    broker = PaperBroker()
    history = broker.ledger.get("trade_history", [])
    # Return reverse chronological
    return {"history": list(reversed(history))}


@router.post("/sync-cash-flows")
def sync_cash_flows(user: str = Depends(get_current_user)):
    """Force an immediate incremental sync of external bank transfers from Schwab."""
    global _LAST_SCHWAB_TX_SYNC
    overrides = get_active_overrides()
    env = overrides.get("env") or settings.ENV
    broker = get_current_broker()

    if env != "live" or not isinstance(broker, SchwabBroker):
        return {"success": True, "message": "Cash flow sync is only active in LIVE mode.", "updated": False}

    try:
        cash = broker.get_cash_balance()
        positions_map = broker.get_positions()
        mkt_val = sum(p.shares * (fetcher.get_latest_quote(s).get("last_price") or p.entry_price) for s, p in positions_map.items())
        total_equity = cash + mkt_val

        ledger_mgr = CapitalLedgerManager(env=env)
        start_dt = ledger_mgr.get_sync_start_date()
        txs = broker.get_transactions(start_date=start_dt, types="JOURNAL,ACH_RECEIPT,ACH_DISBURSEMENT,WIRE_IN,WIRE_OUT")
        if txs:
            ledger_mgr.sync_schwab_transactions(txs, current_equity=total_equity)
        _LAST_SCHWAB_TX_SYNC = datetime.now().timestamp()
        
        metrics = ledger_mgr.get_metrics(total_equity)
        return {
            "success": True,
            "message": f"Successfully checked Schwab for transfers (scanned {len(txs)} records).",
            "metrics": metrics,
        }
    except Exception as e:
        logger.error(f"Manual cash flow sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to sync transfers: {e}")


@router.get("/schwab-status")
def get_schwab_status(user: str = Depends(get_current_user)):
    """Read-only diagnostic endpoint to verify live Schwab connection, balance, and account state."""
    try:
        schwab = SchwabBroker()
        cash = schwab.get_cash_balance()
        positions = schwab.get_positions()
        pos_summary = [
            {"ticker": sym, "shares": pos.shares, "cost_basis": pos.entry_price}
            for sym, pos in positions.items()
        ]
        
        # Token details if available
        auth_tokens = schwab.auth.tokens or {}
        has_refresh_token = bool(auth_tokens.get("refresh_token"))
        
        return {
            "connected": True,
            "account_hash": schwab.account_hash,
            "account_hash_short": f"...{schwab.account_hash[-6:]}" if schwab.account_hash else "Unknown",
            "settled_cash": cash,
            "positions_count": len(positions),
            "positions": pos_summary,
            "has_refresh_token": has_refresh_token,
            "token_source": "Secret Manager / Disk Cache",
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e),
            "detail": "Failed to connect to Schwab or verify token refresh.",
        }


@router.get("/activity-logs")
def get_activity_logs(user: str = Depends(get_current_user)):
    """Retrieve server-side action and routine activities with execution source (Cron vs Manual)."""
    if ACTIVITY_LOG_FILE.exists():
        try:
            with open(ACTIVITY_LOG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return []
    return []


@router.post("/activity-logs/clear")
def clear_activity_logs(user: str = Depends(get_current_user)):
    """Clear server-side activity logs."""
    try:
        if ACTIVITY_LOG_FILE.exists():
            ACTIVITY_LOG_FILE.unlink()
        return {"success": True, "message": "Server activity logs cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear activity logs: {e}")
