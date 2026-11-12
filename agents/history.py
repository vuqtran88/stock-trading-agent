"""Persistence store for AI Copilot historical analysis dossiers."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from config.settings import settings

logger = logging.getLogger(__name__)

ANALYSIS_HISTORY_FILE = settings.DATA_DIR / "copilot_history.json"


class CopilotHistoryStore:
    """Thread-safe persistent JSON store for AI Copilot historical analyses."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or (settings.DATA_DIR / "copilot_history.json")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save_analysis(
        self,
        ticker: str,
        company_name: str,
        dossier: Dict[str, Any],
        persona_reports: List[Dict[str, Any]],
        company_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Saves a new analysis session to history."""
        record_id = str(uuid.uuid4())[:8]
        now_utc = datetime.now(timezone.utc).isoformat()

        record = {
            "id": record_id,
            "timestamp": now_utc,
            "ticker": ticker.upper(),
            "company_name": company_name or dossier.get("company_name", ticker.upper()),
            "verdict": dossier.get("verdict", "HOLD"),
            "conviction_score": dossier.get("conviction_score", 5.0),
            "suggested_horizon": dossier.get("suggested_horizon", "N/A"),
            "target_entry_zone": dossier.get("target_entry_zone"),
            "stop_loss_level": dossier.get("stop_loss_level"),
            "dossier": dossier,
            "persona_reports": persona_reports,
            "company_data": company_data or {},
        }

        history = self.list_analyses(limit=200)
        # Prepend new record so latest comes first
        history.insert(0, record)

        try:
            with open(self.file_path, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist copilot analysis history: {e}")

        return record

    def list_analyses(self, limit: int = 50, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns list of past analyses with optional ticker filter."""
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                if ticker:
                    ticker_clean = ticker.strip().upper()
                    data = [item for item in data if item.get("ticker") == ticker_clean]
                return data[:limit]
        except Exception as e:
            logger.error(f"Failed to load copilot analysis history: {e}")
            return []

    def get_analysis_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single full dossier by ID."""
        for item in self.list_analyses(limit=200):
            if item.get("id") == record_id:
                return item
        return None

    def delete_analysis(self, record_id: str) -> bool:
        """Deletes a specific history record."""
        history = self.list_analyses(limit=200)
        initial_len = len(history)
        history = [item for item in history if item.get("id") != record_id]
        if len(history) != initial_len:
            try:
                with open(self.file_path, "w") as f:
                    json.dump(history, f, indent=2)
                return True
            except Exception as e:
                logger.error(f"Failed to save history after delete: {e}")
        return False

    def clear_history(self) -> None:
        """Clears all history."""
        if self.file_path.exists():
            try:
                self.file_path.unlink()
            except Exception as e:
                logger.error(f"Failed to clear history: {e}")

