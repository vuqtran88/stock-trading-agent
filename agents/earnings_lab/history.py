"""Persistent JSON store for historical Forensic Earnings Lab audits."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from config.settings import settings

logger = logging.getLogger(__name__)

EARNINGS_HISTORY_FILE = settings.DATA_DIR / "earnings_history.json"


class EarningsHistoryStore:
    """Stores deep-dive forensic earnings audit dossiers separately from committee history."""

    def __init__(self, file_path: Optional[Path] = None):
        self.file_path = file_path or (settings.DATA_DIR / "earnings_history.json")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def save_audit(
        self,
        ticker: str,
        company_name: str,
        reporting_period: str,
        dossier: Dict[str, Any],
        raw_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        record_id = str(uuid.uuid4())[:8]
        now_utc = datetime.now(timezone.utc).isoformat()

        record = {
            "id": record_id,
            "timestamp": now_utc,
            "ticker": ticker.upper(),
            "company_name": company_name or dossier.get("company_name", ticker.upper()),
            "reporting_period": reporting_period or dossier.get("reporting_period", "Recent"),
            "earnings_grade": dossier.get("earnings_grade", "B"),
            "quality_score": dossier.get("quality_score", 7.0),
            "guidance_trajectory": dossier.get("guidance_trajectory", "CONFIRMED"),
            "dossier": dossier,
            "raw_payload": raw_payload or {},
        }

        history = self.list_audits(limit=100)
        history.insert(0, record)

        try:
            with open(self.file_path, "w") as f:
                json.dump(history, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to persist earnings audit history: {e}")

        return record

    def list_audits(self, limit: int = 50, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            return []
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
                if not isinstance(data, list):
                    return []
                if ticker:
                    t = ticker.strip().upper()
                    data = [item for item in data if item.get("ticker") == t]
                return data[:limit]
        except Exception as e:
            logger.error(f"Failed to load earnings history: {e}")
            return []

    def get_audit_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        for item in self.list_audits(limit=100):
            if item.get("id") == record_id:
                return item
        return None

    def delete_audit(self, record_id: str) -> bool:
        history = self.list_audits(limit=100)
        orig_len = len(history)
        history = [item for item in history if item.get("id") != record_id]
        if len(history) != orig_len:
            try:
                with open(self.file_path, "w") as f:
                    json.dump(history, f, indent=2)
                return True
            except Exception as e:
                logger.error(f"Failed to save earnings history after delete: {e}")
        return False

