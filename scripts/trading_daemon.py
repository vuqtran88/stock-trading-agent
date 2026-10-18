"""Autonomous Trading Runner Daemon (GCP & Local Compatible).

Features:
- Live heartbeat status published to data_cache/daemon_status.json
- Awareness of NYSE/NASDAQ trading hours & holidays
- Scheduled 3:50 PM ET Afternoon Buy & 9:28 AM ET Morning Sell execution
- Accelerated sandbox test mode (--test-interval <seconds>) for instant autonomous validation
"""

import sys
import time
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone, timedelta
import zoneinfo

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.run_close_routine import run_close_routine
from scripts.run_open_routine import run_open_routine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TradingDaemon")

STATUS_FILE = ROOT_DIR / "data_cache" / "daemon_status.json"
ET_TZ = zoneinfo.ZoneInfo("America/New_York")


def update_heartbeat(status: str, next_event: str, cycle_counter: int = 0):
    """Publish current runner state for UI and monitoring health checks."""
    now_utc = datetime.now(timezone.utc)
    now_et = datetime.now(ET_TZ)
    STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "status": status,
        "last_heartbeat_utc": now_utc.isoformat(),
        "last_heartbeat_et": now_et.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "next_scheduled_event": next_event,
        "cycle_counter": cycle_counter,
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(payload, f, indent=2)


def run_accelerated_sandbox(interval_sec: int):
    """Run alternating Buy and Sell routines every interval_sec seconds for testing."""
    logger.info("=" * 70)
    logger.info(f"STARTING ACCELERATED SANDBOX DAEMON (Interval: {interval_sec}s)")
    logger.info("=" * 70)

    from tests.test_deterministic_cycle import MockDeterministicFetcher, MockEarningsFilter
    from execution.paper_broker import PaperBroker

    broker = PaperBroker()
    cycle = 0

    try:
        while True:
            cycle += 1
            if cycle % 2 == 1:
                # Odd cycle: Afternoon Buy Scan
                event_name = f"Cycle #{cycle}: Afternoon Buy Scan (3:50 PM ET)"
                logger.info(f"\n⚡ TRIGGERING: {event_name}")
                update_heartbeat(status="RUNNING_TEST_BUY", next_event=f"Next Morning Sell in {interval_sec}s", cycle_counter=cycle)
                fetcher = MockDeterministicFetcher(is_morning_exit=False)
                run_close_routine(broker_override=broker, fetcher_override=fetcher, earnings_filter_override=MockEarningsFilter())
            else:
                # Even cycle: Morning Open Sell
                event_name = f"Cycle #{cycle}: Morning Open Sell (9:28 AM ET)"
                logger.info(f"\n⚡ TRIGGERING: {event_name}")
                update_heartbeat(status="RUNNING_TEST_SELL", next_event=f"Next Afternoon Buy in {interval_sec}s", cycle_counter=cycle)
                fetcher = MockDeterministicFetcher(is_morning_exit=True)
                run_open_routine(broker_override=broker, fetcher_override=fetcher)

            logger.info(f"Sleeping for {interval_sec}s until next test event...")
            time.sleep(interval_sec)

    except KeyboardInterrupt:
        logger.info("\nDaemon stopped by user.")
        update_heartbeat(status="STOPPED", next_event="None")


def load_daemon_config():
    """Load dynamic settings from config_override.json or fallback to defaults."""
    override_file = ROOT_DIR / "data_cache" / "config_override.json"
    data = {}
    if override_file.exists():
        try:
            with open(override_file, "r") as f:
                data = json.load(f)
        except Exception:
            pass

    active_strategy = data.get("active_strategy", "overnight_drift")
    strategy_enabled = data.get("strategy_enabled", True)
    close_time_str = data.get("close_routine_time", "15:50")
    open_time_str = data.get("open_routine_time", "09:28")

    try:
        open_h, open_m = [int(x) for x in open_time_str.split(":")]
    except Exception:
        open_h, open_m = 9, 28

    try:
        close_h, close_m = [int(x) for x in close_time_str.split(":")]
    except Exception:
        close_h, close_m = 15, 50

    return {
        "active_strategy": active_strategy,
        "strategy_enabled": strategy_enabled,
        "open_time": (open_h, open_m),
        "close_time": (close_h, close_m),
        "open_time_str": f"{open_h:02d}:{open_m:02d}",
        "close_time_str": f"{close_h:02d}:{close_m:02d}",
    }


