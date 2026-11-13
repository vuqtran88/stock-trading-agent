"""Unit tests for the multi-agent stock picking committee and SSE orchestrator."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from agents.personas.base import CIODossier, PersonaReport
from agents.orchestrator import AgentOrchestrator


@pytest.fixture
def mock_company_data():
    return {
        "ticker": "AAPL",
        "fundamentals": {
            "name": "Apple Inc.",
            "sector": "Technology",
            "market_cap": 3000000000000,
            "trailing_pe": 28.5,
            "forward_pe": 26.0,
            "current_price": 220.50,
        },
        "technicals": {
            "current_price": 220.50,
            "ema20": 218.00,
            "above_ema20": True,
            "rsi14": 58.5,
            "rsi_status": "Neutral",
        },
        "news": [
            {"title": "Apple Reports Record Services Revenue", "publisher": "Reuters", "link": ""},
            {"title": "New M4 Mac Lineup Unveiled", "publisher": "Bloomberg", "link": ""},
        ],
    }


@pytest.fixture
def mock_persona_report():
    return PersonaReport(
        persona_name="Fundamental Analyst",
        score=8.5,
        stance="BULLISH",
        key_findings=["Strong ROE above 40%", "Exceptional ecosystem pricing power"],
        summary="High quality business with durable competitive moat.",
    )


@pytest.fixture
def mock_cio_dossier():
    return CIODossier(
        ticker="AAPL",
        company_name="Apple Inc.",
        verdict="STRONG BUY",
        conviction_score=8.3,
        conviction_score_breakdown=[
            "Fundamental Analyst (35% weight): 8.5/10 × 0.35 = +2.98 pts",
            "Technical Analyst (25% weight): 8.0/10 × 0.25 = +2.00 pts",
            "Sentiment Analyst (20% weight): 9.0/10 × 0.20 = +1.80 pts",
            "Bearish Risk Advocate (Risk Safety, 20% weight): 7.5/10 × 0.20 = +1.50 pts",
        ],
        suggested_horizon="Swing (1-4 weeks)",
        executive_thesis="Exceptional fundamental stability paired with bullish EMA20 trend alignment.",
        key_catalysts=["M4 Mac demand cycle", "Services margin expansion"],
        primary_risks=["Valuation premium relative to historical average"],
        target_entry_zone="$218 - $221",
        stop_loss_level="$212",
        persona_scores={
            "Fundamental Analyst": 8.5,
            "Technical Analyst": 8.0,
            "Sentiment Analyst": 9.0,
            "Bearish Risk Advocate": 7.5,
        },
    )


@pytest.mark.asyncio
async def test_agent_orchestrator_analyze_ticker(mock_company_data, mock_persona_report, mock_cio_dossier):
    orchestrator = AgentOrchestrator()

    # Mock data tools and personas
    orchestrator.data_tools.get_company_context = AsyncMock(return_value=mock_company_data)
    orchestrator.fundamental.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.technical.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.sentiment.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.bear.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.cio.synthesize = AsyncMock(return_value=mock_cio_dossier)

    result = await orchestrator.analyze_ticker("AAPL")

    assert result["ticker"] == "AAPL"
    assert len(result["reports"]) == 4
    assert result["dossier"]["verdict"] == "STRONG BUY"
    assert result["dossier"]["conviction_score"] == 8.3
    assert len(result["dossier"]["conviction_score_breakdown"]) == 4


def test_compute_weighted_conviction_amd_example():
    from agents.personas.cio import compute_weighted_conviction

    scores = {
        "Fundamental Analyst": 6.8,
        "Technical Analyst": 8.5,
        "Sentiment Analyst": 8.5,
        "Bearish Risk Advocate": 3.5,
    }
    weighted_score, breakdown = compute_weighted_conviction(scores)
    # 6.8*0.35 (2.38) + 8.5*0.25 (2.125) + 8.5*0.20 (1.70) + 3.5*0.20 (0.70) = 6.905 -> 6.9
    assert weighted_score == 6.9
    assert len(breakdown) == 4
    assert "+2.38 pts" in breakdown[0]
    assert "+2.12 pts" in breakdown[1] or "+2.13 pts" in breakdown[1]
    assert "+1.70 pts" in breakdown[2]
    assert "+0.70 pts" in breakdown[3]


@pytest.mark.asyncio
async def test_agent_orchestrator_streaming_events(mock_company_data, mock_persona_report, mock_cio_dossier):
    orchestrator = AgentOrchestrator()

    orchestrator.data_tools.get_company_context = AsyncMock(return_value=mock_company_data)
    orchestrator.fundamental.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.technical.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.sentiment.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.bear.analyze = AsyncMock(return_value=mock_persona_report)
    orchestrator.cio.synthesize = AsyncMock(return_value=mock_cio_dossier)

    events = []
    async for chunk in orchestrator.stream_analysis("AAPL"):
        events.append(chunk)

    assert len(events) >= 5
    # Verify presence of key SSE events
    event_str = "".join(events)
    assert "data_ready" in event_str
    assert "persona_report" in event_str
    assert "final_dossier" in event_str
    assert "complete" in event_str

