"""Forensic Earnings Analysis Agent using LiteLLM to produce the 5-part deep dive."""

import json
import logging
from typing import Any, Dict, Optional
from agents.client import LLMClient
from agents.earnings_lab.schema import ForensicEarningsDossier

logger = logging.getLogger(__name__)

FORENSIC_SYSTEM_PROMPT = """You are an elite, highly skeptical Senior Forensic Accounting & Earnings Analyst.
Your job is to produce a rigorous, unflinching 5-part institutional audit of a company's quarterly earnings performance and SEC disclosures.

You evaluate:
1. EXECUTIVE VERDICT & EARNINGS GRADE:
   - Assign an overall letter grade from A+ (stellar organic acceleration, flawless cash conversion, raised guidance) down to F (distorted GAAP/non-GAAP gap, massive miss, severe deceleration, or aggressive accounting).
   - Rate Quality of Earnings from 1.0 to 10.0 (cash generation vs paper accounting tricks, GAAP vs non-GAAP divergence).
   - Provide `quality_score_breakdown`: exactly 2-3 concise forensic bullet points detailing why this quality score was given (e.g. Free Cash Flow conversion %, size of GAAP vs Non-GAAP gap, stock-based compensation burden).
   - Rate Guidance Trajectory (RAISED, CONFIRMED, LOWERED, WITHDRAWN, CAUTIOUS).
2. BEAT / MISS CADENCE & SURPRISE MATRIX:
   - In `eps_surprise_summary`, you MUST include a chronological list of quarters.
   - CRITICAL REQUIREMENT: Row 1 of `eps_surprise_summary` MUST be the current audited quarter being analyzed (e.g. Q3 FY2026), including its reported EPS, estimated EPS, date, and surprise percentage! If the user provided a PDF or transcript, extract the current quarter's reported EPS and consensus from the text. Follow with the trailing quarters beneath it.
   - Evaluate actual performance against Wall Street estimates over the past 4+ quarters.
   - Determine if the company has a habit of "lowering the bar to beat it" or delivering genuine upside.
3. REVENUE QUALITY & CASH FLOW CONVERSION:
   - Carefully verify table column headers (e.g., "September 26, 2026" vs "June 27, 2026") when citing CapEx and Free Cash Flow figures. Do not mistake the prior quarter column for the current quarter!
   - Assess whether top-line revenue growth is organic volume or purely inflation/pricing.
   - Scrutinize Operating Cash Flow and Free Cash Flow conversion vs Reported Net Income.
4. FORWARD GUIDANCE & MANAGEMENT CREDIBILITY:
   - Score management transparency from 1.0 to 10.0. Are they evasive about headwinds, or forthright?
   - Provide `management_credibility_breakdown`: exactly 2-3 concise bullet points detailing why this credibility score was given (e.g. meeting past commitments, candid disclosure of lagging divisions, realistic forward backlog vs supply constraints).
5. RED FLAGS & ACCOUNTING INTEGRITY:
   - Highlight inventory build-ups, DSO (Days Sales Outstanding) spikes, unusual one-time gains, deferred revenue slowdowns, or dilution.
   - Rate accounting integrity as CLEAN, MINOR_CONCERNS, or HIGH_RISK.

Be concrete, quantitative, and direct. Do not hedge with generic disclaimers.
"""


class ForensicEarningsAgent:
    """Invokes LLM with full financial context or uploaded document text to generate ForensicEarningsDossier."""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    async def analyze_financials(
        self,
        ticker: str,
        financial_payload: Dict[str, Any],
        custom_transcript: Optional[str] = None,
    ) -> ForensicEarningsDossier:
        company_name = financial_payload.get("company_name", ticker)
        target_period = financial_payload.get("target_period", "Latest Reported Quarter")

        prompt_data = {
            "ticker": ticker,
            "company_name": company_name,
            "target_period": target_period,
            "key_metrics": {
                "current_price": financial_payload.get("current_price"),
                "profit_margins": financial_payload.get("profit_margins"),
                "operating_margins": financial_payload.get("operating_margins"),
                "revenue_growth": financial_payload.get("revenue_growth"),
            },
            "historical_eps_surprises": financial_payload.get("eps_surprises", []),
            "quarterly_income_statement": financial_payload.get("quarterly_income", {}),
            "quarterly_cash_flow": financial_payload.get("quarterly_cashflow", {}),
            "recent_sec_filings": financial_payload.get("recent_filings", []),
        }

        if custom_transcript:
            prompt_data["custom_earnings_transcript_or_release"] = custom_transcript[:50000]

        user_content = (
            f"Conduct a thorough forensic earnings analysis for {ticker} ({company_name}) for {target_period}.\n\n"
            f"FINANCIAL DATA & FILINGS:\n{json.dumps(prompt_data, indent=2)}\n\n"
            f"Generate the complete 5-part Forensic Earnings Dossier adhering strictly to the schema."
        )

        messages = [
            {"role": "system", "content": FORENSIC_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        dossier: ForensicEarningsDossier = await self.client.complete_structured(messages, ForensicEarningsDossier)
        
        # Ensure ticker, period, and filing links are retained
        dossier.ticker = ticker
        dossier.company_name = company_name
        dossier.reporting_period = target_period

        # Ensure mathematical consistency across eps_surprise_summary
        for row in dossier.eps_surprise_summary:
            est = row.get("eps_estimate")
            rep = row.get("reported_eps")
            if est is not None and rep is not None:
                try:
                    e_val = float(est)
                    r_val = float(rep)
                    if e_val > 0:
                        row["surprise_pct"] = round(((r_val - e_val) / e_val) * 100, 2)
                        row["eps_estimate"] = round(e_val, 2)
                        row["reported_eps"] = round(r_val, 2)
                except (ValueError, TypeError):
                    pass
        
        # Fallback / safety verification for current quarter in eps_surprise_summary
        latest_eps = financial_payload.get("latest_eps")
        if latest_eps and latest_eps.get("reported_eps") is not None:
            # Check if this latest quarter is already represented in eps_surprise_summary
            has_latest = any(
                str(row.get("date", "")) == str(latest_eps.get("date", "")) or
                (row.get("reported_eps") == latest_eps.get("reported_eps") and row.get("eps_estimate") == latest_eps.get("eps_estimate"))
                for row in dossier.eps_surprise_summary
            )
            if not has_latest:
                # Prepend the current audited quarter as row 1
                curr_row = {
                    "date": latest_eps.get("date", "Current Quarter"),
                    "quarter": target_period,
                    "eps_estimate": latest_eps.get("eps_estimate"),
                    "reported_eps": latest_eps.get("reported_eps"),
                    "surprise_pct": latest_eps.get("surprise_pct"),
                    "is_current": True,
                }
                dossier.eps_surprise_summary.insert(0, curr_row)

        if not dossier.sec_filing_links and financial_payload.get("recent_filings"):
            dossier.sec_filing_links = [
                {"type": f.get("type", "Filing"), "title": f.get("title", "SEC Filing"), "url": f.get("edgar_url", "")}
                for f in financial_payload.get("recent_filings", [])
            ]
        return dossier

