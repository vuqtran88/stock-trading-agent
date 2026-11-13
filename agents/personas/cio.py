"""Chief Investment Officer (CIO) Synthesizer. Adjudicates debate across all personas and issues final decision dossier."""

import json
from typing import Any, Dict, List, Optional, Tuple
from agents.client import LLMClient
from agents.personas.base import CIODossier, PersonaReport

PERSONA_WEIGHTS: Dict[str, float] = {
    "Fundamental Analyst": 0.35,
    "Technical Analyst": 0.25,
    "Sentiment Analyst": 0.20,
    "Bearish Risk Advocate": 0.20,
}

SYSTEM_PROMPT = """You are the Chief Investment Officer (CIO) and Chair of the Investment Committee.
You receive specialist analyses from:
1. "Fundamental Analyst" (35% weight)
2. "Technical Analyst" (25% weight)
3. "Sentiment Analyst" (20% weight)
4. "Bearish Risk Advocate" (20% weight — scored as Risk Safety from 1.0=Severe Downside Risk to 10.0=High Safety)

Committee Conviction Formula:
Conviction Score = (0.35 × Fundamental) + (0.25 × Technical) + (0.20 × Sentiment) + (0.20 × Bearish Risk Advocate)

Your responsibility is to weigh their arguments, resolve conflicts (e.g. strong technicals vs stretched valuation), and synthesize a balanced, definitive investment verdict aligned with the weighted Conviction Score:
- STRONG BUY (typically Conviction >= 7.8): Strong multi-factor alignment, clear catalysts, manageable risk.
- ACCUMULATE (typically Conviction 6.3 - 7.7): Attractive upside, buy on pullbacks or support levels.
- HOLD (typically Conviction 4.8 - 6.2): Mixed signals, balanced risk/reward, wait for a clearer catalyst.
- AVOID (typically Conviction < 4.8): Excessive downside risk, broken technicals, or severe fundamental red flags.

You must populate `conviction_score_breakdown` with 3-4 concise bullet points that explicitly explain how each specialist's score and weight contributed to the final Conviction Rating (including how the Bearish Risk Advocate's Risk Safety score tempered or reinforced the bullish thesis), recommend an investment horizon, specify an actionable entry zone and stop-loss level, and summarize key catalysts and risks.
"""


def compute_weighted_conviction(persona_scores: Dict[str, float]) -> Tuple[Optional[float], List[str]]:
    """Calculates the deterministic weighted Conviction Score and formula breakdown lines."""
    total_weight = 0.0
    weighted_sum = 0.0
    formula_lines: List[str] = []

    for persona_name, weight in PERSONA_WEIGHTS.items():
        if persona_name in persona_scores and persona_scores[persona_name] is not None:
            raw_score = float(persona_scores[persona_name])
            contrib = round(raw_score * weight, 2)
            weighted_sum += raw_score * weight
            total_weight += weight
            pct = int(round(weight * 100))
            label = (
                f"{persona_name} (Risk Safety, {pct}% weight)"
                if persona_name == "Bearish Risk Advocate"
                else f"{persona_name} ({pct}% weight)"
            )
            formula_lines.append(f"{label}: {raw_score:.1f}/10 × {weight:.2f} = +{contrib:.2f} pts")

    if total_weight == 0.0:
        return None, []

    normalized_score = weighted_sum / total_weight
    final_score = round(max(1.0, min(10.0, normalized_score)), 1)
    return final_score, formula_lines


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
        weighted_score, formula_lines = compute_weighted_conviction(persona_scores)

        formula_block = ""
        if weighted_score is not None:
            formula_block = (
                f"PRE-COMPUTED WEIGHTED CONVICTION SCORE: {weighted_score}/10\n"
                f"MATHEMATICAL BREAKDOWN:\n"
                + "\n".join(f"- {line}" for line in formula_lines)
                + "\n\n"
            )

        user_content = (
            f"Here is the company overview and committee reports for {ticker} ({company_name}):\n\n"
            f"COMPANY SNAPSHOT:\n{json.dumps(company_data.get('fundamentals', {}), indent=2)}\n\n"
            f"COMMITTEE REPORTS:\n{json.dumps(reports_summary, indent=2)}\n\n"
            f"{formula_block}"
            f"Please synthesize the final investment decision dossier. Ensure `conviction_score` is {weighted_score if weighted_score is not None else 'assigned accurately'} and populate `conviction_score_breakdown`."
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        dossier = await self.client.complete_structured(messages, CIODossier)
        # Ensure ticker, company_name, persona_scores, and deterministic conviction_score are populated accurately
        dossier.ticker = ticker
        dossier.company_name = company_name
        dossier.persona_scores = persona_scores
        if weighted_score is not None:
            dossier.conviction_score = weighted_score
        if not dossier.conviction_score_breakdown and formula_lines:
            dossier.conviction_score_breakdown = formula_lines
        return dossier

