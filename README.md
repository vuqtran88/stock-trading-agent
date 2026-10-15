# Buy-at-Close, Sell-at-Open AI Trading Agent

An autonomous trading agent for US Equities executing the **Overnight Drift** strategy: buying near market close (3:50–3:58 PM ET) and exiting at market open (9:30 AM ET).

## Architecture & Roadmap
Refer to [PLAN.md](file:///Users/vtran/Desktop/Playground/stock-trading-agent/PLAN.md) for complete roadmap, architecture diagram, and safety specifications.

## Quickstart

### 1. Setup Environment
```bash
python3 -m pip install -r requirements.txt
cp .env.example .env
```

### 2. Verify Phase 1 Pipeline
Test the historical market data downloader, parquet caching, fast live quotes, and earnings blackout filter:
```bash
python3 scripts/verify_phase1.py
```

### 3. Run Unit Tests
```bash
pytest
```
