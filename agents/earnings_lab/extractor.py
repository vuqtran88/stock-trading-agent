"""Data extractor for the Forensic Earnings Lab.

Supports:
1. Fast metadata preview (Quarter, Fiscal Year, Filing Date, Available Quarters).
2. Slicing multi-quarter financial statements (Income & Cash Flow).
3. Ingesting custom uploaded PDF earnings releases via pypdf.
4. Parsing raw text earnings call transcripts.
"""

import asyncio
import io
import logging
from typing import Any, Dict, List, Optional
import pandas as pd
import yfinance as yf
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class EarningsLabExtractor:
    """Extracts, normalizes, and previews earnings data from SEC Edgar, yfinance, and custom files."""

    async def preview_metadata(self, ticker: str) -> Dict[str, Any]:
        """Fast preview endpoint to discover latest quarter, fiscal year, and available past quarters."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._preview_metadata_sync, ticker.upper())

    def _preview_metadata_sync(self, ticker: str) -> Dict[str, Any]:
        stock = yf.Ticker(ticker)
        info = stock.info or {}
        company_name = info.get("shortName") or info.get("longName") or ticker

        # 1. Discover recent periodic filings (10-Q, 10-K, 8-K)
        available_filings = []
        latest_filing = None
        try:
            sec_filings = stock.sec_filings or []
            for f in sec_filings:
                f_type = f.get("type", "")
                if f_type in ("10-Q", "10-K", "8-K", "8-K/A"):
                    item = {
                        "type": f_type,
                        "title": f.get("title", f_type),
                        "date": str(f.get("date", "")),
                        "edgar_url": f.get("edgarUrl", ""),
                        "exhibits": f.get("exhibits", {}),
                    }
                    available_filings.append(item)
                    if not latest_filing and f_type in ("10-Q", "10-K"):
                        latest_filing = item
        except Exception as e:
            logger.debug(f"Error reading SEC filings for {ticker}: {e}")

        # 2. Extract EPS surprise dates & latest reported quarter (skip future estimates with NaN reported)
        available_quarters = []
        latest_eps_row = None
        try:
            ed = stock.earnings_dates
            if ed is not None and not ed.empty:
                for idx, row in ed.iterrows():
                    rep = row.get("Reported EPS")
                    # Skip future calendar projections where Reported EPS is NaN
                    if pd.isna(rep):
                        continue

                    q_date = str(idx.date())
                    est = float(row.get("EPS Estimate")) if pd.notnull(row.get("EPS Estimate")) else None
                    rep = float(rep) if pd.notnull(rep) else None

                    # If both reported and estimate are available, calculate consistent surprise %
                    # from the displayed rounded numbers (or exact if provided)
                    if est is not None and est > 0 and rep is not None:
                        surp_calc = round(((rep - est) / est) * 100, 2)
                    elif pd.notnull(surp):
                        surp_calc = round(float(surp), 2)
                    else:
                        surp_calc = None

                    q_item = {
                        "date": q_date,
                        "eps_estimate": round(est, 2) if est is not None else None,
                        "reported_eps": round(rep, 2) if rep is not None else None,
                        "surprise_pct": surp_calc,
                    }
                    available_quarters.append(q_item)
                    if not latest_eps_row:
                        latest_eps_row = q_item
                    if len(available_quarters) >= 4:
                        break
        except Exception as e:
            logger.debug(f"Error reading earnings dates for {ticker}: {e}")

        # Derive universal fiscal period dynamically using company's official fiscal calendar
        detected_period = None
        mrq_ts = info.get("mostRecentQuarter")
        lfy_ts = info.get("lastFiscalYearEnd")

        if mrq_ts and lfy_ts:
            from datetime import datetime
            mrq_dt = datetime.fromtimestamp(mrq_ts)
            lfy_dt = datetime.fromtimestamp(lfy_ts)
            
            # Month difference between latest quarter end and fiscal year end
            month_diff = (mrq_dt.year - lfy_dt.year) * 12 + (mrq_dt.month - lfy_dt.month)
            if month_diff <= 0:
                month_diff += 12
            
            # Map month elapsed to Q1, Q2, Q3, Q4
            q_num = max(1, min(4, (month_diff + 1) // 3))
            
            # Fiscal year is typically the year the fiscal year ends in
            fy_year = lfy_dt.year if q_num == 4 else (lfy_dt.year + 1)
            detected_period = f"Q{q_num} FY{fy_year}"

        # If latest filing is 10-K, override to Q4 / Annual
        if latest_filing and latest_filing.get("type") == "10-K":
            f_date = latest_filing.get("date", "")
            year = f_date.split("-")[0] if "-" in f_date else "2026"
            detected_period = f"Q4 FY{year} (Annual 10-K)"

        # Fallback 1: Check exhibits / filenames in SEC filing
        if not detected_period and latest_filing:
            title_lower = (latest_filing.get("title", "") + " " + latest_filing.get("type", "")).lower()
            exhibits_str = str(latest_filing.get("exhibits", {})).lower()
            if latest_filing.get("type") == "10-K":
                f_date = latest_filing.get("date", "")
                year = f_date.split("-")[0] if "-" in f_date else "2026"
                detected_period = f"Q4 FY{year} (Annual 10-K)"
            else:
                for q_tag in ["q1", "q2", "q3", "q4"]:
                    if q_tag in title_lower or q_tag in exhibits_str:
                        f_date = latest_filing.get("date", "")
                        year = f_date.split("-")[0] if "-" in f_date else "2026"
                        detected_period = f"{q_tag.upper()} FY{year}"
                        break

        if not detected_period:
            detected_period = "Latest Reported Quarter"

        return {
            "ticker": ticker,
            "company_name": company_name,
            "detected_period": detected_period,
            "latest_filing": latest_filing or {
                "type": "10-Q",
                "title": "Quarterly Financial Report",
                "date": available_quarters[0]["date"] if available_quarters else "Recent",
                "edgar_url": f"https://www.sec.gov/edgar/searchedgar/companysearch?company={ticker}",
            },
            "latest_eps": latest_eps_row,
            "available_quarters": available_quarters[:4],
            "recent_filings": available_filings[:5],
        }

    async def get_deep_financials(
        self,
        ticker: str,
        target_period: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Collects multi-quarter income statements, cash flow statements, and EPS history."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._get_deep_financials_sync, ticker.upper(), target_period)

    def _get_deep_financials_sync(
        self,
        ticker: str,
        target_period: Optional[str] = None,
    ) -> Dict[str, Any]:
        stock = yf.Ticker(ticker)
        info = stock.info or {}

        # 1. Income statement line items across recent quarters
        income_summary = {}
        try:
            qi = stock.quarterly_income_stmt
            if qi is not None and not qi.empty:
                cols = [str(c.date()) if hasattr(c, "date") else str(c) for c in qi.columns[:4]]
                for idx in qi.index:
                    idx_str = str(idx)
                    # Keep key line items
                    if any(term in idx_str for term in ["Revenue", "Operating Income", "Net Income", "Gross Profit", "EBITDA", "Cost Of"]):
                        values = [float(v) if pd.notnull(v) else None for v in qi.loc[idx][:4]]
                        income_summary[idx_str] = dict(zip(cols, values))
        except Exception as e:
            logger.debug(f"Error parsing quarterly income stmt: {e}")

        # 2. Cash flow statement line items
        cashflow_summary = {}
        try:
            qc = stock.quarterly_cashflow
            if qc is not None and not qc.empty:
                cols = [str(c.date()) if hasattr(c, "date") else str(c) for c in qc.columns[:4]]
                for idx in qc.index:
                    idx_str = str(idx)
                    if any(term in idx_str for term in ["Free Cash", "Operating Cash", "Capital Expenditure", "Repurchase", "Debt"]):
                        values = [float(v) if pd.notnull(v) else None for v in qc.loc[idx][:4]]
                        cashflow_summary[idx_str] = dict(zip(cols, values))
        except Exception as e:
            logger.debug(f"Error parsing quarterly cash flow: {e}")

        meta = self._preview_metadata_sync(ticker)

        return {
            "ticker": ticker,
            "company_name": info.get("shortName") or ticker,
            "target_period": target_period or meta.get("detected_period"),
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "target_mean_price": info.get("targetMeanPrice"),
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "revenue_growth": info.get("revenueGrowth"),
            "latest_eps": meta.get("latest_eps"),
            "eps_surprises": meta.get("available_quarters", []),
            "recent_filings": meta.get("recent_filings", []),
            "quarterly_income": income_summary,
            "quarterly_cashflow": cashflow_summary,
        }

    def extract_text_from_pdf(self, file_bytes: bytes, max_pages: int = 25) -> str:
        """Extracts text content from uploaded PDF earnings releases or 10-Q documents."""
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            text_parts = []
            pages_to_read = min(len(reader.pages), max_pages)
            for i in range(pages_to_read):
                page_text = reader.pages[i].extract_text()
                if page_text:
                    text_parts.append(f"--- PAGE {i+1} ---\n{page_text}")
            extracted = "\n\n".join(text_parts).strip()
            # Allow up to 60,000 chars so crucial financial schedules (e.g. CapEx, FCF on later pages) are included
            return extracted[:60000] if extracted else "No readable text extracted from PDF."
        except Exception as e:
            logger.error(f"Failed to extract text from PDF: {e}")
            raise ValueError(f"Could not read PDF document: {str(e)}")

