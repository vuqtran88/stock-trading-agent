"""Earnings & SEC Filings Specialist Persona. Focuses on quarterly 10-Q/10-K disclosures, EPS beat/miss trends, and guidance."""

import json
from typing import Any, Dict
from agents.client import LLMClient
from agents.personas.base import PersonaReport

SYSTEM_PROMPT = """You are the Earnings & Filings Analyst on an investment committee.
Your persona name MUST strictly be "Earnings & Filings Analyst".
Your expertise is corporate reporting integrity:
- You analyze historical EPS beat/miss surprises and consistency of executing against Wall Street forecasts.
- You review recent periodic filings (10-Q quarterly reports, 10-K annual reports, 8-K material updates) from SEC EDGAR.
- You identify earnings quality: whether revenue growth is organic, guidance trajectory (upward revision vs lowering the bar), and accounting red flags.

Score from 1.0 (chronic earnings misses / declining guidance / accounting obfuscation) to 10.0 (consistent beat-and-raise cadence / accelerating revenue quality / transparent shareholder reporting).
"""


class EarningsAnalyst:
    def __init__(self, client: LLMClient):
        self.client = client

    async def analyze(self, data: Dict[str, Any]) -> PersonaReport:
        ticker = data.get("ticker", "")
        earnings_data = data.get("earnings", {})
        fundamentals = data.get("fundamentals", {})

        context = {
            "company_name": fundamentals.get("name"),
            "revenue_growth": fundamentals.get("revenue_growth"),
            "profit_margins": fundamentals.get("profit_margins"),
            "operating_margins": fundamentals.get("operating_margins"),
            "historical_eps_surprises": earnings_data.get("historical_eps_surprises", []),
            "recent_sec_filings": earnings_data.get("recent_sec_filings", []),
        }

        user_content = (
            f"Analyze the earnings report history and SEC filings disclosures for {ticker}:\n"
            f"{json.dumps(context, indent=2)}\n\n"
            f"Provide your structured evaluation as 'Earnings & Filings Analyst'."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return await self.client.complete_structured(messages, PersonaReport)

