"""Chief Investment Officer (CIO) Synthesizer. Adjudicates debate across all personas and issues final decision dossier."""

import json
from typing import Any, Dict, List
from agents.client import LLMClient
from agents.personas.base import CIODossier, PersonaReport

SYSTEM_PROMPT = """You are the Chief Investment Officer (CIO) and Chair of the Investment Committee.
You receive specialist analyses from:
1. "Fundamental Analyst"
2. "Technical Analyst"
3. "Sentiment Analyst"
4. "Bearish Risk Advocate"

Your responsibility is to weigh their arguments, resolve conflicts (e.g. strong technicals vs stretched valuation), and synthesize a balanced, definitive investment verdict:
- STRONG BUY: Strong multi-factor alignment, clear catalysts, manageable risk.
- ACCUMULATE: Attractive long-term upside, buy on pullbacks.
- HOLD: Mixed signals, balanced risk/reward, wait for a clearer catalyst.
- AVOID: Excessive downside risk, broken technicals, or severe fundamental red flags.

You must assign a conviction score (1.0 to 10.0), recommend an investment horizon, specify an actionable entry zone and stop-loss level, and summarize key catalysts and risks.
"""


class CIOSynthesizer:
    def __init__(self, client: LLMClient):
        self.client = client

    async def synthesize(
        self,
        company_data: Dict[str, Any],
        reports: List[PersonaReport],
    ) -> CIODossier:
        ticker = company_data.get("ticker", "")
        company_name = company_data.get("fundamentals", {}).get("name", ticker)

        reports_summary = [report.model_dump() for report in reports]
        persona_scores = {r.persona_name: r.score for r in reports}

        user_content = (
            f"Here is the company overview and committee reports for {ticker} ({company_name}):\n\n"
            f"COMPANY SNAPSHOT:\n{json.dumps(company_data.get('fundamentals', {}), indent=2)}\n\n"
            f"COMMITTEE REPORTS:\n{json.dumps(reports_summary, indent=2)}\n\n"
            f"Please synthesize the final investment decision dossier."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        dossier = await self.client.complete_structured(messages, CIODossier)
        # Ensure ticker, company_name, and persona_scores are populated accurately
        dossier.ticker = ticker
        dossier.company_name = company_name
        dossier.persona_scores = persona_scores
        return dossier

