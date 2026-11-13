"""Persistent JSON store for historical Forensic Earnings Lab audits."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
from agents.cloud_storage import load_synced_history, save_synced_history
from config.settings import settings

logger = logging.getLogger(__name__)

EARNINGS_HISTORY_FILE = settings.DATA_DIR / "earnings_history.json"
GCS_EARNINGS_HISTORY_OBJECT = "history/earnings_history.json"


class EarningsHistoryStore:
    """Stores deep-dive forensic earnings audit dossiers separately from committee history (synced with GCS)."""

    def __init__(self, file_path: Optional[Path] = None):
        self._using_default_path = file_path is None
        self.file_path = file_path or (settings.DATA_DIR / "earnings_history.json")
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_all(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        return load_synced_history(
            object_name=GCS_EARNINGS_HISTORY_OBJECT,
            local_path=self.file_path,
            using_default_path=self._using_default_path,
            force_refresh=force_refresh,
        )

    def _save_all(self, records: List[Dict[str, Any]]) -> None:
        save_synced_history(
            object_name=GCS_EARNINGS_HISTORY_OBJECT,
            local_path=self.file_path,
            records=records,
            using_default_path=self._using_default_path,
        )

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

        history = self._load_all()[:99]
        history.insert(0, record)
        self._save_all(history)
        return record

    def list_audits(self, limit: int = 50, ticker: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self._load_all()
        if ticker:
            t = ticker.strip().upper()
            data = [item for item in data if item.get("ticker") == t]
        return data[:limit]

    def get_audit_by_id(self, record_id: str) -> Optional[Dict[str, Any]]:
        for item in self._load_all():
            if item.get("id") == record_id:
                return item
        return None

    def delete_audit(self, record_id: str) -> bool:
        history = self._load_all()
        orig_len = len(history)
        history = [item for item in history if item.get("id") != record_id]
        if len(history) != orig_len:
            self._save_all(history)
            return True
        return False

