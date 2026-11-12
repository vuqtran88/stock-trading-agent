"""Fundamental Value Analyst Persona. Focuses on valuation, margins, moats, and capital allocation."""

import json
from typing import Any, Dict
from agents.client import LLMClient
from agents.personas.base import PersonaReport

SYSTEM_PROMPT = """You are the Fundamental Analyst on an investment committee.
Your persona name MUST strictly be "Fundamental Analyst".
Your philosophy centers on intrinsic valuation, durable economic moats, return on equity (ROE), free cash flow conversion, and debt safety.
You do NOT care about chart patterns or short-term noise.
You judge whether a company is high quality and trading at a fair or advantageous price.

Score from 1.0 (severely overvalued / deteriorating fundamentals) to 10.0 (exceptional quality at a great price).
"""


class FundamentalAnalyst:
    def __init__(self, client: LLMClient):
        self.client = client

    async def analyze(self, data: Dict[str, Any]) -> PersonaReport:
        ticker = data.get("ticker", "")
        fundamentals = data.get("fundamentals", {})

        user_content = (
            f"Analyze the following fundamental data for {ticker}:\n"
            f"{json.dumps(fundamentals, indent=2)}\n\n"
            f"Provide your structured evaluation as 'Fundamental Analyst'."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return await self.client.complete_structured(messages, PersonaReport)

