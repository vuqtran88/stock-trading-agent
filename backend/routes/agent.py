"""Agent Copilot endpoints: SSE streaming, single-ticker analysis, and universe screening."""

import asyncio
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from agents.orchestrator import AgentOrchestrator
from agents.history import CopilotHistoryStore
from agents.earnings_lab.extractor import EarningsLabExtractor
from agents.earnings_lab.forensic_agent import ForensicEarningsAgent
from agents.earnings_lab.history import EarningsHistoryStore
from backend.routes.auth import get_current_user, verify_token
from config.settings import settings
from fastapi import File, Form, UploadFile

router = APIRouter(prefix="/api/agent", tags=["AI Copilot"])
history_store = CopilotHistoryStore()
earnings_extractor = EarningsLabExtractor()
earnings_agent = ForensicEarningsAgent()
earnings_history_store = EarningsHistoryStore()


class ScreenRequest(BaseModel):
    tickers: Optional[List[str]] = None
    limit: int = 3


@router.get("/stream")
async def stream_analysis(
    request: Request,
    ticker: str = Query(..., description="Stock symbol to analyze, e.g. NVDA"),
    token: Optional[str] = Query(None, description="Auth token for SSE connections"),
):
    """Streams real-time persona analysis and CIO synthesis via Server-Sent Events (SSE)."""
    if not (token and verify_token(token)):
        get_current_user(request)

    orchestrator = AgentOrchestrator()

    return StreamingResponse(
        orchestrator.stream_analysis(ticker),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/analyze/{ticker}")
async def analyze_ticker(
    ticker: str,
    user: str = Depends(get_current_user),
):
    """Synchronous fallback returning the full committee dossier."""
    orchestrator = AgentOrchestrator()
    result = await orchestrator.analyze_ticker(ticker)
    return result


@router.post("/screen")
async def screen_universe(
    req: ScreenRequest,
    user: str = Depends(get_current_user),
):
    """Runs committee analysis across active universe symbols and ranks top recommendations."""
    universe = req.tickers or settings.TICKERS
    orchestrator = AgentOrchestrator()

    # Limit concurrent analyses to avoid rate limiting
    results = []
    for symbol in universe[:8]:  # inspect up to 8 symbols
        try:
            res = await orchestrator.analyze_ticker(symbol)
            dossier = res.get("dossier", {})
            results.append({
                "ticker": symbol,
                "company_name": dossier.get("company_name", symbol),
                "verdict": dossier.get("verdict", "HOLD"),
                "conviction_score": dossier.get("conviction_score", 5.0),
                "suggested_horizon": dossier.get("suggested_horizon", "Swing"),
                "executive_thesis": dossier.get("executive_thesis", ""),
                "target_entry_zone": dossier.get("target_entry_zone", "N/A"),
                "stop_loss_level": dossier.get("stop_loss_level", "N/A"),
            })
        except Exception as e:
            continue

    # Rank by conviction score descending
    results.sort(key=lambda x: x["conviction_score"], reverse=True)
    return {
        "screened_count": len(results),
        "top_picks": results[:req.limit],
        "all_ranked": results,
    }


@router.get("/history")
def get_analysis_history(
    limit: int = Query(50, ge=1, le=200),
    ticker: Optional[str] = Query(None),
    user: str = Depends(get_current_user),
):
    """Retrieve historical copilot analyses."""
    return history_store.list_analyses(limit=limit, ticker=ticker)


@router.get("/history/{record_id}")
def get_analysis_record(
    record_id: str,
    user: str = Depends(get_current_user),
):
    """Retrieve a single historical analysis dossier by ID."""
    record = history_store.get_analysis_by_id(record_id)
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Analysis record not found")
    return record


@router.delete("/history/{record_id}")
def delete_analysis_record(
    record_id: str,
    user: str = Depends(get_current_user),
):
    """Delete a single analysis record."""
    success = history_store.delete_analysis(record_id)
    return {"success": success}


# ---------------------------------------------------------------------------
# Earnings Intelligence Lab Endpoints
# ---------------------------------------------------------------------------

class EarningsAuditRequest(BaseModel):
    ticker: str
    target_period: Optional[str] = None
    custom_transcript: Optional[str] = None


@router.get("/earnings/preview")
async def preview_earnings_metadata(
    ticker: str = Query(..., description="Stock symbol, e.g. AAPL"),
    user: str = Depends(get_current_user),
):
    """Fast preview endpoint resolving latest quarter, fiscal year, and SEC reports for user confirmation."""
    return await earnings_extractor.preview_metadata(ticker)


@router.post("/earnings/audit")
async def run_forensic_earnings_audit(
    req: EarningsAuditRequest,
    user: str = Depends(get_current_user),
):
    """Executes the deep-dive 5-part forensic earnings audit."""
    financial_payload = await earnings_extractor.get_deep_financials(
        ticker=req.ticker,
        target_period=req.target_period,
    )
    dossier = await earnings_agent.analyze_financials(
        ticker=req.ticker,
        financial_payload=financial_payload,
        custom_transcript=req.custom_transcript,
    )
    saved_record = earnings_history_store.save_audit(
        ticker=req.ticker,
        company_name=dossier.company_name,
        reporting_period=dossier.reporting_period,
        dossier=dossier.model_dump(),
        raw_payload=financial_payload,
    )
    return {
        "id": saved_record.get("id"),
        "dossier": dossier.model_dump(),
        "financial_payload": financial_payload,
    }


@router.post("/earnings/upload")
async def upload_earnings_document(
    ticker: str = Form(...),
    target_period: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    transcript_text: Optional[str] = Form(None),
    user: str = Depends(get_current_user),
):
    """Accepts custom PDF earnings release or raw pasted transcript text for deep forensic audit."""
    custom_text = transcript_text or ""
    if file:
        file_bytes = await file.read()
        if file.filename.lower().endswith(".pdf"):
            extracted = earnings_extractor.extract_text_from_pdf(file_bytes)
            custom_text = f"{custom_text}\n\n{extracted}".strip()
        else:
            custom_text = f"{custom_text}\n\n{file_bytes.decode('utf-8', errors='ignore')}".strip()

    financial_payload = await earnings_extractor.get_deep_financials(
        ticker=ticker,
        target_period=target_period or "Custom Uploaded Document",
    )
    dossier = await earnings_agent.analyze_financials(
        ticker=ticker,
        financial_payload=financial_payload,
        custom_transcript=custom_text,
    )
    saved_record = earnings_history_store.save_audit(
        ticker=ticker,
        company_name=dossier.company_name,
        reporting_period=dossier.reporting_period,
        dossier=dossier.model_dump(),
        raw_payload=financial_payload,
    )
    return {
        "id": saved_record.get("id"),
        "dossier": dossier.model_dump(),
    }


@router.get("/earnings/history")
def get_earnings_history(
    limit: int = Query(50, ge=1, le=100),
    ticker: Optional[str] = Query(None),
    user: str = Depends(get_current_user),
):
    """Retrieve historical forensic earnings audits."""
    return earnings_history_store.list_audits(limit=limit, ticker=ticker)


@router.get("/earnings/history/{record_id}")
def get_earnings_history_record(
    record_id: str,
    user: str = Depends(get_current_user),
):
    """Retrieve a single saved forensic earnings dossier by ID."""
    record = earnings_history_store.get_audit_by_id(record_id)
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Earnings audit record not found")
    return record


@router.delete("/earnings/history/{record_id}")
def delete_earnings_history_record(
    record_id: str,
    user: str = Depends(get_current_user),
):
    """Delete a saved earnings audit."""
    success = earnings_history_store.delete_audit(record_id)
    return {"success": success}


@router.delete("/history")
def clear_all_history(
    user: str = Depends(get_current_user),
):
    """Clear all analysis history."""
    history_store.clear_history()
    return {"success": True, "message": "Copilot history cleared"}

