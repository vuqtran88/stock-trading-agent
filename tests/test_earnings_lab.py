"""Unit tests for the standalone Forensic Earnings Lab."""

import pytest
from unittest.mock import AsyncMock, patch
from agents.earnings_lab.schema import ForensicEarningsDossier
from agents.earnings_lab.extractor import EarningsLabExtractor
from agents.earnings_lab.forensic_agent import ForensicEarningsAgent


@pytest.fixture
def mock_earnings_payload():
    return {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "target_period": "Q3 FY2026",
        "current_price": 338.50,
        "profit_margins": 0.276,
        "operating_margins": 0.326,
        "revenue_growth": 0.164,
        "eps_surprises": [
            {"date": "2026-07-30", "eps_estimate": 1.89, "reported_eps": 2.02, "surprise_pct": 6.88},
            {"date": "2026-04-30", "eps_estimate": 1.94, "reported_eps": 2.01, "surprise_pct": 3.61},
        ],
        "recent_filings": [
            {"type": "10-Q", "title": "Quarterly Report", "date": "2026-07-31", "edgar_url": "https://sec.gov"},
        ],
        "quarterly_income": {"Total Revenue": {"2026-06-30": 94000000000.0}},
        "quarterly_cashflow": {"Free Cash Flow": {"2026-06-30": 28000000000.0}},
    }


@pytest.fixture
def mock_forensic_dossier():
    return ForensicEarningsDossier(
        ticker="AAPL",
        company_name="Apple Inc.",
        reporting_period="Q3 FY2026",
        earnings_grade="A",
        quality_score=9.2,
        guidance_trajectory="RAISED",
        executive_summary="Flawless quarterly execution across both product and services ecosystems.",
        beat_miss_analysis="Exceeded Wall Street consensus by 6.88% on robust gross margin upside.",
        eps_surprise_summary=[{"date": "2026-07-30", "reported_eps": 2.02, "surprise_pct": 6.88}],
        revenue_quality_analysis="Organic double-digit revenue expansion driven by Services resilience.",
        cash_flow_conversion="Stellar conversion with Free Cash Flow matching 98% of reported Net Income.",
        forward_guidance_analysis="Management offered confident forward guidance citing accelerating upgrade cycles.",
        management_credibility_score=9.5,
        red_flags=["Consumer hardware upgrade cycle extension"],
        accounting_integrity_rating="CLEAN",
        sec_filing_links=[{"type": "10-Q", "title": "Quarterly Report", "url": "https://sec.gov"}],
    )


@pytest.mark.asyncio
async def test_forensic_agent_analyze_financials(mock_earnings_payload, mock_forensic_dossier):
    agent = ForensicEarningsAgent()
    agent.client.complete_structured = AsyncMock(return_value=mock_forensic_dossier)

    dossier = await agent.analyze_financials("AAPL", mock_earnings_payload)

    assert dossier.ticker == "AAPL"
    assert dossier.earnings_grade == "A"
    assert dossier.quality_score == 9.2
    assert dossier.accounting_integrity_rating == "CLEAN"


def test_pdf_extractor_mock():
    extractor = EarningsLabExtractor()
    # Test fallback on invalid bytes
    with pytest.raises(ValueError):
        extractor.extract_text_from_pdf(b"invalid_pdf_content")

