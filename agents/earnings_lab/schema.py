"""Pydantic schema for the comprehensive Forensic Earnings Dossier."""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ForensicEarningsDossier(BaseModel):
    """Structured report returned by the deep-dive Forensic Earnings Analyst."""
    ticker: str
    company_name: str
    reporting_period: str = Field(description="Fiscal period analyzed, e.g. 'Q3 FY2026'")
    period_ended: Optional[str] = Field(default=None, description="Date the quarterly period ended, e.g. '2026-06-27'")
    filing_date: Optional[str] = Field(default=None, description="Date 10-Q/10-K/8-K was filed with SEC")
    filing_type: Optional[str] = Field(default="10-Q", description="Type of filing, e.g. '10-Q', '10-K', '8-K', or 'Custom Transcript'")
    
    # 1. Executive Summary & Core Verdict
    earnings_grade: Literal["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "D", "F"] = Field(
        description="Overall letter grade evaluating operational execution and reporting quality"
    )
    quality_score: float = Field(
        description="Accounting and earnings transparency rating from 1.0 to 10.0",
        ge=1.0, le=10.0
    )
    quality_score_breakdown: List[str] = Field(
        default_factory=list,
        description="2-3 specific accounting factors justifying the Quality Score (e.g. GAAP vs non-GAAP divergence, FCF conversion ratio, stock-based comp burden)"
    )
    guidance_trajectory: Literal["RAISED", "CONFIRMED", "LOWERED", "WITHDRAWN", "CAUTIOUS"] = Field(
        description="Directional momentum of management forward guidance"
    )
    executive_summary: str = Field(
        description="2-3 paragraph forensic executive synthesis of the quarterly performance"
    )

    # 2. Historical Beat/Miss Execution
    beat_miss_analysis: str = Field(
        description="Detailed review of EPS & revenue against Wall Street consensus estimates"
    )
    eps_surprise_summary: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Chronological quarters actual vs estimated EPS with surprise percentages, ALWAYS starting with the current audited quarter as row 1"
    )

    # 3. Revenue Quality & Cash Flow Conversion
    revenue_quality_analysis: str = Field(
        description="Analysis of organic top-line expansion, pricing power, and gross/operating margins"
    )
    cash_flow_conversion: str = Field(
        description="Reconciliation of reported Net Income to actual Free Cash Flow and capital allocation"
    )

    # 4. Forward Guidance & Management Credibility
    forward_guidance_analysis: str = Field(
        description="Assessment of management forward projections, product rollout timelines, and credibility"
    )
    management_credibility_score: float = Field(
        description="Score from 1.0 to 10.0 on management transparency vs evasiveness",
        ge=1.0, le=10.0
    )
    management_credibility_breakdown: List[str] = Field(
        default_factory=list,
        description="2-3 specific guidance factors justifying Credibility Score (e.g. historical delivery vs promises, transparency on headwinds, realistic supply backlog)"
    )

    # 5. Red Flags & Accounting Integrity
    red_flags: List[str] = Field(
        default_factory=list,
        description="Identified risks: aggressive revenue recognition, inventory build, margin pressure, dilution"
    )
    accounting_integrity_rating: Literal["CLEAN", "MINOR_CONCERNS", "HIGH_RISK"] = Field(
        description="Forensic evaluation of GAAP compliance and disclosure cleanliness"
    )

    # Direct SEC Filing URLs
    sec_filing_links: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Direct links to SEC EDGAR exhibits for investor verification"
    )
