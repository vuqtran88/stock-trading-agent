"""Risk & Bearish Devil's Advocate Persona. Proactively searches for vulnerabilities, red flags, and downside risks."""

import json
from typing import Any, Dict
from agents.client import LLMClient
from agents.personas.base import PersonaReport

SYSTEM_PROMPT = """You are the Bearish Risk Advocate on an investment committee.
Your persona name MUST strictly be "Bearish Risk Advocate".
Your primary mission is capital preservation. You actively challenge groupthink and confirmation bias.
You look for:
- Valuation traps and stretched multiples
- Hidden leverage, debt refinancing cliffs, or declining margins
- Technical overbought extremes or divergences
- Macro/regulatory threats and competitive erosion

Note on Scoring: Score from 1.0 (imminent catastrophic risk / severe downside) to 10.0 (minimal identifiable downside risks, unusually safe asymmetric risk/reward).
"""


class BearAdvocate:
    def __init__(self, client: LLMClient):
        self.client = client

    async def analyze(self, data: Dict[str, Any]) -> PersonaReport:
        ticker = data.get("ticker", "")
        context = {
            "fundamentals": data.get("fundamentals", {}),
            "technicals": data.get("technicals", {}),
            "news": data.get("news", []),
        }

        user_content = (
            f"Thoroughly critique and probe downside risks for {ticker}:\n"
            f"{json.dumps(context, indent=2)}\n\n"
            f"Provide your structured risk evaluation as 'Bearish Risk Advocate'."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        return await self.client.complete_structured(messages, PersonaReport)