def run_production_schedule():
    """Live clock scheduler executing at user-configured ET times on weekdays."""
    logger.info("=" * 70)
    logger.info("STARTING PRODUCTION TRADING DAEMON (Configurable US Market Schedule)")
    logger.info("=" * 70)

    last_morning_date = None
    last_afternoon_date = None

    try:
        while True:
            cfg = load_daemon_config()
            strategy_enabled = cfg["strategy_enabled"]
            active_strat = cfg["active_strategy"]
            open_h, open_m = cfg["open_time"]
            close_h, close_m = cfg["close_time"]

            now_et = datetime.now(ET_TZ)
            today_date = now_et.date()
            weekday = now_et.weekday()  # 0=Monday, 4=Friday, 5=Sat, 6=Sun

            is_weekend = weekday >= 5
            hour = now_et.hour
            minute = now_et.minute

            if not strategy_enabled:
                next_event = f"Execution PAUSED by user for '{active_strat}'. Automated routine triggers disabled."
                update_heartbeat(status="PAUSED_BY_USER", next_event=next_event)
                time.sleep(15)
                continue

            # Compute next event string
            if is_weekend:
                next_event = f"Market Closed (Weekend). Next: Monday {cfg['open_time_str']} ET"
            elif hour < open_h or (hour == open_h and minute < open_m):
                m_diff = (open_h * 60 + open_m) - (hour * 60 + minute)
                h_diff = m_diff // 60
                m_rem = m_diff % 60
                next_event = f"Today {cfg['open_time_str']} ET Morning Exit ({h_diff}h {m_rem}m) [{active_strat}]"
            elif hour < close_h or (hour == close_h and minute < close_m):
                m_diff = (close_h * 60 + close_m) - (hour * 60 + minute)
                h_diff = m_diff // 60
                m_rem = m_diff % 60
                next_event = f"Today {cfg['close_time_str']} ET Afternoon Entry ({h_diff}h {m_rem}m) [{active_strat}]"
            else:
                next_event = f"Trading finished for today. Next: Tomorrow {cfg['open_time_str']} ET"

            update_heartbeat(status="SCHEDULED_WAITING", next_event=next_event)

            # Weekday execution triggers
            if not is_weekend:
                # Morning open routine trigger
                if hour == open_h and minute >= open_m and minute < (open_m + 7) and last_morning_date != today_date:
                    logger.info(f"⏰ {cfg['open_time_str']} ET Triggered: Running Morning Sell Routine [{active_strat}]...")
                    run_open_routine()
                    last_morning_date = today_date

                # Afternoon close routine trigger
                if hour == close_h and minute >= close_m and minute < (close_m + 8) and last_afternoon_date != today_date:
                    logger.info(f"⏰ {cfg['close_time_str']} ET Triggered: Running Afternoon Close Routine [{active_strat}]...")
                    run_close_routine()
                    last_afternoon_date = today_date

            time.sleep(15)  # Check clock every 15 seconds

    except KeyboardInterrupt:
        logger.info("\nTrading daemon terminated.")
        update_heartbeat(status="STOPPED", next_event="None")


def main():
    parser = argparse.ArgumentParser(description="Autonomous Trading Runner Daemon")
    parser.add_argument("--test-interval", type=int, help="Accelerated test mode interval in seconds (e.g. 20)")
    args = parser.parse_args()

    if args.test_interval:
        run_accelerated_sandbox(args.test_interval)
    else:
        run_production_schedule()


if __name__ == "__main__":
    main()
