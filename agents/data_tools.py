"""Zero-cost financial, technical, and news data aggregator for AI agent personas."""

import asyncio
import logging
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd
import yfinance as yf
from data.fetcher import MarketDataFetcher

logger = logging.getLogger(__name__)


class AgentDataTools:
    """Aggregates fundamentals, technical indicators, and news into a concise LLM context payload."""

    def __init__(self):
        self.fetcher = MarketDataFetcher()

    async def get_company_context(self, ticker: str) -> Dict[str, Any]:
        """Runs in thread pool to fetch fundamentals, technicals, and news asynchronously."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._collect_sync, ticker.upper())

    def _collect_sync(self, ticker: str) -> Dict[str, Any]:
        try:
            stock = yf.Ticker(ticker)
            info = stock.info or {}
        except Exception as e:
            logger.warning(f"Failed to fetch info for {ticker}: {e}")
            info = {}

        # 1. Fundamental Summary
        fundamentals = {
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "market_cap": info.get("marketCap"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "debt_to_equity": info.get("debtToEquity"),
            "free_cashflow": info.get("freeCashflow"),
            "revenue_growth": info.get("revenueGrowth"),
            "target_mean_price": info.get("targetMeanPrice"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "52_week_high": info.get("fiftyTwoWeekHigh"),
            "52_week_low": info.get("fiftyTwoWeekLow"),
        }

        # 2. Technical Summary (using cached/fetched OHLCV history)
        technicals = self._calculate_technicals(ticker)

        # 3. Recent News
        news = self._extract_recent_news(stock)

        # 4. Earnings Reports & SEC Filings Summary
        earnings = self._extract_earnings_and_filings(stock)

        return {
            "ticker": ticker,
            "fundamentals": fundamentals,
            "technicals": technicals,
            "news": news,
            "earnings": earnings,
        }

    def _calculate_technicals(self, ticker: str) -> Dict[str, Any]:
        try:
            # fetch_historical pulls cached parquet data or yfinance
            df = self.fetcher.fetch_historical(ticker)
            if df is None or df.empty or len(df) < 30:
                # Fallback to direct yfinance history if needed
                stock = yf.Ticker(ticker)
                df = stock.history(period="6mo")

            if df is None or df.empty or len(df) < 30:
                return {"status": "insufficient_data"}

            close = df["Close"]
            current_close = float(close.iloc[-1])

            # Moving averages
            ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
            sma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else None
            sma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else None

            # RSI 14
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / (loss + 1e-9)
            rsi = float(100 - (100 / (1 + rs)).iloc[-1])

            # 20-day High / Low
            recent_high = float(df["High"].iloc[-20:].max())
            recent_low = float(df["Low"].iloc[-20:].min())

            # 20-day Volume Trend
            vol = df["Volume"]
            avg_vol = float(vol.iloc[-20:].mean()) if len(vol) >= 20 else float(vol.mean())
            last_vol = float(vol.iloc[-1])
            vol_ratio = round(last_vol / (avg_vol + 1e-9), 2)

            return {
                "current_price": round(current_close, 2),
                "ema20": round(ema20, 2),
                "sma50": round(sma50, 2) if sma50 else "N/A",
                "sma200": round(sma200, 2) if sma200 else "N/A",
                "above_ema20": current_close > ema20,
                "rsi14": round(rsi, 1),
                "rsi_status": "Overbought" if rsi > 70 else ("Oversold" if rsi < 30 else "Neutral"),
                "20d_high": round(recent_high, 2),
                "20d_low": round(recent_low, 2),
                "volume_ratio_vs_20d_avg": vol_ratio,
            }
        except Exception as e:
            logger.warning(f"Error calculating technicals for {ticker}: {e}")
            return {"status": "error", "error": str(e)}

    def _extract_recent_news(self, stock: yf.Ticker, limit: int = 5) -> List[Dict[str, str]]:
        headlines = []
        try:
            raw_news = stock.news or []
            for item in raw_news[:limit]:
                content = item.get("content", {}) if isinstance(item, dict) else {}
                title = item.get("title") or content.get("title")
                publisher = item.get("publisher") or content.get("provider", {}).get("displayName", "News")
                link = item.get("link") or content.get("canonicalUrl", {}).get("url", "")
                if title:
                    headlines.append({
                        "title": title,
                        "publisher": publisher,
                        "link": link,
                    })
        except Exception as e:
            logger.debug(f"Could not retrieve news headlines: {e}")
        return headlines

    def _extract_earnings_and_filings(self, stock: yf.Ticker) -> Dict[str, Any]:
        """Extract historical EPS beat/miss surprises and recent SEC periodic reports (10-Q, 10-K, 8-K)."""
        eps_history = []
        try:
            ed = stock.earnings_dates
            if ed is not None and not ed.empty:
                for idx, row in ed.head(4).iterrows():
                    est = row.get("EPS Estimate")
                    rep = row.get("Reported EPS")
                    surp = row.get("Surprise(%)")
                    eps_history.append({
                        "quarter_date": str(idx.date()),
                        "eps_estimate": float(est) if pd.notnull(est) else None,
                        "reported_eps": float(rep) if pd.notnull(rep) else None,
                        "surprise_pct": float(surp) if pd.notnull(surp) else None,
                    })
        except Exception as e:
            logger.debug(f"Could not retrieve earnings dates: {e}")

        recent_filings = []
        try:
            filings = stock.sec_filings or []
            for f in filings[:5]:
                f_type = f.get("type")
                if f_type in ("10-Q", "10-K", "8-K", "8-K/A"):
                    recent_filings.append({
                        "type": f_type,
                        "title": f.get("title"),
                        "date": str(f.get("date")),
                        "edgar_url": f.get("edgarUrl"),
                    })
        except Exception as e:
            logger.debug(f"Could not retrieve SEC filings: {e}")

        return {
            "historical_eps_surprises": eps_history,
            "recent_sec_filings": recent_filings,
        }

