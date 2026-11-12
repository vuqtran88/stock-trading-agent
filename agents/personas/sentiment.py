"""Sentiment & Catalyst Scout Persona. Focuses on market perception, news tone, and near-term triggers."""

import json
from typing import Any, Dict
from agents.client import LLMClient
from agents.personas.base import PersonaReport

SYSTEM_PROMPT = """You are the Sentiment & Catalyst Scout on an investment committee.
Your persona name MUST strictly be "Sentiment Analyst".
Your role is to assess headline sentiment, near-term catalysts (earnings dates, product launches, regulatory updates), and market narrative.
You determine whether current market perception is overly euphoric, overly panicked, or positioned for positive surprise.

Score from 1.0 (toxic sentiment / impending negative catalyst) to 10.0 (overwhelmingly favorable sentiment / strong positive catalyst tailwinds).
"""


class SentimentAnalyst:
    def __init__(self, client: LLMClient):
        self.client = client

    async def analyze(self, data: Dict[str, Any]) -> PersonaReport:
        ticker = data.get("ticker", "")
        news = data.get("news", [])
        fundamentals = data.get("fundamentals", {})

        context = {
            "company_name": fundamentals.get("name"),
            "sector": fundamentals.get("sector"),
            "target_mean_price": fundamentals.get("target_mean_price"),
            "current_price": fundamentals.get("current_price"),
            "recent_headlines": news,
        }

        user_content = (
            f"Analyze the market sentiment and recent news for {ticker}:\n"
            f"{json.dumps(context, indent=2)}\n\n"
            f"Provide your structured evaluation as 'Sentiment Analyst'."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return await self.client.complete_structured(messages, PersonaReport)

