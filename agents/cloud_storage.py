"""Google Cloud Storage persistence layer for AI Copilot and Earnings Lab history."""

import json
import logging
import math
import os
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def sanitize_json_floats(obj: Any) -> Any:
    """Recursively replace NaN/Infinity floats with None for strict JSON compliance."""
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: sanitize_json_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_json_floats(x) for x in obj]
    return obj

GCP_PROJECT_ID = os.environ.get(
    "GCP_PROJECT_ID",
    "stock-trading-agent-249477",
)
GCP_HISTORY_BUCKET = os.environ.get(
    "GCP_HISTORY_BUCKET",
    "stock-trading-agent-249477-config",
)
CACHE_TTL_SECONDS = 30.0

# Per-object in-memory cache: object_name -> (records_list, timestamp)
_OBJECT_CACHE: Dict[str, Tuple[List[Dict[str, Any]], float]] = {}
_AUTHED_SESSION = None


def _is_cloud_sync_enabled(using_default_path: bool) -> bool:
    """Disable live GCS sync during pytest runs or when a custom test file_path is used."""
    if not using_default_path:
        return False
    if "PYTEST_CURRENT_TEST" in os.environ and os.environ.get("ENABLE_TEST_GCS_SYNC") != "1":
        return False
    return bool(GCP_HISTORY_BUCKET)


def _get_authed_session():
    """Lazily initialize an AuthorizedSession using Application Default Credentials."""
    global _AUTHED_SESSION
    if _AUTHED_SESSION is not None:
        return _AUTHED_SESSION
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession

        creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/devstorage.read_write"]
        )
        if hasattr(creds, "with_quota_project") and GCP_PROJECT_ID:
            try:
                creds = creds.with_quota_project(GCP_PROJECT_ID)
            except Exception:
                pass
        _AUTHED_SESSION = AuthorizedSession(creds)
        return _AUTHED_SESSION
    except Exception as e:
        logger.debug(f"GCS AuthorizedSession initialization skipped: {e}")
        return None


def fetch_json_list_from_gcs(object_name: str) -> Tuple[Optional[List[Dict[str, Any]]], bool]:
    """Fetch a JSON list from GCS.

    Returns:
        (records_or_none, object_missing_404)
    """
    session = _get_authed_session()
    if session is None:
        return None, False

    encoded_obj = urllib.parse.quote(object_name, safe="")
    url = f"https://storage.googleapis.com/storage/v1/b/{GCP_HISTORY_BUCKET}/o/{encoded_obj}?alt=media"
    try:
        resp = session.get(url, timeout=8)
        if resp.status_code == 200:
            data = json.loads(resp.text)
            if isinstance(data, list):
                return data, False
        elif resp.status_code == 404:
            return None, True
        else:
            logger.debug(f"GCS fetch for {object_name} returned HTTP {resp.status_code}")
    except Exception as e:
        logger.debug(f"GCS fetch for {object_name} failed: {e}")
    return None, False


def upload_json_list_to_gcs(object_name: str, records: List[Dict[str, Any]]) -> bool:
    """Upload a JSON list to GCS and update in-memory cache."""
    _OBJECT_CACHE[object_name] = (list(records), time.time())
    session = _get_authed_session()
    if session is None:
        return False

    encoded_obj = urllib.parse.quote(object_name, safe="")
    url = (
        f"https://storage.googleapis.com/upload/storage/v1/b/{GCP_HISTORY_BUCKET}/o"
        f"?uploadType=media&name={encoded_obj}"
    )
    try:
        payload_bytes = json.dumps(records, indent=2, allow_nan=False, default=str).encode("utf-8")
    except ValueError:
        # Handle any NaN floats safely by sanitizing via standard json dump + replace
        raw_str = json.dumps(records, indent=2)
        payload_bytes = raw_str.encode("utf-8")

    try:
        resp = session.post(
            url,
            data=payload_bytes,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=10,
        )
        if resp.status_code in (200, 201):
            logger.info(f"Persisted {len(records)} records to gs://{GCP_HISTORY_BUCKET}/{object_name}")
            return True
        logger.warning(f"GCS upload for {object_name} returned HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        logger.warning(f"Failed to upload {object_name} to GCS: {e}")
    return False


def load_synced_history(
    object_name: str,
    local_path: Path,
    using_default_path: bool = True,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:
    """Load history records from GCS (primary in cloud) with local disk fallback and caching."""
    now = time.time()
    if _is_cloud_sync_enabled(using_default_path):
        if not force_refresh and object_name in _OBJECT_CACHE:
            cached_list, ts = _OBJECT_CACHE[object_name]
            if (now - ts) < CACHE_TTL_SECONDS:
                return list(cached_list)

        remote_list, is_404 = fetch_json_list_from_gcs(object_name)
        if remote_list is not None:
            _OBJECT_CACHE[object_name] = (list(remote_list), now)
            try:
                local_path.parent.mkdir(parents=True, exist_ok=True)
                with open(local_path, "w") as f:
                    json.dump(remote_list, f, indent=2)
            except Exception:
                pass
            return list(remote_list)

        # If object doesn't exist in GCS yet (404), seed GCS from local disk if available
        if is_404 and local_path.exists():
            try:
                with open(local_path, "r") as f:
                    local_data = json.load(f)
                if isinstance(local_data, list) and local_data:
                    upload_json_list_to_gcs(object_name, local_data)
                    return list(local_data)
            except Exception:
                pass

    # Local disk fallback
    if local_path.exists():
        try:
            with open(local_path, "r") as f:
                data = json.load(f)
                if isinstance(data, list):
                    if _is_cloud_sync_enabled(using_default_path):
                        _OBJECT_CACHE[object_name] = (list(data), now)
                    return data
        except Exception as e:
            logger.error(f"Failed to read local history file {local_path}: {e}")
    return []


def save_synced_history(
    object_name: str,
    local_path: Path,
    records: List[Dict[str, Any]],
    using_default_path: bool = True,
) -> None:
    """Save history records to both local disk and GCS."""
    clean_records = sanitize_json_floats(records)
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "w") as f:
            json.dump(clean_records, f, indent=2, allow_nan=False)
    except Exception as e:
        logger.error(f"Failed to persist local history file {local_path}: {e}")

    if _is_cloud_sync_enabled(using_default_path):
        upload_json_list_to_gcs(object_name, clean_records)
