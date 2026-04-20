"""Drake automation API routes - queues tasks to Celery."""
import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from drake_service.schemas.drake_schemas import (
    DrakeLaunchPayload,
    PrintReturnPayload,
    EfileBatchPayload,
    EfileStatusBatchPayload,
    FIBatchPayload,
    EfileStatusCheckPayload,
)
from drake_service.tasks.automation_tasks import (
    run_drake_launch,
    run_query_clients,
    run_print_return,
    run_efile_batch,
    run_efile_status_batch,
    run_fi_batch,
    run_efile_status_open_session,
    run_efile_status_check_client,
    run_efile_status_close_session,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Drake Automation"])


def _task_response(task_id: str, status: str = "pending") -> Dict[str, Any]:
    return {"task_id": task_id, "status": status}


@router.post("/drake/launch")
async def launch_drake(request: DrakeLaunchPayload):
    """Queue Drake fill-in flow. Returns task_id for polling."""
    if not request or not request.data:
        raise HTTPException(status_code=400, detail="No data provided for automation.")
    payload = request.model_dump()
    task = run_drake_launch.delay(payload)
    return _task_response(task.id)


@router.post("/drake/query-clients")
async def query_drake_clients():
    """Queue Drake client export flow."""
    task = run_query_clients.delay()
    return _task_response(task.id)


@router.post("/drake/print-return")
async def print_drake_return(request: PrintReturnPayload):
    """Queue Drake print return flow."""
    payload = request.model_dump()
    task = run_print_return.delay(payload)
    return _task_response(task.id)


@router.post("/drake/efile/run-batch")
async def run_efile_batch_endpoint(request: EfileBatchPayload):
    """
    Queue Drake efile batch: open + select clients + close.
    Replaces open -> select-clients -> close flow.
    """
    if not request.client_ids:
        return {"status": "skipped", "message": "No client IDs provided", "processed_count": 0, "client_status": "Unknown"}
    payload = {
        "client_ids": request.client_ids,
        "open": request.open,
        "close": request.close
    }
    task = run_efile_batch.delay(payload)
    return _task_response(task.id)


@router.post("/karbon/process-efile-status")
async def process_efile_status_internal(request: EfileStatusBatchPayload):
    """
    Queue efile status batch. Body: { "targets": [...] }.
    Service A fetches Karbon items and sends targets.
    """
    targets = request.targets
    if not targets:
        return {"task_id": None, "status": "skipped", "message": "No targets"}
    task = run_efile_status_batch.delay({"targets": targets})
    return _task_response(task.id)


@router.post("/karbon/process-fi")
async def process_fi_internal(request: FIBatchPayload):
    """
    Queue FI batch. Body: { "targets": [...], "close_drake": true }.
    Service A fetches Karbon items and sends targets.
    """
    targets = request.targets
    if not targets:
        return {"task_id": None, "status": "skipped", "message": "No targets"}
    payload = {"targets": targets, "close_drake": request.close_drake}
    task = run_fi_batch.delay(payload)
    return _task_response(task.id)


# --- New E-file Status Interactive Endpoints ---

@router.post("/drake/efile-status/open")
async def efile_status_open_session():
    """Queue opening a persistent Drake e-file status session."""
    try:
        task = run_efile_status_open_session.delay()
        return _task_response(task.id)
    except Exception as exc:
        logger.error("Failed to queue Drake e-file status session opening", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while queueing Drake status session task")


@router.post("/drake/efile-status/check-client")
async def efile_status_check_client(request: EfileStatusCheckPayload):
    """Queue a check for one client's e-file status."""
    payload = request.model_dump(exclude_none=True)
    client_id = payload.get("client_id")
    client_name = payload.get("client_name")
    work_item_key = payload.get("work_item_key")

    logger.info(
        "E-file status check request received for queueing",
        extra={
            "client_id": client_id,
            "client_name": client_name,
            "work_item_key": work_item_key,
        },
    )

    try:
        if not client_id:
            raise ValueError("client_id is required")

        task = run_efile_status_check_client.delay(payload)
        return _task_response(task.id)
    except ValueError as exc:
        logger.warning(
            "Invalid e-file status check input",
            extra={"client_id": client_id, "work_item_key": work_item_key, "error": str(exc)},
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error(
            "Failed to queue Drake lookup",
            extra={"client_id": client_id, "work_item_key": work_item_key, "error": str(exc)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Internal server error while queueing Drake status check")


@router.post("/drake/efile-status/close")
async def efile_status_close_session():
    """Queue closing the persistent Drake e-file status session."""
    try:
        task = run_efile_status_close_session.delay()
        return _task_response(task.id)
    except Exception as exc:
        logger.error("Failed to queue Drake e-file status session closing", extra={"error": str(exc)}, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error while queueing Drake status session close task")

@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Poll task status and result."""
    from drake_service.core.celery_app import celery_app

    result = celery_app.AsyncResult(task_id)
    if result.state == "PENDING":
        return {"task_id": task_id, "status": "pending", "result": None}
    if result.state == "SUCCESS":
        return {"task_id": task_id, "status": "success", "result": result.result}
    if result.state == "FAILURE":
        return {"task_id": task_id, "status": "failure", "result": None, "error": str(result.result)}
    return {"task_id": task_id, "status": result.state.lower(), "result": result.result}
