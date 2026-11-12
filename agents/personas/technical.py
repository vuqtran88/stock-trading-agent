"""Technical and Momentum Analyst Persona. Focuses on moving averages, trend strength, RSI, volume, and timing."""

import json
from typing import Any, Dict
from agents.client import LLMClient
from agents.personas.base import PersonaReport

SYSTEM_PROMPT = """You are the Technical & Momentum Analyst on an investment committee.
Your persona name MUST strictly be "Technical Analyst".
Your objective is to identify favorable risk-reward setups, trend strength, moving average alignments (EMA20, SMA50, SMA200), RSI momentum, and volume validation.
You disregard accounting metrics and focus entirely on whether institutional buyers or sellers control the tape right now.

Score from 1.0 (severe technical breakdown / distribution) to 10.0 (high-probability breakout / strong trend with momentum).
"""


class TechnicalAnalyst:
    def __init__(self, client: LLMClient):
        self.client = client

    async def analyze(self, data: Dict[str, Any]) -> PersonaReport:
        ticker = data.get("ticker", "")
        technicals = data.get("technicals", {})

        user_content = (
            f"Analyze the technical indicators for {ticker}:\n"
            f"{json.dumps(technicals, indent=2)}\n\n"
            f"Provide your structured evaluation as 'Technical Analyst'."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return await self.client.complete_structured(messages, PersonaReport)

