"""Async multi-agent orchestrator managing parallel persona execution and SSE event streaming."""

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
from agents.client import LLMClient
from agents.data_tools import AgentDataTools
from agents.personas.base import CIODossier, PersonaReport
from agents.personas.fundamental import FundamentalAnalyst
from agents.personas.technical import TechnicalAnalyst
from agents.personas.sentiment import SentimentAnalyst
from agents.personas.bear_advocate import BearAdvocate
from agents.personas.cio import CIOSynthesizer
from agents.history import CopilotHistoryStore

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Coordinates data gathering, parallel persona analysis, CIO synthesis, and real-time streaming."""

    def __init__(self, model: Optional[str] = None):
        self.client = LLMClient(model=model)
        self.data_tools = AgentDataTools()
        self.history_store = CopilotHistoryStore()
        self.fundamental = FundamentalAnalyst(self.client)
        self.technical = TechnicalAnalyst(self.client)
        self.sentiment = SentimentAnalyst(self.client)
        self.bear = BearAdvocate(self.client)
        self.cio = CIOSynthesizer(self.client)

    async def analyze_ticker(self, ticker: str) -> Dict[str, Any]:
        """Runs the complete committee analysis on a single ticker and returns the final result dict."""
        ticker = ticker.upper()
        company_data = await self.data_tools.get_company_context(ticker)

        # Run 4 specialist personas in parallel
        reports: List[PersonaReport] = await asyncio.gather(
            self.fundamental.analyze(company_data),
            self.technical.analyze(company_data),
            self.sentiment.analyze(company_data),
            self.bear.analyze(company_data),
        )

        dossier: CIODossier = await self.cio.synthesize(company_data, reports)

        # Save to history store
        history_record = self.history_store.save_analysis(
            ticker=ticker,
            company_name=company_data.get("fundamentals", {}).get("name", ticker),
            dossier=dossier.model_dump(),
            persona_reports=[r.model_dump() for r in reports],
            company_data=company_data,
        )

        return {
            "id": history_record.get("id"),
            "ticker": ticker,
            "company_data": company_data,
            "reports": [r.model_dump() for r in reports],
            "dossier": dossier.model_dump(),
        }

    async def stream_analysis(self, ticker: str) -> AsyncGenerator[str, None]:
        """Streams real-time progress events as Server-Sent Events (SSE) data chunks."""
        ticker = ticker.upper()

        def make_sse(event_type: str, data: Any) -> str:
            payload = json.dumps({"event": event_type, "data": data})
            return f"event: {event_type}\ndata: {payload}\n\n"

        # Step 1: Ingesting Market Data
        yield make_sse("status", {"message": f"Fetching market fundamentals, technicals, and news for {ticker}..."})
        try:
            company_data = await self.data_tools.get_company_context(ticker)
            yield make_sse("data_ready", {
                "ticker": ticker,
                "name": company_data.get("fundamentals", {}).get("name", ticker),
                "sector": company_data.get("fundamentals", {}).get("sector", "N/A"),
                "current_price": company_data.get("fundamentals", {}).get("current_price"),
            })
        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            yield make_sse("error", {"message": f"Failed to fetch market data: {str(e)}"})
            return

        # Step 2: Convening Personas concurrently
        yield make_sse("status", {"message": "Convening specialist personas in parallel..."})

        # Wrappers to yield event as soon as each individual persona completes
        async def run_and_notify(persona_fn, persona_name: str) -> PersonaReport:
            yield_msg = {"persona": persona_name, "status": "started"}
            # We cannot yield directly across inner generator easily, so we run tasks and gather
            res = await persona_fn(company_data)
            return res

        # Run personas as tasks
        tasks = [
            asyncio.create_task(self.fundamental.analyze(company_data)),
            asyncio.create_task(self.technical.analyze(company_data)),
            asyncio.create_task(self.sentiment.analyze(company_data)),
            asyncio.create_task(self.bear.analyze(company_data)),
        ]

        reports = []
        for completed_task in asyncio.as_completed(tasks):
            try:
                report = await completed_task
                reports.append(report)
                yield make_sse("persona_report", report.model_dump())
            except Exception as e:
                logger.error(f"Persona analysis error: {e}")
                yield make_sse("error", {"message": f"Specialist analysis warning: {str(e)}"})

        # Step 3: CIO Synthesis
        yield make_sse("status", {"message": "CIO is adjudicating debate and synthesizing final dossier..."})
        try:
            dossier = await self.cio.synthesize(company_data, reports)
            
            # Save completed analysis to history store
            history_record = self.history_store.save_analysis(
                ticker=ticker,
                company_name=company_data.get("fundamentals", {}).get("name", ticker),
                dossier=dossier.model_dump(),
                persona_reports=[r.model_dump() for r in reports],
                company_data=company_data,
            )

            dossier_payload = dossier.model_dump()
            dossier_payload["history_id"] = history_record.get("id")
            yield make_sse("final_dossier", dossier_payload)
        except Exception as e:
            logger.error(f"CIO synthesis error: {e}")
            yield make_sse("error", {"message": f"CIO synthesis failed: {str(e)}"})

        yield make_sse("complete", {"ticker": ticker, "status": "success", "history_id": history_record.get("id") if 'history_record' in locals() else None})

