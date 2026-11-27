"""Local, atomic forecast-run snapshots for bounded synchronous executions."""

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from backend.api.schemas.batch_forecast import BatchResponse
from backend.services.batch_forecast_service import generate_batch
from backend.services import operational_store
from src.decisionos.config import Settings

logger = logging.getLogger(__name__)


def run_directory():
    return Settings.project_path(os.environ.get("DECISIONOS_FORECAST_RUN_DIR", "forecast_runs"))


def _path(run_id):
    identifier = str(UUID(str(run_id)))
    return run_directory() / f"{identifier}.json"


def _write(record):
    if operational_store.enabled():
        operational_store.put("forecast_run", record["run_id"], record)
        return
    directory = run_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as handle:
        temporary = Path(handle.name)
        try:
            json.dump(record, handle, allow_nan=False)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            handle.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, _path(record["run_id"]))
    finally:
        temporary.unlink(missing_ok=True)


def get_run(run_id):
    if operational_store.enabled():
        try:
            return operational_store.get("forecast_run", str(UUID(str(run_id))))
        except FileNotFoundError:
            pass  # Existing local snapshots remain readable; never imported automatically.
    path = _path(run_id)
    if not path.is_file():
        raise FileNotFoundError("Forecast run not found.")
    return json.loads(path.read_text(encoding="utf-8"))


def list_runs(limit=20):
    if operational_store.enabled():
        return [{key: value for key, value in record.items() if key != "result"}
                for record in operational_store.recent("forecast_run", limit)]
    directory = run_directory()
    if not directory.is_dir():
        return []
    paths = sorted(directory.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)[:limit]
    return [{key: value for key, value in json.loads(path.read_text(encoding="utf-8")).items()
             if key != "result"} for path in paths]


def execute_run(request):
    record = {"run_id": str(uuid4()), "status": "running",
              "created_at": datetime.now(timezone.utc).isoformat(),
              "request": request.model_dump(mode="json"), "completed_pairs": 0, "total_pairs": None}
    _write(record)

    def progress(completed, total):
        record.update(completed_pairs=completed, total_pairs=total)
        _write(record)

    try:
        result = generate_batch(request, progress=progress)
        record["result"] = BatchResponse.model_validate(result).model_dump(mode="json")
        record["status"] = "completed"
    except Exception:
        logger.exception("Forecast run failed run_id=%s", record["run_id"])
        record.update(status="failed", error="Forecast run failed. Check server logs for details.")
        _write(record)
        raise
    _write(record)
    return record
