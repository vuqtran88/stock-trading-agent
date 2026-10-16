# Project State Context: Stock Trading Agent

## Quick Snapshot
- **Strategy**: US Equities Buy-at-Close (3:50 PM ET on Day T), Sell-at-Open (9:30 AM ET on Day T+1) overnight drift.
- **Universe**: `QQQ` (benchmark), `AAPL`, `MSFT`, `NVDA`, `AMZN`, `GOOGL`, `META`, `TSLA`.
- **Status**: Phases 1–4 are fully built, tested (12/12 passing unit tests), and live credentials verified with Charles Schwab.

## Completed Milestones
1. **Phase 1: Foundation & Market Data**
   - `config/settings.py` (Pydantic env loader).
   - `data/fetcher.py` (yfinance downloader with Parquet cache and fast quote resolution).
   - `data/earnings.py` (earnings blackout detector).
   - `scripts/verify_phase1.py` (pipeline validation).

2. **Phase 2: Historical Backtesting Engine**
   - `strategies/overnight_strategy.py` (QQQ 20 EMA regime filter, earnings blackout, momentum/pullback ranking).
   - `backtesting/engine.py` & `backtesting/metrics.py` (CAGR, Max Drawdown, Sharpe, Sortino, Win Rate, Profit Factor, Expected Value per trade).
   - `scripts/run_backtest.py` (historical simulation 2018–present with equity and drawdown charts).
   - `scripts/audit_trades.py` (short-window day-by-day inspector tool).

3. **Phase 3: Risk Engine & Local Paper Broker**
   - `risk/risk_manager.py` (hard caps: $1k max position, $5k portfolio exposure, $250 daily loss ceiling, kill switch).
   - `execution/base_broker.py` & `execution/paper_broker.py` (local JSON ledger tracking cash and open positions).
   - `scripts/run_close_routine.py` (3:50 PM buy routine).
   - `scripts/run_open_routine.py` (9:28 AM sell routine).
   - `scripts/emergency_kill_switch.py` (instant halt & liquidate tool).

4. **Phase 4: Charles Schwab API & Live Pilot**
   - `execution/schwab_auth.py` (OAuth2 token manager with 7-day refresh token auto-refresh).
   - `execution/schwab_broker.py` (official Schwab Trader REST API integration, auto account hash discovery).
   - `notifications/notifier.py` (Discord webhook alerts for buys, sells with P&L, emergency stops).
   - `scripts/schwab_login.py` (CLI login helper with cached token validation).
   - `scripts/scan_secrets.py` + `.git/hooks/pre-commit` + `.github/workflows/security-scan.yml` (pre-commit secret scanner preventing leaks of keys, `.env`, or Discord webhooks).

## Live Schwab Accounts Linked
- Hash 1: `59BD30941584226BEAF816A0F768EA27EE2096C3D082550EA9547D7DDF593208` (Account ...9676)
- Hash 2: `058805D347B11CB7E0FE86A0916F368E01BD400FD24F32DE86436003DC2DCDC8` (Account ...4571)

## Essential Commands
```bash
# Verify Schwab authentication & balance
python3 scripts/schwab_login.py

# Run 3:50 PM ET afternoon buy routine (uses ENV="paper" or "live")
python3 scripts/run_close_routine.py

# Run 9:28 AM ET morning sell routine (liquidates positions at open, alerts Discord)
python3 scripts/run_open_routine.py

# Day-by-day trade audit on any window
python3 scripts/audit_trades.py --days 30

# Emergency Kill Switch
python3 scripts/emergency_kill_switch.py status
python3 scripts/emergency_kill_switch.py stop
python3 scripts/emergency_kill_switch.py reset

# Run test suite
pytest
```
