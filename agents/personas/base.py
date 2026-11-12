"""Base Persona definition and structured response schemas for the AI committee."""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class PersonaReport(BaseModel):
    """Structured report returned by each individual specialist persona."""
    persona_name: str = Field(description="Name or title of the persona")
    score: float = Field(description="Score from 1.0 to 10.0 assessing suitability/strength", ge=1.0, le=10.0)
    stance: Literal["BULLISH", "NEUTRAL", "BEARISH"] = Field(description="Overall persona stance")
    key_findings: List[str] = Field(description="3-5 concise bullet points backing this persona's evaluation")
    summary: str = Field(description="2-3 sentence executive thesis from this persona's point of view")


class CIODossier(BaseModel):
    """Final synthesized investment dossier produced by the CIO."""
    ticker: str
    company_name: str
    verdict: Literal["STRONG BUY", "ACCUMULATE", "HOLD", "AVOID"] = Field(
        description="Definitive action recommendation"
    )
    conviction_score: float = Field(description="Overall committee conviction rating from 1.0 to 10.0", ge=1.0, le=10.0)
    suggested_horizon: Literal["Intraday/Overnight", "Swing (1-4 weeks)", "Position (1-6 months)", "Long-term (1+ years)"]
    executive_thesis: str = Field(description="Clear, persuasive synthesis explaining why to buy, hold, or avoid")
    key_catalysts: List[str] = Field(description="Upcoming catalysts or reasons for price appreciation")
    primary_risks: List[str] = Field(description="Top downside risks identified by the Bear Advocate")
    target_entry_zone: Optional[str] = Field(description="Recommended entry price range or condition")
    stop_loss_level: Optional[str] = Field(description="Recommended risk mitigation stop level")
    persona_scores: dict = Field(description="Mapping of persona name to their individual score (1.0 - 10.0)")

