"""
Unified FastAPI application for Badger Automation
Handles all tax form types (1065, 1120, 1120-S) with Web UI
"""
import os
import json
import shutil
import logging
import math
import time
import re
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
from enum import Enum
import pandas as pd

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Form, Query, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response
from fastapi.exceptions import RequestValidationError
import csv
from io import StringIO
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest
from AI_Page.di_client import extract_pages_text_smart, debug_split_pages_to_output
from pydantic import BaseModel, Field
from AI_Page.llm_client import find_page_map_with_llm, llm_extract_single_prompt

# Import unified pipeline and config
from core import run_pipeline
from core.config import get_form_config, get_page_detection_mapping
from core.utils import get_pdf_page_count
from core.excel_export import generate_unified_excel
from extractFilingInstructions.routes import router as filing_instructions_router

# Karbon API imports

from fastapi import APIRouter
from api.automation_routes import workitems_router
from services.karbon_service import (
    get_karbon_work_items_for_efile_status,
    update_work_items_for_efile_status,
    get_karbon_work_items_for_FI_status,
)
from typing import List, Dict, Any, Set
import asyncio

from DrakeAutomation.ocr_normalization import normalize_id
from DrakeAutomation.config import (
    DRAKE24_CWD,
    DRAKE24_EXE,
    DRAKE24_TITLE,
    DRAKE_CWD,
    DRAKE_EXE,
    DRAKE_TITLE,
    EXPORT_FOLDER,
)
from services.drake_service import check_clients_status_in_drake, open_efile_session as open_efile_status_session_svc, clear_find_client_dialog
from services.drake_service_client import (
    call_drake_launch,
    start_drake_launch,
    get_task_status,
    call_query_clients,
    call_print_return,
    call_efile_run_batch,
    call_process_efile_status,
    call_process_fi,
    call_efile_status_check_client,
    call_efile_status_open_session,
    call_efile_status_close_session,
    get_workitem_status,
    get_ocr_results,
    enqueue_workitems,
    enqueue_fi_workitems,
    check_can_trigger,
    update_workitem_status,
    trigger_process_fi,
    upsert_ocr_result,
)

from services.email_service import (
    send_email,
    build_efile_status_summary_email,
    build_fi_processing_summary_email,
    build_ocr_completion_email,
    build_efile_batch_summary_email,
    compute_efile_totals_from_details,
    build_drake_completion_email,
)
from dotenv import load_dotenv
load_dotenv()



# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logging.getLogger("pypdf").setLevel(logging.ERROR)
logging.getLogger("pypdf._reader").setLevel(logging.ERROR)

app = FastAPI(title="Badger Automation - Tax Document Processing")
app.include_router(filing_instructions_router, prefix="/api/filing-instructions", tags=["Filing Instructions"])
app.include_router(workitems_router)

router = APIRouter(prefix="/api/karbon", tags=["Karbon"])
GLOBAL_DRAKE_SESSION = None
_DRAKE_LOCK = asyncio.Lock()
GLOBAL_EFILE_STATUS_CONTEXT = {
    "session": None,
    "win": None,
    "efile": None
}

@app.exception_handler(TimeoutError)
async def timeout_exception_handler(request: Request, exc: TimeoutError):
    """Custom handler for pywinauto TimeoutError to return a specific status code."""
    logger.error(f"Automation Timeout: {exc}", exc_info=True)

    # Send alert email for critical automation timeouts
    try:
        user_email = os.getenv("USER_EMAIL")
        if user_email:
            # Extract screenshot path from exception message if present
            screenshot_path = None
            error_message = str(exc)
            match = re.search(r"Screenshot saved at: (.+)", error_message)
            if match:
                screenshot_path = match.group(1).strip()
                error_message = error_message.replace(match.group(0), "").strip()

            subject = "[Badger] Drake Automation Error: Window Not Active"
            html_body = f"""
            <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
                <h2 style="color: #d9534f;">Drake Automation Error</h2>
                <p>The automation process was interrupted because a required window was not found or active.</p>
                <p><strong>Error Details:</strong> {error_message}</p>
                <p>The batch process has been stopped.</p>
            </div>
            """
            text_body = f"Drake Automation Error: Window Not Active.\nDetails: {error_message}"
            
            attachments = [screenshot_path] if screenshot_path and os.path.exists(screenshot_path) else []
            await asyncio.to_thread(send_email, user_email, subject, html_body, text_body, attachments=attachments)
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")

    return JSONResponse(
        status_code=408,  # Request Timeout
        content={"detail": f"Automation timed out waiting for a window or control: {str(exc)}"},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log detailed validation errors for 422 responses"""
    logger.error(f"❌ Validation Error: {exc.errors()}")
    try:
        body = await request.body()
        logger.error(f"❌ Request Body: {body.decode('utf-8', errors='ignore')}")
    except Exception as e:
        logger.error(f"Could not read request body: {e}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )

W2_NUMERIC_LABELS = {
    "wages, tips, other compensation",
    "federal income tax withheld",
    "social security wages",
    "social security tax withheld",
    "medicare wages and tips",
    "medicare tax withheld",
    "social security tips",
    "allocated tips",
    "dependent care benefits",
    "nonqualified plans",
    "amount",
    "state wages, tips, etc.",
    "state income tax",
    "local wages, tips, etc.",
    "local income tax",
}


def _normalize_numeric_input(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value) if math.isfinite(value) else None
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if cleaned == "":
        return None
    cleaned = re.sub(r"[,\s$€£¥]", "", cleaned)
    cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
    if cleaned in ("", ".", "-", "-."):
        return None
    is_negative = cleaned.startswith("-")
    cleaned = cleaned.replace("-", "")
    parts = cleaned.split(".")
    if len(parts) > 1:
        cleaned = f"{parts[0]}.{''.join(parts[1:])}"
    if is_negative:
        cleaned = f"-{cleaned}"
    try:
        num = float(cleaned)
    except ValueError:
        return None
    return num if math.isfinite(num) else None


def _format_two_decimal(value) -> str:
    num = _normalize_numeric_input(value)
    if num is None:
        return "0.00"
    return f"{num:.2f}"


def _is_w2_numeric_label(label: str) -> bool:
    if not label:
        return False
    return label.strip().lower() in W2_NUMERIC_LABELS

class DrakeCompletionNotifyRequest(BaseModel):
    clientName: str = Field(..., alias='clientName')
    clientId: str = Field(..., alias='clientId')
    formType: str = Field(..., alias='formType')
    items: int
    status: str
    errorMessage: Optional[str] = Field(None, alias='errorMessage')
    jobId: Optional[str] = Field(None, alias='jobId')

class CSPMiddleware(BaseHTTPMiddleware):
    """Add Content Security Policy headers to allow SheetJS and other necessary sources"""
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        # Set CSP header that allows SheetJS (which may use eval) and CDN sources
        # Note: unsafe-eval is required for SheetJS library to work properly
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "img-src 'self' data: https:; "
            "font-src 'self' https://cdnjs.cloudflare.com https://cdn.jsdelivr.net; "
            "connect-src 'self' http://localhost:* https://localhost:*; "
            "frame-src 'self' blob:"
        )
        # Set CSP for all responses (browser will only use it for HTML)
        if hasattr(response, 'headers'):
            response.headers["Content-Security-Policy"] = csp_policy
        return response


# Add CSP middleware before CORS
app.add_middleware(CSPMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Base output directory
BASE_OUTPUT_DIR = Path(os.getenv("AUTOMATION_OUTPUTS_DIR", Path(__file__).parent / "outputs"))
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

@router.get("/efile/workitems")
async def efile_workitems(
    top: int = Query(100, ge=1, le=500),
    work_status: str = Query("Waiting for IRS/Agency")
):
    """
    Get Karbon work items for E-file status processing.
    Always fetches DB status and merges so UI shows correct badges on first load.
    On Karbon failure, returns empty list (no 500).
    """
    from services.karbon_workitem_service import enrich_efile_items_with_status
    try:
        items = await get_karbon_work_items_for_efile_status(
            top=top,
            work_status_filter=work_status
        )
    except Exception as e:
        logger.warning("Error fetching e-file work items from Karbon. Returning empty list: %s", e)
        items = []
    return await enrich_efile_items_with_status(items)


@router.get("/fi/workitems")
async def fi_workitems(
    top: int = Query(100, ge=1, le=500),
    work_status: str = Query("Return Assembly")
):
    """
    Get Karbon work items for Filing Instructions processing.
    List load does not call Service B status APIs; status polling starts after processing trigger.
    """
    try:
        from services.karbon_fi_workitem_service import get_fi_workitems_enriched
        return await get_fi_workitems_enriched(
            top=top,
            work_status_filter=work_status,
        )
    except Exception as e:
        # Fail-soft: when Karbon is temporarily unavailable (DNS/network),
        # return empty list so UI can continue working.
        logger.warning("Error fetching FI work items from Karbon. Returning empty list: %s", e)
        return []


class EfileProcessRequest(BaseModel):
    work_item_keys: List[str]
    user_email: Optional[str] = None
    close_drake: bool = True
    send_email: bool = True

@router.post("/process-fi")
async def process_fi_endpoint(request: EfileProcessRequest, background_tasks: BackgroundTasks):
    """
    Process Filing Instructions for selected Karbon work items.
    1. Opens Drake
    2. Prints FI to PDF
    3. Uploads PDF to Karbon
    """
    selected_keys = set(request.work_item_keys)
    if not selected_keys:
        return {"message": "No items selected"}

    logger.info(f"Starting FI processing for {len(selected_keys)} items")

    # Prevent duplicate triggers if items are already queued/processing in Service B.
    blocked_keys = []
    for key in selected_keys:
        try:
            check = await check_can_trigger(str(key))
            if check.get("in_progress"):
                blocked_keys.append(str(key))
        except Exception:
            pass  # assume can trigger if Service B unreachable
    if blocked_keys:
        return {
            "message": "Some items are already queued or processing",
            "blocked_keys": list(blocked_keys),
            "status": "blocked",
            "processed_count": 0,
            "totals": {"updated": 0, "failed_drake": 0, "failed_karbon": 0, "skipped": 0},
            "details": [],
        }

    # Fetch items to get details (Client ID, Name)
    # We fetch a larger batch to ensure we find the selected ones
    all_items = await get_karbon_work_items_for_FI_status(top=500)
    targets = [i for i in all_items if i.get("workItemKey") in selected_keys]
    
    if len(targets) < len(selected_keys):
        logger.warning(f"Requested {len(selected_keys)} items but only found {len(targets)} in Karbon query.")
    
    # STEP 1 — Insert ALL selected records into DB first (status=IN_QUEUE)
    # (Service B owns the DB; we proxy enqueue to Service B)
    await enqueue_fi_workitems(
        [
            {
                "workitem_id": str(t.get("workItemKey")),
                "tax_id": t.get("registrationNumber"),
                "client_name": t.get("clientName"),
            }
            for t in targets
            if t.get("workItemKey")
        ]
    )

    # STEP 2 — Start automation and wait for the result.
    # The frontend is calling this endpoint sequentially for each item.
    try:
        result = await call_process_fi(targets, close_drake=request.close_drake)
    except Exception as e:
        logger.error(f"Error in FI automation (Service B): {e}", exc_info=True)
        return JSONResponse(status_code=500, content={"detail": f"Automation Error: {str(e)}"})

    return result


class FISummaryRequest(BaseModel):
    processed_count: int
    totals: Dict[str, int]
    details: List[Dict[str, Any]]
    user_email: Optional[str] = None

@router.post("/send-fi-summary")
async def send_fi_summary_endpoint(request: FISummaryRequest, background_tasks: BackgroundTasks):
    subject, html, text = build_fi_processing_summary_email(
        processed_count=request.processed_count,
        totals=request.totals,
        details=request.details
    )
    user_email = request.user_email or os.getenv("USER_EMAIL", "")
    if user_email:
        background_tasks.add_task(send_email, user_email, subject, html, text)
    return {"status": "sent"}

@router.get("/efile-status-work-items")
async def query_karbon_for_efile_status(
    top: int = Query(100, ge=1, le=500),
    skip: int = Query(0, ge=0),
    work_status: str = Query("Waiting for IRS/Agency"),
):
    """
    Fetch Karbon e-file work items for list view.
    Status polling starts only after explicit processing is triggered.
    """
    try:
        from services.karbon_workitem_service import get_efile_status_workitems_enriched
        return await get_efile_status_workitems_enriched(
            top=top, skip=skip, work_status_filter=work_status
        )
    except Exception as e:
        logger.warning("Error querying Karbon work items. Returning empty list: %s", e)
        return []


@router.post("/process-efile-status")
async def process_efile_status_endpoint(
    request: EfileProcessRequest,
    background_tasks: BackgroundTasks,
):
    # -----------------------------
    # Validate input
    # -----------------------------
    selected_keys: set[str] = {k for k in request.work_item_keys if k}
    if not selected_keys:
        return {"message": "No items selected", "updated": 0}

    # -----------------------------
    # Check automation status via Service B - prevent duplicate triggers
    # -----------------------------
    blocked_keys = []
    for key in selected_keys:
        try:
            check = await check_can_trigger(key)
            if check.get("in_progress"):
                blocked_keys.append(key)
        except Exception:
            pass  # assume can trigger if Service B unreachable
    if blocked_keys:
        return {
            "message": "Some items are already queued or processing",
            "blocked_keys": list(blocked_keys),
            "status": "blocked",
            "updated": 0,
        }

    # -----------------------------
    # Fetch latest Karbon items
    # -----------------------------
    try:
        all_items = await get_karbon_work_items_for_efile_status()
    except Exception as e:
        logger.error(f"Failed to fetch Karbon items: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch Karbon items")

    # -----------------------------
    # Filter selected + processable, exclude SUCCESS, enqueue in Service B
    # -----------------------------
    items_by_key = {
        x.get("workItemKey"): x
        for x in all_items
        if x.get("workItemKey")
    }

    targets = []
    for k in selected_keys:
        item = items_by_key.get(k)
        if not item or not item.get("processable"):
            continue
        try:
            check = await check_can_trigger(k)
            status = check.get("status")
            if status == "SUCCESS":
                continue
            if check.get("can_trigger"):
                targets.append(item)
        except Exception:
            targets.append(item)  # assume can trigger if check fails

    if not targets:
        return {
            "message": "No processable items found for the selected keys",
            "processed_count": 0,
            "updates_found": 0,
            "totals": {
                "processed": 0,
                "updated": 0,
                "failed": 0,
                "skipped": 0,
                "failed_drake": 0,
                "failed_karbon": 0,
            },
            "details": [],
        }

    # -----------------------------
    # Enqueue in Service B (mark IN_QUEUE), then run Drake automation
    # -----------------------------
    target_keys = [str(item.get("workItemKey")) for item in targets if item.get("workItemKey")]
    try:
        await enqueue_workitems(target_keys, triggered_by=None)
        # Update the first item to IN_PROCESSING immediately to provide feedback
        if target_keys:
            try:
                await update_workitem_status(target_keys[0], "IN_PROCESSING", "Starting...")
            except Exception as e:
                logger.warning(f"Failed to set initial processing status for {target_keys[0]}: {e}")
    except Exception as e:
        logger.warning(f"Failed to enqueue in Service B: {e}")

    # -----------------------------
    # Run Drake automation via Service B
    # -----------------------------
    try:
        result = await call_process_efile_status(targets)
        updates = result.get("updates", [])
        details = result.get("details", [])
    except Exception as e:
        logger.error(
            "Workitem processing failed",
            extra={"error": str(e)},
            exc_info=True,
        )
        err_msg = str(e)
        if hasattr(e, "response") and hasattr(e.response, "status_code"):
            err_msg = f"HTTP {e.response.status_code}: {err_msg}"
        for item in targets:
            key = item.get("workItemKey")
            if key:
                try:
                    await update_workitem_status(str(key), "FAIL", err_msg)
                except Exception:
                    pass
        raise HTTPException(status_code=500, detail="Failed to process Drake")

    # -----------------------------
    # Update Karbon
    # -----------------------------
    karbon_update_result = {
        "updated": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }

    if updates:
        try:
            karbon_update_result = await update_work_items_for_efile_status(updates)
        except Exception as e:
            logger.error(f"Failed to update Karbon: {e}", exc_info=True)
            karbon_update_result = {
                "updated": 0,
                "failed": len(updates),
                "skipped": 0,
                "details": [],
                "error": str(e),
            }

    # -----------------------------
    # Build summary (per-record aggregation)
    # -----------------------------
    totals = compute_efile_totals_from_details(details, karbon_update_result)
    processed = totals.get("processed", len(targets))

    if karbon_update_result.get("details"):
        karbon_fail_map = {
            str(d["workItemKey"]): d["reason"]
            for d in karbon_update_result["details"]
            if d.get("status") == "failed" and d.get("workItemKey")
        }
        for d in details:
            wk = str(d.get("workItemKey", ""))
            if wk in karbon_fail_map:
                d["result"] = "failed"
                existing_err = d.get("error")
                karbon_err = karbon_fail_map[wk]
                d["error"] = f"{existing_err} | {karbon_err}" if existing_err else karbon_err

    # -----------------------------
    # Email summary (optional)
    # -----------------------------
    subject, html, text = build_efile_status_summary_email(
        totals=totals,
        processed_count=processed,
        details=details,
    )

    user_email = request.user_email or os.getenv("USER_EMAIL", "")
    if user_email and request.send_email:
        logger.info(f"Sending summary email to {user_email}")
        background_tasks.add_task(
            send_email,
            user_email,
            subject,
            html,
            text,
        )

    # -----------------------------
    # Final response
    # -----------------------------
    return {
        "message": "Processing completed",
        "processed_count": processed,
        "updates_found": len(updates),
        "totals": totals,
        "details": details,  # Drake logs (frontend uses this)
        "karbon_update_result": karbon_update_result,
    }


class EfileSummaryRequest(BaseModel):
    totals: Dict[str, int]
    processed_count: int
    updates_found: int
    details: List[Dict[str, Any]]
    user_email: Optional[str] = None

@router.post("/send-efile-summary")
async def send_efile_summary_endpoint(request: EfileSummaryRequest, background_tasks: BackgroundTasks):
    """
    Endpoint to send a summary email after batch processing is complete on frontend.
    """
    subject, html, text = build_efile_status_summary_email(
        totals=request.totals,
        processed_count=request.processed_count,
        details=request.details,
    )
    
    user_email = request.user_email or os.getenv("USER_EMAIL", "")
    if user_email:
        logger.info(f"Sending batch summary email to {user_email}")
        background_tasks.add_task(send_email, user_email, subject, html, text)
    
    return {"status": "sent"}

class EfileOpenWithKeysRequest(BaseModel):
    work_item_keys: List[str]

@router.post("/efile-status/open")
async def open_efile_status_session_endpoint(request: Optional[EfileOpenWithKeysRequest] = None):
    """
    Proxy to Service B to open a persistent Drake e-file status session.
    If work_item_keys are provided, this also acts as a batch trigger,
    enqueuing all items and setting the first to IN_PROCESSING.
    """
    if request and request.work_item_keys:
        keys = request.work_item_keys
        if keys:
            initial_statuses = {keys[0]: "IN_PROCESSING"}
            try:
                # This will set the first item to IN_PROCESSING and others to IN_QUEUE.
                await enqueue_workitems(keys, initial_statuses=initial_statuses)
                logger.info(f"Enqueued e-file batch of {len(keys)} items. Set {keys[0]} to IN_PROCESSING.")
            except Exception as e:
                logger.warning(f"Failed to enqueue batch with initial status: {e}")

    try:
        return await call_efile_status_open_session()
    except Exception as e:
        logger.error(f"Failed to proxy efile-status open to Service B: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Service B call failed: {str(e)}")

class EfileStatusCheckRequest(BaseModel):
    client_id: str
    client_name: Optional[str] = None
    work_item_key: Optional[str] = None  # permaKey for automation tracking

@router.post("/efile-status/check-client")
async def check_efile_status_client(request: EfileStatusCheckRequest):
    """Check one client's e-file status via Service B Drake lookup."""
    client_id = (request.client_id or "").strip()
    client_name = (request.client_name or "").strip() or None
    work_item_key = (request.work_item_key or "").strip() or None

    logger.info(
        "Checking Drake status",
        extra={
            "client_id": client_id,
            "client_name": client_name,
            "work_item_key": work_item_key,
        },
    )

    try:
        if not client_id:
            raise ValueError("client_id is required")

        if work_item_key:
            try:
                check = await check_can_trigger(work_item_key)
                if check.get("in_progress"):
                    logger.info(
                        "Skipping Drake lookup because workitem is already active",
                        extra={"work_item_key": work_item_key, "status": check.get("status")},
                    )
                    return {
                        "status": "blocked",
                        "automation_status": check.get("status"),
                        "message": "Already queued or processing",
                    }
                if not check.get("can_trigger"):
                    logger.info(
                        "Skipping Drake lookup because workitem already completed",
                        extra={"work_item_key": work_item_key, "status": check.get("status")},
                    )
                    return {
                        "status": "skipped",
                        "automation_status": check.get("status"),
                        "message": "Already completed",
                    }
            except Exception as precheck_exc:
                # Do not fail user request if precheck is unavailable.
                logger.warning(
                    "Precheck failed; continuing with direct Drake lookup",
                    extra={"work_item_key": work_item_key, "error": str(precheck_exc)},
                )

        logger.info("Starting Drake lookup", extra={"client_id": client_id, "work_item_key": work_item_key})
        result = await call_efile_status_check_client(client_id, client_name, work_item_key)

        drake_status = result.get("drake_status") if isinstance(result, dict) else None
        logger.info(
            "Drake lookup completed",
            extra={"client_id": client_id, "work_item_key": work_item_key, "drake_status": drake_status},
        )

        # check-client endpoint only checks status; Karbon update is handled by a dedicated endpoint.
        logger.info(
            "Karbon update not attempted in check-client endpoint",
            extra={"work_item_key": work_item_key, "drake_status": drake_status},
        )

        return {
            "status": "ok",
            "drake_status": drake_status,
            "client_id": client_id,
            "work_item_key": work_item_key,
        }
    except ValueError as e:
        logger.warning("Invalid input for efile status check: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(
            "Unexpected error while checking Drake client status",
            extra={"client_id": client_id, "client_name": client_name, "work_item_key": work_item_key, "error": str(e)},
            exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Error checking Drake status for '{client_name or client_id}': {str(e)}")

@router.post("/efile-status/close")
async def close_efile_status_session_endpoint():
    """Proxy to Service B to close the persistent Drake e-file status session."""
    try:
        return await call_efile_status_close_session()
    except Exception as e:
        logger.error(f"Failed to proxy efile-status close to Service B: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Service B call failed: {str(e)}")

class KarbonUpdateStatusRequest(BaseModel):
    work_item_key: str
    efile_status: str

@router.post("/update-workitem-status")
async def update_workitem_status_endpoint(request: KarbonUpdateStatusRequest):
    updates = [{
        "workItemKey": request.work_item_key,
        "efileStatus": request.efile_status
    }]
    result = await update_work_items_for_efile_status(updates)
    return result

app.include_router(router)

# Job status tracking
job_status: Dict[str, Dict] = {}


class FormType(str, Enum):
    FORM_1065 = "1065"
    FORM_1120 = "1120"
    FORM_1120S = "1120s"
    FORM_1040 = "1040"
    FORM_1099DIV = "1099DIV"
    FORM_1099INT = "1099INT"
    FORM_1099MISC = "1099MISC"
    FORM_1099NEC = "1099NEC"
    FORM_1099R = "1099R"
    FORM_1099SSA = "1099SSA"
    FORM_W2 = "W2"
    FORM_W2G = "W2G"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def update_job_status(job_id: str, status: JobStatus, error: Optional[str] = None):
    """Update job status"""
    if job_id not in job_status:
        job_status[job_id] = {
            "job_id": job_id,
            "status": status.value,
            "created_at": datetime.now().isoformat(),
            "form_type": None,
        }
    job_status[job_id]["status"] = status.value
    job_status[job_id]["updated_at"] = datetime.now().isoformat()
    if error:
        job_status[job_id]["error"] = error


def process_document_async(job_id: str, form_type: FormType, pdf_path: str, output_dir: str, custom_page_groups: Optional[Dict] = None):
    """Process document in background"""
    import logging
    import time
    
    logger = logging.getLogger(__name__)
    start_time = time.time()
    
    try:
        update_job_status(job_id, JobStatus.PROCESSING)
        logger.info(f"📋 Job {job_id}: Starting processing (Form {form_type.value})")
        if custom_page_groups:
            logger.info(f"📋 Using custom page groups: {custom_page_groups}")
        
        # The "Tax Automation" flow (which calls this async function) does not use Drake-specific normalization.
        for_drake = False
        # Use unified pipeline with form type and optional custom page groups
        results = run_pipeline(form_type.value, pdf_path, output_dir, custom_page_groups, for_drake=for_drake)
        
        elapsed = time.time() - start_time
        logger.info(f"✅ Job {job_id}: Completed successfully in {elapsed:.2f}s")
        
        if job_id in job_status:
            job_status[job_id]["execution_stats"] = results.get("_execution_stats", {})
            
        update_job_status(job_id, JobStatus.COMPLETED)
        try:
            client_id = (job_status.get(job_id, {}) or {}).get("client_id")
            outputs_parent_folder = (job_status.get(job_id, {}) or {}).get("outputs_parent_folder")
            if client_id and outputs_parent_folder:
                asyncio.run(
                    upsert_ocr_result(
                        {
                            "tax_id": str(client_id),
                            "outputs_parent_folder": str(outputs_parent_folder),
                            "ocr_status": "EXTRACTED",
                        }
                    )
                )
        except Exception as persist_err:
            logger.warning("Failed to persist OCR success to Service B: %s", persist_err)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"❌ Job {job_id}: Failed after {elapsed:.2f}s - {str(e)}", exc_info=True)
        update_job_status(job_id, JobStatus.FAILED, str(e))
        try:
            client_id = (job_status.get(job_id, {}) or {}).get("client_id")
            outputs_parent_folder = (job_status.get(job_id, {}) or {}).get("outputs_parent_folder")
            if client_id and outputs_parent_folder:
                asyncio.run(
                    upsert_ocr_result(
                        {
                            "tax_id": str(client_id),
                            "outputs_parent_folder": str(outputs_parent_folder),
                            "ocr_status": "EXTRACTED_FAIL",
                            "error_message": str(e),
                        }
                    )
                )
        except Exception as persist_err:
            logger.warning("Failed to persist OCR failure to Service B: %s", persist_err)


@app.get("/", response_class=HTMLResponse)
async def read_root():
    """Serve the main web UI"""
    html_path = static_dir / "index.html"
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding='utf-8'))
    return HTMLResponse(content="<h1>Badger Automation API</h1><p>Web UI coming soon</p>")


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document and return page count"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")
    
    # Create temporary job directory
    job_id = f"temp_{os.path.splitext(file.filename)[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    job_dir = BASE_OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    pdf_path = job_dir / file.filename
    
    # Save uploaded file
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Get page count
    try:
        page_count = get_pdf_page_count(str(pdf_path))
    except Exception as e:
        logger.error(f"Error reading PDF: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error reading PDF: {str(e)}")
    
    # Initialize job status
    update_job_status(job_id, JobStatus.PENDING)
    job_status[job_id]["form_type"] = None
    job_status[job_id]["filename"] = file.filename
    job_status[job_id]["page_count"] = page_count
    job_status[job_id]["pdf_path"] = str(pdf_path)
    
    return {
        "job_id": job_id,
        "filename": file.filename,
        "page_count": page_count,
        "message": "Document uploaded successfully"
    }

def _infer_form_type_from_text(pages: list) -> Optional[str]:
    """
    Infer the form type based on text content of the first few pages.
    """
    if not pages:
        return None
    
    # Check first 2 pages
    text_content = []
    for p in pages[:2]:
        if isinstance(p, dict):
            text_content.append(p.get("text", ""))
        else:
            text_content.append(str(p))
            
    text = "\n".join(text_content).upper()
    
    # Check for specific form markers
    if "1120-S" in text or "1120S" in text:
        return "1120s"
    if "FORM 1120" in text and "1120-S" not in text:
        return "1120"
    if "FORM 1065" in text:
        return "1065"
    if "FORM 1040" in text:
        return "1040"
    if "1099-DIV" in text:
        return "1099DIV"
    if "1099-INT" in text:
        return "1099INT"
    if "1099-R" in text:
        return "1099R"
    if "SSA-1099" in text:
        return "1099SSA"
    if "W-2" in text:
        return "W2"
    if "W-2G" in text:
        return "W2G"
    if "1099-NEC" in text:
        return "1099NEC"
    if "1099-MISC" in text:
        return "1099MISC"
        
    return None

def _get_auto_detection_mapping():
    """
    Returns mapping for detecting multiple form types at once.
    Maps LLM keys to (Group Name, Form Type Value).
    """
    return {
        "w2_pages": ("Form W-2", "W2"),
        "1099_ssa_pages": ("Form 1099-SSA", "1099SSA"),
        "1099_div_pages": ("Form 1099-DIV", "1099DIV"),
        "1099_int_pages": ("Form 1099-INT", "1099INT"),
        "1099_r_pages": ("Form 1099-R", "1099R"),
        "1099_misc_pages": ("Form 1099-MISC", "1099MISC"),
        "1099_nec_pages": ("Form 1099-NEC", "1099NEC"),
        "form_1040_page": ("Form 1040", "1040")
    }

@app.post("/api/jobs/{job_id}/detect-pages")
async def detect_pages(job_id: str, form_type: Optional[str] = Form(None)):
    """
    Use AI to detect page numbers for the uploaded PDF based on form type.
    Returns detected page groups mapped to the form's configuration.
    """
    start_time = time.time()
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    pdf_path = job_status[job_id].get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    try:
        # Import AI_Page modules
        import sys
        ai_page_path = Path(__file__).parent / "AI_Page"
        if str(ai_page_path) not in sys.path:
            sys.path.insert(0, str(ai_page_path))
        # Read PDF bytes
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        ocr_start = time.time()
        # Extract text from pages using smart extraction (PyPDF + DI for weak pages)
        pages = extract_pages_text_smart(pdf_bytes)
        ocr_time = time.time() - ocr_start
        logger.info(f"[DETECT] Job {job_id}: Extracted {len(pages)} pages in {ocr_time:.2f}s")
        
        # Auto-detect form type if not provided
        if not form_type or form_type == "Auto":
            form_type = "Auto"
            logger.info(f"[DETECT] Job {job_id}: Auto-detection mode enabled. Will use LLM for multi-form detection.")
        
        logger.info(f"[DETECT] Job {job_id}: Starting AI page detection for form type {form_type}")
        
        llm_start = time.time()
        # Use LLM to detect page map
        page_map = find_page_map_with_llm(pages)
        llm_time = time.time() - llm_start
        logger.info(f"[DETECT] Job {job_id}: AI detected page_map = {page_map}")
        
        logger.info(f"[DETECT] Job {job_id}: Clients detected = {page_map.get('clients', [])}")
        
        # Map detected pages to form's page_groups
        # AI_Page returns 1-based page numbers, we need to convert to 0-based for config
        detected_groups = {}
        detected_form_types = set()

        if form_type == "Auto":
            # Multi-form detection mode
            auto_mapping = _get_auto_detection_mapping()
            for ai_key, (group_name, f_type) in auto_mapping.items():
                detected_value = page_map.get(ai_key)
                if detected_value:
                    if isinstance(detected_value, list):
                        pages_0_based = [p - 1 for p in detected_value if p is not None]
                        if pages_0_based:
                            detected_groups[group_name] = pages_0_based
                            detected_form_types.add(f_type)
                    elif isinstance(detected_value, int):
                        detected_groups[group_name] = [detected_value - 1]
                        detected_form_types.add(f_type)
            
            # If we found exactly one type, update the form_type for the job
            if len(detected_form_types) == 1:
                form_type = list(detected_form_types)[0]
                job_status[job_id]["form_type"] = form_type
            
        else:
            # Specific form type detection
            detection_mapping = get_page_detection_mapping(form_type)
            
            for ai_key, group_name in detection_mapping.items():
                detected_value = page_map.get(ai_key)
                
                if detected_value is not None:
                    # Handle both single page (int) and multiple pages (list)
                    if isinstance(detected_value, list):
                        # Convert 1-based to 0-based
                        pages_0_based = [p - 1 for p in detected_value if p is not None]
                        if pages_0_based:
                            detected_groups[group_name] = pages_0_based
                    elif isinstance(detected_value, int):
                        # Single page, convert 1-based to 0-based
                        detected_groups[group_name] = [detected_value - 1]
        
        # For form types with combined schedule groups (1065, 1120),
        # merge schedule_l, schedule_m1, schedule_m2 pages into one group
        form_type_lower = form_type.lower()
        if form_type_lower in ["1065", "1120"]:
            schedule_group = "Schedule_M_L" if form_type_lower == "1065" else "Schedule_M_L_1120"
            schedule_pages = set()
            
            for ai_key in ["schedule_l", "schedule_m1", "schedule_m2"]:
                detected_value = page_map.get(ai_key)
                if detected_value is not None:
                    if isinstance(detected_value, int):
                        schedule_pages.add(detected_value - 1)  # Convert to 0-based
                    elif isinstance(detected_value, list):
                        schedule_pages.update(p - 1 for p in detected_value if p is not None)
            
            if schedule_pages:
                detected_groups[schedule_group] = sorted(list(schedule_pages))
        
        # For 1120s, also merge schedule_m1 and schedule_m2 into pages_13
        if form_type_lower == "1120s":
            schedule_m_pages = set()
            for ai_key in ["schedule_m1", "schedule_m2"]:
                detected_value = page_map.get(ai_key)
                if detected_value is not None:
                    if isinstance(detected_value, int):
                        schedule_m_pages.add(detected_value - 1)
                    elif isinstance(detected_value, list):
                        schedule_m_pages.update(p - 1 for p in detected_value if p is not None)
            
            if schedule_m_pages:
                detected_groups["pages_13"] = sorted(list(schedule_m_pages))
        
        # Store detection results in job status for reference
        job_status[job_id]["detected_page_map"] = page_map
        job_status[job_id]["detected_groups"] = detected_groups
        
        logger.info(f"[DETECT] Job {job_id}: Mapped to groups = {detected_groups}")
        
        elapsed_time = time.time() - start_time
        logger.info("=" * 60)
        logger.info(f"⏱️  [DETECT] Job {job_id}: Detection completed in {elapsed_time:.2f}s")
        logger.info(f"   - OCR/Text Extraction: {ocr_time:.2f}s")
        logger.info(f"   - LLM Analysis: {llm_time:.2f}s")
        logger.info("=" * 60)

        return {
            "job_id": job_id,
            "form_type": form_type,
            "raw_page_map": page_map,
            "detected_groups": detected_groups,
            "execution_time": elapsed_time,
            "ocr_time": ocr_time,
            "llm_time": llm_time,
            "detected_types": list(detected_form_types) if 'detected_form_types' in locals() else [],
            "list_clients": page_map.get("clients", []),
            "message": "Page detection completed successfully"
        }
        
    except Exception as e:
        logger.error(f"[DETECT] Job {job_id}: AI detection failed - {str(e)}", exc_info=True)
        # Return empty detection on failure (frontend will use defaults)
        return {
            "job_id": job_id,
            "form_type": form_type,
            "raw_page_map": {},
            "detected_groups": {},
            "error": str(e),
            "message": "Page detection failed, using default pages"
        }


@app.post("/api/jobs/{job_id}/debug-split-pages")
async def debug_split_pages(job_id: str, selected_groups: str = Form(...), form_type: str = Form(...)):
    """
    Debug endpoint to split the uploaded PDF into individual page images
    and save them to the outputs folder. Supports multi-form type extraction.
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")

    job_info = job_status[job_id]
    pdf_path = job_info.get("pdf_path") 

    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        logger.info(f"Debug split pages requested for job {job_id}")
        job_dir = BASE_OUTPUT_DIR / job_id
        split_dir = job_dir / "split_pages"
        
            
        # Build a map from page number (0-based) to its corresponding form type
        page_to_form_type = {}
        try:
            groups = json.loads(selected_groups)
            for group_name, pages in groups.items():
                # Find form type for this group using the pre-built map
                group_form_type = _GROUP_NAME_TO_FORM_TYPE_MAP.get(group_name)

                if not group_form_type:
                    # Fallback to the overall form_type if group-specific one not found
                    group_form_type = form_type if form_type != "Auto" else None

                if not group_form_type:
                    logger.warning(f"Could not determine form type for group '{group_name}'. Skipping.")
                    continue

                for page in pages:
                    page_to_form_type[page] = group_form_type
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse selected_groups for multi-form mapping, will use single form_type.")
            # Fallback for single form_type if parsing fails
            if form_type != "Auto":
                unique_pages = set()
                for pages in json.loads(selected_groups).values():
                    unique_pages.update(pages)
                for page in unique_pages:
                    page_to_form_type[page] = form_type

        # Split pages
        split_results = debug_split_pages_to_output(str(pdf_path), str(split_dir), page_numbers=sorted(list(page_to_form_type.keys())))

        # Extract data for each page
        for item in split_results:
            try:
                page_number_0_based = item['page_number'] - 1
                current_form_type = page_to_form_type.get(page_number_0_based)

                if not current_form_type:
                    item["extracted_data"] = {"error": f"No form type mapped for page {item['page_number']}."}
                    continue

                single_page_pdf_path = item.get("pdf_path")
                config = get_form_config(current_form_type)
                page_output_root = split_dir / f"page_{item['page_number']}_output"
                custom_page_groups_for_pipeline = {group: [0] for group in config.page_groups.keys()}

                for_drake = True
                extracted_data = run_pipeline(
                    form_type=current_form_type,
                    input_pdf=single_page_pdf_path,
                    output_root=str(page_output_root),
                    custom_page_groups=custom_page_groups_for_pipeline,
                    for_drake=for_drake
                )
                item["extracted_data"] = extracted_data
            except Exception as e:
                logger.error(f"Failed to extract data for page {item['page_number']}: {e}", exc_info=True)
                item["extracted_data"] = {"error": str(e)}

        return {
            "message": f"Successfully split and extracted {len(split_results)} pages to {split_dir}",
            "results": split_results,
        }
    
    except Exception as e:
        logger.error(f"Error splitting pages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to split pages: {str(e)}")
    
@app.get("/api/jobs/{job_id}/split_pages/{image_filename}")
async def get_split_page_image(job_id: str, image_filename: str):
    """Serve a single split page image for debugging."""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")

    image_path = BASE_OUTPUT_DIR / job_id / "split_pages" / image_filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    return FileResponse(str(image_path))

# Build a comprehensive map from any group name to a form type code
_GROUP_NAME_TO_FORM_TYPE_MAP = {}
# 1. From specific form configs (e.g., 'pages_8_9' -> '1120s')
for ft_enum in FormType:
    try:
        config = get_form_config(ft_enum.value)
        for group_name in config.page_groups.keys():
            _GROUP_NAME_TO_FORM_TYPE_MAP[group_name] = ft_enum.value
    except (ValueError, FileNotFoundError):
        pass # Ignore form types without a config

# 2. From auto-detection mapping (e.g., 'Form W-2' -> 'W2')
_GROUP_NAME_TO_FORM_TYPE_MAP.update({
    v[0]: v[1] for v in _get_auto_detection_mapping().values()
})

@app.get("/api/forms/{form_type}/page-groups")
async def get_form_page_groups(form_type: str):
    """Get available page groups for a form type"""
    try:
        config = get_form_config(form_type)
        
        # Create friendly names for different form types
        friendly_names = {}
        if form_type.lower() == "1120s":
            friendly_names = {
                "pages_8_9": "Form 1120S",
                "pages_12": "Schedule L",
                "pages_13": "Schedule M",
            }
        elif form_type.lower() == "1120":
            friendly_names = {
                "Form_1120": "Form 1120",
                "Schedule_M_L_1120": "Schedule L, M-1, M-2"
            }
        elif form_type.lower() == "1065":
            friendly_names = {
                "Form_1065": "Form 1065",
                "Schedule_M_L": "Schedule L, M-1, M-2"
            }
        elif form_type.lower() == "1040":
            friendly_names = {
                "Form_1040": "Form 1040"
            }
        elif form_type.lower() == "1099div":
            friendly_names = {
                "Form_1099DIV": "Form 1099-DIV"
            }
        elif form_type.lower() == "1099int":
            friendly_names = {
                "Form_1099INT": "Form 1099-INT"
            }
        elif form_type.lower() == "1099misc":
            friendly_names = {
                "Form_1099MISC": "Form 1099-MISC"
            }
        elif form_type.lower() == "1099nec":
            friendly_names = {
                "Form_1099NEC": "Form 1099-NEC"
            }
        elif form_type.lower() == "1099r":
            friendly_names = {
                "Form_1099R": "Form 1099-R"
            }
        elif form_type.lower() == "1099ssa":
            friendly_names = {
                "Form_1099SSA": "Form 1099-SSA"
            }
        elif form_type.lower() == "w2":
            friendly_names = {
                "Form_W2": "Form W-2"
            }
        elif form_type.lower() == "w2g":
            friendly_names = {
                "Form_W2G": "Form W-2G"
            }
        
        page_groups = []
        for group_name, pages in config.page_groups.items():
            page_groups.append({
                "name": group_name,
                "display_name": friendly_names.get(group_name, group_name),
                "pages": pages,
                "page_range": f"{min(pages)}-{max(pages)}" if pages else ""
            })
        
        return {
            "form_type": form_type,
            "page_groups": page_groups
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
@app.post("/api/jobs/{job_id}/debug-split-pages")
async def debug_split_pages(job_id: str, selected_groups: str = Form(...), form_type: str = Form(...)):
    """
    Debug endpoint to split the uploaded PDF into individual page images
    and save them to the outputs folder. Supports multi-form type extraction.
    """
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")

    job_info = job_status[job_id]
    pdf_path = job_info.get("pdf_path") 

    if not pdf_path or not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="File not found")

    try:
        logger.info(f"Debug split pages requested for job {job_id}")
        job_dir = BASE_OUTPUT_DIR / job_id
        split_dir = job_dir / "split_pages"
        
            
        # Build a map from page number (0-based) to its corresponding form type
        page_to_form_type = {}
        try:
            groups = json.loads(selected_groups)
            for group_name, pages in groups.items():
                # Find form type for this group using the pre-built map
                group_form_type = _GROUP_NAME_TO_FORM_TYPE_MAP.get(group_name)

                if not group_form_type:
                    # Fallback to the overall form_type if group-specific one not found
                    group_form_type = form_type if form_type != "Auto" else None

                if not group_form_type:
                    logger.warning(f"Could not determine form type for group '{group_name}'. Skipping.")
                    continue

                for page in pages:
                    page_to_form_type[page] = group_form_type
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse selected_groups for multi-form mapping, will use single form_type.")
            # Fallback for single form_type if parsing fails
            if form_type != "Auto":
                unique_pages = set()
                for pages in json.loads(selected_groups).values():
                    unique_pages.update(pages)
                for page in unique_pages:
                    page_to_form_type[page] = form_type

        # Split pages
        split_results = debug_split_pages_to_output(str(pdf_path), str(split_dir), page_numbers=sorted(list(page_to_form_type.keys())))

        # Extract data for each page
        for item in split_results:
            try:
                page_number_0_based = item['page_number'] - 1
                current_form_type = page_to_form_type.get(page_number_0_based)

                if not current_form_type:
                    item["extracted_data"] = {"error": f"No form type mapped for page {item['page_number']}."}
                    continue

                single_page_pdf_path = item.get("pdf_path")
                config = get_form_config(current_form_type)
                page_output_root = split_dir / f"page_{item['page_number']}_output"
                custom_page_groups_for_pipeline = {group: [0] for group in config.page_groups.keys()}

                for_drake = True
                extracted_data = run_pipeline(
                    form_type=current_form_type,
                    input_pdf=single_page_pdf_path,
                    output_root=str(page_output_root),
                    custom_page_groups=custom_page_groups_for_pipeline,
                    for_drake=for_drake
                )
                item["extracted_data"] = extracted_data
            except Exception as e:
                logger.error(f"Failed to extract data for page {item['page_number']}: {e}", exc_info=True)
                item["extracted_data"] = {"error": str(e)}

        return {
            "message": f"Successfully split and extracted {len(split_results)} pages to {split_dir}",
            "results": split_results,
        }
    
    except Exception as e:
        logger.error(f"Error splitting pages: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to split pages: {str(e)}")

@app.post("/api/process/{form_type}")
async def process_document(
    form_type: FormType,
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    page_groups: Optional[str] = Form(None)  # JSON string of page groups
):
    """Process a tax document"""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Please upload a PDF file")
    
    # Parse custom page groups if provided
    custom_page_groups = None
    if page_groups:
        try:
            custom_page_groups = json.loads(page_groups)
            # Validate page groups format
            if not isinstance(custom_page_groups, dict):
                raise ValueError("page_groups must be a dictionary")
            for group_name, pages in custom_page_groups.items():
                if not isinstance(pages, list) or not all(isinstance(p, int) for p in pages):
                    raise ValueError(f"Page group '{group_name}' must be a list of integers")
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Invalid JSON format for page_groups")
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    
    # Create job directory
    job_id = f"{form_type.value}_{os.path.splitext(file.filename)[0]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    job_dir = BASE_OUTPUT_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    pdf_path = job_dir / file.filename
    output_dir = job_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Save uploaded file
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    
    # Initialize job status
    update_job_status(job_id, JobStatus.PENDING)
    job_status[job_id]["form_type"] = form_type.value
    job_status[job_id]["filename"] = file.filename
    if custom_page_groups:
        job_status[job_id]["custom_page_groups"] = custom_page_groups
    
    # Process in background
    background_tasks.add_task(process_document_async, job_id, form_type, str(pdf_path), str(output_dir), custom_page_groups)
    
    return {
        "status": "accepted",
        "job_id": job_id,
        "form_type": form_type.value,
        "filename": file.filename,
        "message": "Document processing started"
    }

@app.get("/api/jobs")
async def list_jobs():
    """List all jobs"""
    return {
        "jobs": list(job_status.values()),
        "total": len(job_status)
    }


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Get job status"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_info = job_status[job_id].copy()
    active_job_statuses = {JobStatus.PENDING.value, JobStatus.PROCESSING.value}
    has_active_jobs = any(
        (entry or {}).get("status") in active_job_statuses
        for entry in job_status.values()
    )
    # For this API, queue_empty means there is no pending/processing background OCR job.
    job_info["queue_empty"] = not has_active_jobs
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    
    if output_dir.exists():
        job_info["files"] = [f.name for f in output_dir.iterdir() if f.is_file()]
        job_info["has_results"] = len(job_info["files"]) > 0
    else:
        job_info["files"] = []
        job_info["has_results"] = False
    
    return job_info


@app.get("/api/jobs/{job_id}/files")
async def list_job_files(job_id: str):
    """List files for a job"""
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Job output not found")
    
    files = []
    for file_path in output_dir.iterdir():
        if file_path.is_file():
            files.append({
                "name": file_path.name,
                "size": file_path.stat().st_size,
                "type": file_path.suffix[1:] if file_path.suffix else "unknown"
            })
    
    return {"job_id": job_id, "files": files}


@app.get("/api/jobs/{job_id}/preview-group/{group_name}")
async def preview_page_group(job_id: str, group_name: str, pages: str = Query(...)):
    """Preview a page group by creating a PDF subset"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    pdf_path = job_status[job_id].get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    # Parse pages
    try:
        page_list = json.loads(pages)
        if not isinstance(page_list, list) or not all(isinstance(p, int) for p in page_list):
            raise ValueError("pages must be a JSON array of integers")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for pages")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Create temporary PDF subset
    from core.utils import split_pdf_by_page_groups
    import hashlib

    job_dir = BASE_OUTPUT_DIR / job_id
    
    # Use a hash of the pages to create a unique directory for this specific page configuration
    # This prevents file locking issues when multiple requests access the same preview
    pages_hash = hashlib.md5(pages.encode('utf-8')).hexdigest()
    preview_dir = job_dir / "previews" / f"{group_name}_{pages_hash}"
    preview_dir.mkdir(parents=True, exist_ok=True)
    
    page_groups = {group_name: page_list}
    
    # Check if file already exists to avoid regeneration and locking issues
    pdf_stem = Path(pdf_path).stem
    expected_filename = f"{pdf_stem}_{group_name}.pdf"
    expected_path = preview_dir / expected_filename
    
    if expected_path.exists():
        subset_paths = {group_name: str(expected_path)}
    else:
        try:
            subset_paths = split_pdf_by_page_groups(str(pdf_path), page_groups, str(preview_dir))
        except Exception as e:
            # If failed (e.g. race condition/locking), check if file exists now
            if expected_path.exists():
                subset_paths = {group_name: str(expected_path)}
            else:
                raise HTTPException(status_code=500, detail=f"Failed to create preview: {str(e)}")
    
    if group_name not in subset_paths:
        raise HTTPException(status_code=500, detail="Failed to create preview")
    
    preview_path = subset_paths[group_name]
    return FileResponse(
        path=preview_path,
        media_type="application/pdf",
        filename=f"preview_{group_name}.pdf",
        content_disposition_type="inline"
    )


@app.post("/api/jobs/{job_id}/process-groups")
async def process_with_selected_groups(
    job_id: str,
    form_type: FormType = Form(...),
    selected_groups: str = Form(...),  # JSON object mapping group names to page arrays
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    """Process document with selected page groups"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    pdf_path = job_status[job_id].get("pdf_path")
    if not pdf_path or not Path(pdf_path).exists():
        raise HTTPException(status_code=404, detail="PDF file not found")
    
    # Parse selected groups
    try:
        page_groups = json.loads(selected_groups)
        if not isinstance(page_groups, dict):
            raise ValueError("selected_groups must be a dictionary")
        for group_name, pages in page_groups.items():
            if not isinstance(pages, list) or not all(isinstance(p, int) for p in pages):
                raise ValueError(f"Page group '{group_name}' must be a list of integers")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format for selected_groups")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not page_groups:
        raise HTTPException(status_code=400, detail="At least one page group must be selected")
    
    # Update job status
    job_status[job_id]["form_type"] = form_type.value
    job_status[job_id]["selected_groups"] = page_groups
    
    # Set status to PROCESSING immediately to avoid race conditions in frontend polling
    update_job_status(job_id, JobStatus.PROCESSING)
    
    # Create output directory
    job_dir = BASE_OUTPUT_DIR / job_id
    output_dir = job_dir / "output"
    output_dir.mkdir(exist_ok=True)
    
    # Process in background
    background_tasks.add_task(process_document_async, job_id, form_type, pdf_path, str(output_dir), page_groups)
    
    return {
        "status": "accepted",
        "job_id": job_id,
        "form_type": form_type.value,
        "selected_groups": page_groups,
        "message": "Document processing started"
    }

@app.get("/api/jobs/{job_id}/download/{filename}")
async def download_file(job_id: str, filename: str):
    """Download a result file"""
    file_path = BASE_OUTPUT_DIR / job_id / "output" / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream"
    )


@app.get("/api/jobs/{job_id}/results")
async def get_job_results(job_id: str, raw: bool = False):
    """Get merged JSON results. If raw=True, returns all JSON files."""
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Job output not found")
    
    # If raw is requested, return all JSON files as a dictionary
    if raw:
        json_files = []
        for file_path in output_dir.glob("*.json"):
            with open(file_path, "r", encoding="utf-8") as f:
                json_files.append({
                    "filename": file_path.name,
                    "data": json.load(f)
                })
        return json_files
    
    # Default behavior: try to return the merged file
    form_type = job_status.get(job_id, {}).get("form_type", "")
    merged_files = {
        "1065": "1065_merged.json",
        "1120": "1120_merged.json",
        "1120s": "1120S_merged.json",
        "1040": "1040_merged.json",
        "1099DIV": "1099DIV_merged.json",
        "1099INT": "1099INT_merged.json",
        "1099MISC": "1099MISC_merged.json",
        "1099NEC": "1099NEC_merged.json",
        "1099R": "1099R_merged.json",
        "1099SSA": "1099SSA_merged.json",
        "W2": "W2_merged.json",
        "W2G": "W2G_merged.json"
    }
    
    merged_filename = merged_files.get(form_type)
    if merged_filename:
        merged_path = output_dir / merged_filename
        if merged_path.exists():
            with open(merged_path, "r", encoding="utf-8") as f:
                return json.load(f)
    
    # Fallback if no merged file: return all JSON files
    json_files = {}
    for file_path in output_dir.glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            json_files[file_path.name] = json.load(f)
    
    return json_files


@app.get("/api/jobs/{job_id}/results/with-bounding-boxes")
async def get_job_results_with_boxes(job_id: str):
    """Get results with bounding boxes for visualization"""
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Job output not found")
    
    # Get results
    form_type = job_status.get(job_id, {}).get("form_type", "")
    merged_files = {
        "1065": "1065_merged.json",
        "1120": "1120_merged.json",
        "1120s": "1120S_merged.json",
        "1040": "1040_merged.json",
        "1099DIV": "1099DIV_merged.json",
        "1099INT": "1099INT_merged.json",
        "1099MISC": "1099MISC_merged.json",
        "1099NEC": "1099NEC_merged.json",
        "1099R": "1099R_merged.json",
        "1099SSA": "1099SSA_merged.json",
        "W2": "W2_merged.json",
        "W2G": "W2G_merged.json"
    }
    
    merged_filename = merged_files.get(form_type)
    results = {}
    
    if merged_filename:
        merged_path = output_dir / merged_filename
        if merged_path.exists():
            with open(merged_path, "r", encoding="utf-8") as f:
                results = json.load(f)
    
    # Get selected groups for preview paths
    selected_groups = job_status.get(job_id, {}).get("selected_groups", {})
    pdf_path = job_status.get(job_id, {}).get("pdf_path")
    
    # Generate preview paths for selected groups
    group_previews = {}
    if pdf_path and selected_groups:
        for group_name in selected_groups.keys():
            group_previews[group_name] = f"/api/jobs/{job_id}/preview-group/{group_name}?pages={json.dumps(selected_groups[group_name])}"
    
    return {
        "results": results,
        "group_previews": group_previews,
        "selected_groups": selected_groups
    }


class OcrNotificationRequest(BaseModel):
    client_id: str
    client_name: str
    form_type: str

@app.post("/api/jobs/{job_id}/notify-ocr-completion")
async def notify_ocr_completion(
    job_id: str,
    request: OcrNotificationRequest,
    background_tasks: BackgroundTasks,
):
    """
    Endpoint to trigger an email notification when OCR processing is complete.
    """
    # Get recipient email from environment variables (e.g., USER_EMAIL)
    # You should configure this in your .env file
    recipient = os.getenv("USER_EMAIL")
    if not recipient:
        logger.warning("Recipient email not configured on server (USER_EMAIL env var is missing). Cannot send notification.")
        # Don't fail the client request, just log and return success
        return {"message": "Processing complete, but email notification was not sent due to server configuration."}

    subject, html_body, text_body = build_ocr_completion_email(
        client_id=request.client_id,
        client_name=request.client_name,
        form_type=request.form_type,
        job_id=job_id,
    )
    
    # Send email in the background to avoid blocking the API response
    background_tasks.add_task(
        send_email,
        to_email=recipient,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )
    
    return {"message": "Email notification queued."}


@app.post("/api/jobs/{job_id}/save-edited-data")
async def save_edited_data(job_id: str, request: Request):
    """Save edited field values back to the results JSON"""
    try:
        request_data = await request.json()
        output_dir = BASE_OUTPUT_DIR / job_id / "output"
        if not output_dir.exists():
            raise HTTPException(status_code=404, detail="Job output not found")
        
        # Get form type to determine which merged file to use
        form_type = job_status.get(job_id, {}).get("form_type", "")
        merged_files = {
            "1065": "1065_merged.json",
            "1120": "1120_merged.json",
            "1120s": "1120S_merged.json",
            "1040": "1040_merged.json",
            "1099DIV": "1099DIV_merged.json",
            "1099INT": "1099INT_merged.json",
            "1099MISC": "1099MISC_merged.json",
            "1099NEC": "1099NEC_merged.json",
            "W2": "W2_merged.json",
            "W2G": "W2G_merged.json",
        }
        
        merged_filename = merged_files.get(form_type)
        if not merged_filename:
            raise HTTPException(status_code=404, detail="No results found for this form type")
        
        results_file = output_dir / merged_filename
        if not results_file.exists():
            raise HTTPException(status_code=404, detail="Results file not found")
        
        # Load existing results
        with open(results_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        # Update results with edited values
        edited_fields = request_data.get('edited_fields', {})
        if form_type in {"W2", "W2G"}:
            for fields in edited_fields.values():
                for field_data in fields.values():
                    if isinstance(field_data, dict) and _is_w2_numeric_label(field_data.get("label", "")):
                        field_data["value"] = _format_two_decimal(field_data.get("value"))
        for group_name, fields in edited_fields.items():
            if group_name in results:
                group_data = results[group_name]
                
                # Handle both direct fields and nested models
                if 'fields' in group_data:
                    for field_key, field_data in fields.items():
                        if field_key in group_data['fields']:
                            # Update the value in the mapped structure
                            if isinstance(group_data['fields'][field_key], dict):
                                group_data['fields'][field_key]['value'] = field_data['value']
                            else:
                                # If not mapped structure, update directly
                                group_data['fields'][field_key] = field_data['value']
                elif 'models' in group_data:
                    # Update models
                    for model_id, model_data in group_data['models'].items():
                        if 'fields' in model_data:
                            for field_key, field_data in fields.items():
                                if field_key in model_data['fields']:
                                    if isinstance(model_data['fields'][field_key], dict):
                                        model_data['fields'][field_key]['value'] = field_data['value']
                                    else:
                                        model_data['fields'][field_key] = field_data['value']
        
        # Save updated results
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"✅ Saved edited data for job {job_id}")
        return JSONResponse({"status": "success", "message": "Edited data saved successfully"})
    
    except Exception as e:
        logger.error(f"❌ Error saving edited data: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))



@app.get("/api/jobs/{job_id}/excel")
async def generate_excel_file(job_id: str):
    """Generate unified Excel file from results"""
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Job output not found")
    
    # Get form type to determine which merged file to use
    form_type = job_status.get(job_id, {}).get("form_type", "")
    merged_files = {
        "1065": "1065_merged.json",
        "1120": "1120_merged.json",
        "1120s": "1120S_merged.json",
        "1040": "1040_merged.json",
        "1099DIV": "1099DIV_merged.json",
        "1099INT": "1099INT_merged.json",
        "1099MISC": "1099MISC_merged.json",
        "1099NEC": "1099NEC_merged.json",
        "1099R": "1099R_merged.json",
        "1099SSA": "1099SSA_merged.json",
        "W2": "W2_merged.json",
        "W2G": "W2G_merged.json"
    }
    
    merged_filename = merged_files.get(form_type)
    if not merged_filename:
        raise HTTPException(status_code=404, detail="No results found for this form type")
    
    merged_path = output_dir / merged_filename
    if not merged_path.exists():
        raise HTTPException(status_code=404, detail="Results file not found")
    
    # Load results
    with open(merged_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    # Generate Excel file
    excel_path = output_dir / "results.xlsx"
    try:
        generate_unified_excel(results, str(excel_path))
    except Exception as e:
        logger.error(f"Error generating Excel file: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel file: {str(e)}")
    
    # Return Excel file as download
    if not excel_path.exists():
        raise HTTPException(status_code=500, detail="Excel file was not created")
    
    return FileResponse(
        path=str(excel_path),
        filename="results.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


@app.get("/api/jobs/{job_id}/excel/view")
async def view_excel_file(job_id: str):
    """Serve Excel file for iframe embedding"""
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    excel_path = output_dir / "results.xlsx"
    
    if not excel_path.exists():
        # Try to generate it first
        try:
            form_type = job_status.get(job_id, {}).get("form_type", "")
            merged_files = {
                "1065": "1065_merged.json",
                "1120": "1120_merged.json",
                "1120s": "1120S_merged.json",
                "1040": "1040_merged.json",
                "1099DIV": "1099DIV_merged.json"
            }
            
            merged_filename = merged_files.get(form_type)
            if merged_filename:
                merged_path = output_dir / merged_filename
                if merged_path.exists():
                    with open(merged_path, "r", encoding="utf-8") as f:
                        results = json.load(f)
                    generate_unified_excel(results, str(excel_path))
        except Exception as e:
            logger.error(f"Error generating Excel file for view: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Failed to generate Excel file: {str(e)}")
    
    if not excel_path.exists():
        raise HTTPException(status_code=404, detail="Excel file not found")
    
    # Return Excel file with appropriate headers for iframe embedding
    return FileResponse(
        path=str(excel_path),
        filename="results.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "inline; filename=results.xlsx",
            "X-Content-Type-Options": "nosniff"
        }
    )


@app.get("/api/jobs/{job_id}/export/excel")
async def export_to_excel(job_id: str, edited_fields: Optional[str] = Query(None)):
    """Export results to Excel format with multiple worksheets"""
    import tempfile
    
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Job output not found")
    
    # Get results
    form_type = job_status.get(job_id, {}).get("form_type", "")
    merged_files = {
        "1065": "1065_merged.json",
        "1120": "1120_merged.json",
        "1120s": "1120S_merged.json",
        "1040": "1040_merged.json",
        "1099DIV": "1099DIV_merged.json",
        "1099INT": "1099INT_merged.json",
        "1099MISC": "1099MISC_merged.json",
        "1099NEC": "1099NEC_merged.json",
        "1099R": "1099R_merged.json",
        "1099SSA": "1099SSA_merged.json",
        "W2": "W2_merged.json",
        "W2G": "W2G_merged.json"
    }
    
    merged_filename = merged_files.get(form_type)
    if not merged_filename:
        raise HTTPException(status_code=404, detail="No results found for this form type")
    
    merged_path = output_dir / merged_filename
    if not merged_path.exists():
        raise HTTPException(status_code=404, detail="Results file not found")
    
    with open(merged_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    # Parse edited fields if provided
    edited_fields_dict = {}
    if edited_fields:
        try:
            edited_fields_dict = json.loads(edited_fields)
        except:
            pass
    
    # Generate Excel file in temporary location
    with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
        excel_path = tmp_file.name
    
    try:
        # Generate Excel with edited fields applied
        generate_unified_excel(results, excel_path, edited_fields_dict)
        
        # Return Excel file
        return FileResponse(
            path=excel_path,
            filename=f"results_{job_id}.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="results_{job_id}.xlsx"'}
        )
    except Exception as e:
        # Clean up temp file on error
        import os
        if os.path.exists(excel_path):
            os.unlink(excel_path)
        raise HTTPException(status_code=500, detail=f"Failed to generate Excel file: {str(e)}")


@app.get("/api/jobs/{job_id}/export/json")
async def export_to_json(job_id: str):
    """Export results to JSON format with only form groups and fields (line, label, value)"""
    output_dir = BASE_OUTPUT_DIR / job_id / "output"
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Job output not found")
    
    # Get results
    form_type = job_status.get(job_id, {}).get("form_type", "")
    merged_files = {
        "1065": "1065_merged.json",
        "1120": "1120_merged.json",
        "1120s": "1120S_merged.json",
        "1040": "1040_merged.json",
        "1099DIV": "1099DIV_merged.json",
        "1099INT": "1099INT_merged.json",
        "1099MISC": "1099MISC_merged.json",
        "1099NEC": "1099NEC_merged.json",
        "1099R": "1099R_merged.json",
        "1099SSA": "1099SSA_merged.json",
        "W2": "W2_merged.json",
        "W2G": "W2G_merged.json"
    }
    
    merged_filename = merged_files.get(form_type)
    if not merged_filename:
        raise HTTPException(status_code=404, detail="No results found for this form type")
    
    merged_path = output_dir / merged_filename
    if not merged_path.exists():
        raise HTTPException(status_code=404, detail="Results file not found")
    
    # Load results
    with open(merged_path, "r", encoding="utf-8") as f:
        results = json.load(f)
    
    # Format results: extract only form groups and fields with line/label/value structure
    formatted_results = {}
    
    for group_name, group_data in results.items():
        # Skip metadata keys (starting with _)
        if group_name.startswith("_"):
            continue
        
        if not isinstance(group_data, dict):
            continue
        
        # Collect all fields from this group
        fields_list = []
        
        # Check if this group has models (nested structure)
        if isinstance(group_data.get("models"), dict) and group_data["models"]:
            # Extract fields from each model
            for model_id, model_data in group_data["models"].items():
                if not isinstance(model_data, dict):
                    continue
                
                fields = model_data.get("fields", {})
                if not isinstance(fields, dict):
                    continue
                
                # Extract fields that have line/label/value structure
                for field_key, field_value in fields.items():
                    # Skip metadata keys and model IDs
                    if field_key.startswith("_") or field_key == model_id:
                        continue
                    
                    # Check if field has line/label/value structure
                    if isinstance(field_value, dict) and "line" in field_value and "label" in field_value:
                        fields_list.append({
                            "line": field_value.get("line", ""),
                            "label": field_value.get("label", ""),
                            "value": field_value.get("value", "")
                        })
                
                # For W2 forms, also include box12 and state_local_taxes
                box12_data = model_data.get("box12")
                if box12_data and isinstance(box12_data, dict):
                    # Add box12 entries to fields_list
                    for box12_key, box12_value in box12_data.items():
                        if isinstance(box12_value, dict) and "line" in box12_value and "label" in box12_value:
                            fields_list.append({
                                "line": box12_value.get("line", ""),
                                "label": box12_value.get("label", ""),
                                "value": box12_value.get("value", "")
                            })
                
                state_local_data = model_data.get("state_local_taxes")
                if state_local_data and isinstance(state_local_data, dict):
                    # Add state_local_taxes as a special entry
                    formatted_results[f"{group_name}_state_local_taxes"] = state_local_data
                
                # Include 1099-DIV state taxes withheld if present
                if model_id == "prebuilt-tax.us.1099DIV":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        formatted_results[f"{group_name}_state_taxes_withheld"] = state_taxes_data
                
                # Include 1099-INT state taxes withheld if present
                if model_id == "prebuilt-tax.us.1099INT":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        formatted_results[f"{group_name}_state_taxes_withheld"] = state_taxes_data
                
                # Include 1099-MISC state taxes withheld if present
                if model_id == "prebuilt-tax.us.1099MISC":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        formatted_results[f"{group_name}_state_taxes_withheld"] = state_taxes_data
                # Include 1099-NEC state taxes withheld if present
                if model_id == "prebuilt-tax.us.1099NEC":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        formatted_results[f"{group_name}_state_taxes_withheld"] = state_taxes_data
                
                # Include 1099-R state and local taxes withheld if present
                if model_id == "prebuilt-tax.us.1099R":
                    state_taxes_data = model_data.get("state_taxes_withheld")
                    if state_taxes_data and isinstance(state_taxes_data, dict):
                        formatted_results[f"{group_name}_state_taxes_withheld"] = state_taxes_data
                    local_taxes_data = model_data.get("local_taxes_withheld")
                    if local_taxes_data and isinstance(local_taxes_data, dict):
                        formatted_results[f"{group_name}_local_taxes_withheld"] = local_taxes_data
                
        elif group_data.get("fields"):
            # Direct fields structure
            fields = group_data.get("fields", {})
            if isinstance(fields, dict):
                # Extract fields that have line/label/value structure
                for field_key, field_value in fields.items():
                    # Skip metadata keys
                    if field_key.startswith("_"):
                        continue
                    
                    # Check if field has line/label/value structure
                    if isinstance(field_value, dict) and "line" in field_value and "label" in field_value:
                        fields_list.append({
                            "line": field_value.get("line", ""),
                            "label": field_value.get("label", ""),
                            "value": field_value.get("value", "")
                        })
            
            # For W2 forms with direct fields structure, also include box12 and state_local_taxes
            box12_data = group_data.get("box12")
            if box12_data and isinstance(box12_data, dict):
                # Add box12 entries to fields_list
                for box12_key, box12_value in box12_data.items():
                    if isinstance(box12_value, dict) and "line" in box12_value and "label" in box12_value:
                        fields_list.append({
                            "line": box12_value.get("line", ""),
                            "label": box12_value.get("label", ""),
                            "value": box12_value.get("value", "")
                        })
            
            state_local_data = group_data.get("state_local_taxes")
            if state_local_data and isinstance(state_local_data, dict):
                # Add state_local_taxes as a special entry
                formatted_results[f"{group_name}_state_local_taxes"] = state_local_data
            
            # Include 1099-DIV state taxes withheld if present (direct structure)
            state_taxes_data = group_data.get("state_taxes_withheld")
            if state_taxes_data and isinstance(state_taxes_data, dict):
                formatted_results[f"{group_name}_state_taxes_withheld"] = state_taxes_data
            
            # Include 1099-R local taxes withheld if present (direct structure)
            if group_name == "Form_1099R":
                local_taxes_data = group_data.get("local_taxes_withheld")
                if local_taxes_data and isinstance(local_taxes_data, dict):
                    formatted_results[f"{group_name}_local_taxes_withheld"] = local_taxes_data
        
        # Only add group if it has fields
        if fields_list:
            formatted_results[group_name] = fields_list
    
    # Create temporary JSON file with formatted results
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json', encoding='utf-8') as tmp_file:
        json.dump(formatted_results, tmp_file, ensure_ascii=False, indent=2)
        tmp_path = tmp_file.name
    
    # Return formatted JSON file
    return FileResponse(
        path=tmp_path,
        filename=f"results_{job_id}.json",
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="results_{job_id}.json"'}
    )

class DrakeLaunchRequest(BaseModel):
    job_id: Optional[str] = None
    client_id: Optional[str] = None
    data: Optional[Any] = None


@app.post("/api/drake/launch-async")
async def launch_drake_software_async(request: Optional[DrakeLaunchRequest] = None):
    """
    Start Drake automation asynchronously and return task_id immediately.
    Frontend should poll /api/drake/tasks/{task_id} until completion.
    """
    if not request:
        raise HTTPException(status_code=400, detail="Invalid request received.")
    if not request.data:
        raise HTTPException(status_code=400, detail="No data provided for automation.")
    if not request.job_id:
        raise HTTPException(status_code=400, detail="Job ID is missing.")
    if not request.client_id:
        raise HTTPException(status_code=400, detail="Client ID is missing.")
    try:
        return await start_drake_launch(request.model_dump())
    except Exception as e:
        logger.error(f"Failed to enqueue Drake launch task: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to enqueue Drake task: {str(e)}")


@app.get("/api/drake/tasks/{task_id}")
async def get_drake_task_status(task_id: str):
    """
    Proxy task status polling from Service B.
    """
    try:
        return await get_task_status(task_id)
    except Exception as e:
        logger.warning(f"Failed to poll Drake task {task_id}: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to poll task status: {str(e)}")


@app.post("/api/drake/launch")
async def launch_drake_software(
    background_tasks: BackgroundTasks,
    request: Optional[DrakeLaunchRequest] = None
):
    """
    Receives a request to launch the Drake software and enter form data.
    Validates all inputs and ensures the automation completes successfully before returning.
    """
    try:
        # ========== INPUT VALIDATION ==========
        if not request:
            raise HTTPException(status_code=400, detail="Invalid request received. Please try again.")
        
        if not request.data:
            raise HTTPException(status_code=400, detail="No data provided for automation. Please ensure data was extracted correctly.")
        
        # Extract and validate job_id
        job_id = request.job_id
        if not job_id:
            raise HTTPException(status_code=400, detail="Job ID is missing. Please restart the process.")
        
        # Extract and validate client_id
        if not request.client_id:
            raise HTTPException(status_code=400, detail="Client ID is missing. Please select a client.")
        
        try:
            client_id = normalize_id(request.client_id)
        except Exception as e:
            raise HTTPException(status_code=400, detail="The Client ID format is invalid. Please check the ID.")
        
        if not client_id:
            raise HTTPException(status_code=400, detail="The Client ID could not be processed. Please check the ID.")
        
        # Extract and validate data
        raw_data = request.data
        if not isinstance(raw_data, (list, dict)):
            raise HTTPException(status_code=400, detail="Data must be a list or object.")
        
        data_items = raw_data if isinstance(raw_data, list) else [raw_data]
        
        if not data_items or len(data_items) == 0:
            raise HTTPException(status_code=400, detail="No records found to import.")
        
        # Extract form_type from data
        form_type = []
        try:
            form_type = list({
                item.get("fields", {}).get("FormType", {}).get("value")
                for item in data_items
                if isinstance(item, dict) and item.get("fields", {}).get("FormType", {}).get("value")
            })
        except (IndexError, AttributeError, TypeError) as e:
            logger.warning(f"Could not extract form_type from data: {str(e)}")
        
        if not form_type:
            raise HTTPException(status_code=400, detail="Could not determine the tax form type (e.g., W-2, 1099). Please check the extraction results.")
        
        # Validate client exists in Drake database
        # client_tax_return_data = await get_latest_drake_clients()
        
        # if client_tax_return_data:
        #     client_found = False
        #     for client in client_tax_return_data:
        #         if client.get("Taxpayer ID") == client_id:
        #             logger.info(f"The client ID exists in the data with ID: {client.get('Taxpayer ID')}, Name: {client.get('Taxpayer Name')}")
        #             client_found = True
                    
        #             return_type = str(client.get("Return Type", "")).strip()
        #             if return_type != "1040":
        #                 client_name = client.get("Taxpayer Name", "Unknown")
        #                 recipient = os.getenv("USER_EMAIL")
        #                 if recipient:
        #                     from services.email_service import mask_id_last4
        #                     subject = f"[Badger] Drake Automation Error: Incorrect Return Type"
        #                     html_body = f"""
        #                     <div style="font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e0e0e0; border-radius: 5px;">
        #                         <h2 style="color: #d9534f;">Drake Automation Error</h2>
        #                         <p>The client <strong>{client_name}</strong> (ID: {mask_id_last4(client_id)}) has Return Type <strong>{return_type}</strong>.</p>
        #                         <p>Expected Return Type: <strong>1040</strong>.</p>
        #                         <p>The automation process has been stopped.</p>
        #                     </div>
        #                     """
        #                     text_body = f"Drake Automation Error: Client {client_name} ({mask_id_last4(client_id)}) has Return Type {return_type}. Expected 1040."
        #                     background_tasks.add_task(send_email, recipient, subject, html_body, text_body)
                        
        #                 raise HTTPException(status_code=400, detail=f"Client Return Type is '{return_type}', expected '1040'.")
        #             break
        #     if not client_found:
        #         # Attempt to extract client name from data for the email
        #         client_name_display = "Unknown"
        #         try:
        #             if data_items and len(data_items) > 0:
        #                 first_item = data_items[0]
        #                 # Unwrap if needed (handle both direct fields and nested under 'fields')
        #                 fields = first_item.get("fields") or first_item
                        
        #                 # Try common name fields
        #                 potential_names = []
                        
        #                 # Helper to safely get value from structure { value: "...", ... } or raw string
        #                 def get_val(obj, key):
        #                     if not isinstance(obj, dict): return None
        #                     val = obj.get(key)
        #                     if isinstance(val, dict) and "value" in val:
        #                         return val.get("value")
        #                     return val

        #                 # Check different form structures
        #                 potential_names.append(get_val(fields.get("Recipient"), "Name")) # 1099s
        #                 potential_names.append(get_val(fields.get("Employee"), "Name")) # W2
        #                 potential_names.append(get_val(fields.get("TaxpayerName"), "value")) # 1040/Business
        #                 potential_names.append(fields.get("TaxpayerName")) # Flat string
                        
        #                 for name in potential_names:
        #                     if name and isinstance(name, str) and name.strip():
        #                         client_name_display = name.strip()
        #                         break
        #         except Exception as e:
        #             logger.warning(f"Could not extract client name for error email: {e}")

        #         recipient = os.getenv("USER_EMAIL")
        #         if recipient:
        #             subject, html, text = build_client_not_found_email(client_id, client_name_display)
        #             background_tasks.add_task(send_email, recipient, subject, html, text)
                    
        #         from services.email_service import mask_id_last4
        #         raise HTTPException(status_code=400, detail=f"Client ID {mask_id_last4(client_id)} was not found in the Drake client list. Please ensure the client exists in Drake.")
        # else:
        #     logger.warning("Could not retrieve latest client list to validate Client ID.")
        #     raise HTTPException(status_code=400, detail='Could not retrieve the client list to validate the Client ID.\nPlease go to "Extract Drake Client List" to query Drake.')
        
        logger.info(f"✓ Validated inputs - Job: {job_id}, Client: {client_id}, Form: {[form for form in form_type]}, Items: {len(data_items)}")
        
        # ========== LOG REQUEST DATA ==========
        logger.info("=" * 25 + " BEGIN DRAKE LAUNCH DATA " + "=" * 25)
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Client ID: {client_id}")
        logger.info(f"Form Type: {form_type}")
        logger.info(f"Data Items Count: {len(data_items)}")
        logger.info(f"Data for Drake automation:\n{json.dumps(raw_data, indent=2)}")
        logger.info("=" * 26 + " END DRAKE LAUNCH DATA " + "=" * 27)
        
        # ========== EXECUTE AUTOMATION (via Service B) ==========
        logger.info(f"🚀 Starting Drake fill-in flow via Service B...")
        try:
            result = await call_drake_launch(request.model_dump())
            if isinstance(result, dict) and result.get("status") == "failed":
                raise HTTPException(status_code=400, detail=result.get("message"))
            return result
        except HTTPException:
            raise
        except ValueError as ve:
            logger.error(f"Drake automation validation failed: {str(ve)}")
            raise HTTPException(status_code=400, detail=str(ve))
        except TimeoutError as te:
            logger.error(f"Drake automation timed out: {str(te)}")
            raise HTTPException(status_code=504, detail=e)
        except Exception as e:
            logger.error(f"Drake automation failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=e)
                        
    except HTTPException as http_e:
        # Re-raise HTTP exceptions as-is
        logger.error(f"HTTP Exception: {http_e.detail}")
        raise http_e
    except Exception as e:
        # Catch any unexpected exceptions
        logger.error(f"Unexpected error during Drake launch/automation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected error during Drake automation: {str(e)}")

@app.post("/api/drake/notify-completion")
async def notify_drake_completion(
    request: DrakeCompletionNotifyRequest,
    background_tasks: BackgroundTasks,
):
    """
    Receives a notification from the frontend when a Drake automation step is complete
    and sends a summary email.
    """
    logger.info(f"Received Drake completion notification: {request.status} for client {request.clientName}")

    recipient = os.getenv("USER_EMAIL")
    if not recipient:
        logger.warning("USER_EMAIL not set. Cannot send Drake completion email.")
        return {"status": "skipped", "message": "Recipient email not configured on server."}

    # Load detailed results from file if jobId is provided
    details = []
    if request.jobId:
        try:
            details_path = BASE_OUTPUT_DIR / request.jobId / "output" / "drake_import_details.json"
            if details_path.exists():
                with open(details_path, "r", encoding="utf-8") as f:
                    details = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read drake import details for email: {e}")

    # Build the email content
    subject, html_body, text_body = build_drake_completion_email(
        status=request.status,
        client_name=request.clientName,
        client_id=request.clientId,
        form_type=request.formType,
        items=request.items,
        error_message=request.errorMessage,
        details=details,
    )

    # Send email in the background
    background_tasks.add_task(
        send_email,
        to_email=recipient,
        subject=subject,
        html_body=html_body,
        text_body=text_body,
    )

    return {"status": "success", "message": "Email notification queued."}

@app.post("/api/drake/query-clients")
async def query_drake_clients(background_tasks: BackgroundTasks):
    """
    Runs the Drake client export automation via Service B.
    """
    try:
        logger.info("🚀 Received request to query Drake for client list (via Service B).")
        result = await call_query_clients()
        logger.info(f"✓ Successfully loaded {len(result)} records")
        return result
    except Exception as e:
        logger.error(f"❌ Error querying Drake clients: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to query Drake clients. Please ensure Drake is open and try again.")


@app.get("/api/drake/file-metadata")
async def get_file_metadata():
    """
    Returns metadata about the latest export file including timestamp.
    """
    from pathlib import Path
    from datetime import datetime
    
    try:
        export_path = Path(EXPORT_FOLDER)
        if not export_path.exists():
            return {"exists": False, "message": "Export folder does not exist"}
        
        csv_files = list(export_path.glob("*.csv"))
        if not csv_files:
            return {"exists": False, "message": "No CSV files found in export folder"}
        
        # Get the most recently modified file
        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        file_stat = latest_file.stat()
        mod_time = datetime.fromtimestamp(file_stat.st_mtime)
        
        # Extract timestamp from filename (e.g., Sample_Client_Report_20260205_161929.csv)
        filename = latest_file.name
        parts = filename.split('_')
        timestamp_str = ""
        
        if len(parts) >= 4:
            date_part = parts[-2]  # e.g., "20260205"
            time_part = parts[-1].split('.')[0]  # e.g., "161929"
            if date_part.isdigit() and len(date_part) == 8 and len(time_part) == 6:
                formatted_date = f"{date_part[:4]}-{date_part[4:6]}-{date_part[6:8]}"
                formatted_time = f"{time_part[:2]}:{time_part[2:4]}:{time_part[4:6]}"
                timestamp_str = f"{formatted_date} {formatted_time}"
        
        return {
            "exists": True,
            "filename": filename,
            "timestamp": timestamp_str or mod_time.strftime("%Y-%m-%d %H:%M:%S"),
            "full_path": str(latest_file),
            "size_bytes": file_stat.st_size
        }
    except Exception as e:
        logger.error(f"Error getting file metadata: {e}")
        return {"exists": False, "message": f"Error: {str(e)}"}


@app.get("/api/drake/latest-clients")
async def get_latest_drake_clients():
    """
    Gets client data from the most recently exported CSV file without running automation.
    """
    
    try:
        logger.info("🚀 Received request for latest Drake client list from existing file.")
        
        # Get all CSV files in EXPORT_FOLDER
        export_path = Path(EXPORT_FOLDER)
        if not export_path.exists():
            logger.warning(f"Export folder does not exist: {EXPORT_FOLDER}")
            return []
        
        csv_files = list(export_path.glob("*.csv"))
        if not csv_files:
            logger.warning("No CSV files found in export folder.")
            return []
        
        # Get the most recently modified file
        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"Loading data from latest file: {latest_file}")

        # Read the CSV file directly here to avoid import issues
        try:
            df = pd.read_csv(str(latest_file), encoding="utf-8", sep=",", skiprows=2)
            df = df.iloc[:-1]
            df.columns = df.columns.str.strip()
            
            # Ensure the required columns exist before trying to select them
            required_cols = ["Taxpayer ID", "Taxpayer Name", "Return Type"]
            if all(col in df.columns for col in required_cols):
                result_df = df[required_cols].copy()
                
                # Replace NaN, NaT, and other non-JSON-serializable values with None
                result_df = result_df.astype(object).where(pd.notna(result_df), None)
                
                result = result_df.to_dict(orient='records')
                logger.info(f"✓ Successfully loaded {len(result)} records from {latest_file.name}")
                return result
            else:
                available_cols = df.columns.tolist()
                logger.error(f"CSV file is missing required columns. Expected: {required_cols}, Available: {available_cols}")
                return []
        except Exception as csv_error:
            logger.error(f"Failed to read CSV file {latest_file}: {csv_error}")
            return []
            
    except Exception as e:
        logger.error(f"❌ Error getting latest Drake clients: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching latest clients: {e}")

@app.delete("/api/jobs/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its files"""
    if job_id not in job_status:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_dir = BASE_OUTPUT_DIR / job_id
    if job_dir.exists():
        shutil.rmtree(job_dir)
    
    del job_status[job_id]
    return {"status": "deleted", "job_id": job_id}

class DrakePrintRequest(BaseModel):
    client_id: str
    return_type: str

def get_form_type_enum(return_type: str) -> Optional[FormType]:
    """Map return type string to FormType enum"""
    rt = str(return_type).upper()
    if "1120S" in rt or "1120-S" in rt: return FormType.FORM_1120S
    if "1120" in rt: return FormType.FORM_1120
    if "1065" in rt: return FormType.FORM_1065
    if "1040" in rt: return FormType.FORM_1040
    return None

@app.post("/api/drake/print-return")
async def print_drake_return(request: DrakePrintRequest, background_tasks: BackgroundTasks):
    """
    Opens Drake, finds the client, and selects forms for printing via Service B.
    """
    logger.info("=" * 25 + " BEGIN DRAKE PRINT RETURN (via Service B) " + "=" * 25)
    logger.info(f"Received print request for Client: {request.client_id}, Type: {request.return_type}")

    try:
        result = await call_print_return(request.model_dump())
    except Exception as e:
        logger.error(f"Print automation failed: {e}", exc_info=True)
        return {"status": "failed", "message": str(e)}

    generated_pdf_path = result.get("generated_pdf_path") if result else None
    outputs_parent_folder_from_service = result.get("outputs_parent_folder") if result else None

    # If a PDF was generated, create a processing job automatically
    if generated_pdf_path and os.path.exists(generated_pdf_path):
        def _derive_outputs_parent_folder(path_str: str, tax_id: str) -> Optional[str]:
            """
            Return relative outputs/<client-folder> from an absolute file path.
            Does not store absolute paths in DB.
            Never returns outputs/printers.
            """
            try:
                p = Path(path_str).resolve()
            except Exception:
                return None
            parts = list(p.parts)
            # Find "outputs" segment and take the next folder as client folder.
            tax_id_norm = str(tax_id or "").strip()
            for i, seg in enumerate(parts):
                if seg.lower() != "outputs":
                    continue

                # Prefer the first segment that clearly maps to this client (contains the tax_id).
                if tax_id_norm:
                    for j in range(i + 1, min(i + 8, len(parts))):
                        s = str(parts[j])
                        if tax_id_norm in s:
                            return str(Path("outputs") / s).replace("\\", "/")

                # Otherwise skip known intermediate folders like outputs/printers/<client-folder>/...
                intermediates = {"printers", "printer"}
                if i + 3 < len(parts) and str(parts[i + 1]).lower() in intermediates:
                    candidate = str(parts[i + 2])
                    return str(Path("outputs") / candidate)

                if i + 1 < len(parts):
                    candidate = str(parts[i + 1])
                    if candidate.lower() in intermediates:
                        return None
                    return str(Path("outputs") / candidate)
            # Fallback: if parent is directly under outputs in current repo layout
            parent = p.parent
            if parent and parent.name and parent.name.lower() not in {"printers", "printer"}:
                return str(Path("outputs") / parent.name)
            # Final fallback for printer path:
            # D:\...\printers\<name>.pdf -> outputs\<name>
            stem = p.stem.strip()
            if stem:
                return str(Path("outputs") / stem)
            return None

        def _normalize_outputs_parent_folder(path_str: Optional[str]) -> Optional[str]:
            """Normalize and validate relative outputs/<client-folder> path."""
            raw = str(path_str or "").strip()
            if not raw:
                return None
            rel = raw.replace("/", "\\").lstrip("\\")
            if not rel.lower().startswith("outputs\\"):
                return None
            parts = [p for p in rel.split("\\") if p]
            if len(parts) < 2:
                return None
            if parts[1].lower() in {"printers", "printer"}:
                return None
            return "\\".join(parts[:2])

        form_type_enum = get_form_type_enum(request.return_type)
        
        if form_type_enum:
            # Create Job ID
            filename = os.path.basename(generated_pdf_path)
            job_id = f"{form_type_enum.value}_{os.path.splitext(filename)[0]}"
            job_dir = BASE_OUTPUT_DIR / job_id
            job_dir.mkdir(exist_ok=True)
            
            dest_pdf_path = job_dir / filename
            
            # Copy the generated PDF to the job directory
            shutil.copy2(generated_pdf_path, dest_pdf_path)
            
            # Get page count
            page_count = 0
            try:
                page_count = get_pdf_page_count(str(dest_pdf_path))
            except Exception as e:
                logger.warning(f"Could not get page count for {dest_pdf_path}: {e}")

            # Initialize Job Status
            update_job_status(job_id, JobStatus.PENDING)
            job_status[job_id]["form_type"] = form_type_enum.value
            job_status[job_id]["filename"] = filename
            job_status[job_id]["pdf_path"] = str(dest_pdf_path)
            job_status[job_id]["client_id"] = request.client_id
            job_status[job_id]["page_count"] = page_count
            outputs_parent_folder = _normalize_outputs_parent_folder(outputs_parent_folder_from_service)
            if not outputs_parent_folder:
                outputs_parent_folder = _normalize_outputs_parent_folder(
                    _derive_outputs_parent_folder(generated_pdf_path, request.client_id)
                )
            job_status[job_id]["outputs_parent_folder"] = outputs_parent_folder
            if not outputs_parent_folder:
                logger.warning(
                    "Could not resolve outputs_parent_folder for client %s (generated_pdf_path=%s)",
                    request.client_id,
                    generated_pdf_path,
                )
            
            # DO NOT start processing here. The frontend flow (page detection -> process) will trigger it.
            # The old flow started a background task here, which caused a race condition with the frontend's own processing trigger.
            logger.info(f"✅ Job {job_id} created for client {request.client_id}. PDF copied. Ready for frontend to trigger processing.")
            
            return {"status": "success", "message": f"Job created. Job ID: {job_id}", "job_id": job_id}

    logger.error(f"❌ Failed to generate PDF for client: {request.client_id}")
    return {"status": "failed", "message": f"Failed to generate PDF for client: {request.client_id}"}


@app.get("/api/ocr-results")
async def proxy_ocr_results(tax_ids: str = Query(..., description="Comma-separated tax_ids")):
    """
    Service A proxy endpoint.
    Service A never reads/writes OCR DB directly; it calls Service B.
    """
    keys = [k.strip() for k in tax_ids.split(",") if k.strip()]
    if not keys:
        return []
    try:
        return await get_ocr_results(keys)
    except Exception as e:
        logger.warning("Service B unavailable for OCR results: %s", e)
        return []


class DrakeEfileBatchRequest(BaseModel):
    client_ids: List[str]
    open: bool = True
    close: bool = True


@app.post("/api/drake/efile/run-batch")
async def run_drake_efile_batch(request: DrakeEfileBatchRequest):
    """
    Runs Drake efile flow for all client_ids in one batch via Service B.
    Replaces open -> select-clients -> close flow.
    """
    if not request.client_ids:
        return {"status": "skipped", "message": "No client IDs provided", "processed_count": 0, "client_status": "Unknown"}
    try:
        result = await call_efile_run_batch(request.client_ids, open=request.open, close=request.close)
        return result
    except Exception as e:
        logger.error(f"EF batch failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/drake/efile/open")
async def open_drake_efile():
    """No-op: session is managed by run-batch. Kept for backward compatibility."""
    return {"status": "success"}


@app.post("/api/drake/efile/select-clients")
async def select_drake_efile_clients(request: DrakeEfileBatchRequest):
    """
    Proxies to run-batch. For backward compatibility when frontend calls select-clients with all ids.
    """
    if not request.client_ids:
        return {"status": "skipped", "message": "No client IDs provided", "processed_count": 0, "client_status": "Unknown"}
    try:
        result = await call_efile_run_batch(request.client_ids, open=request.open, close=request.close)
        return result
    except Exception as e:
        logger.error(f"EF select-clients failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


class DrakeEfileCloseRequest(BaseModel):
    success_count: int = 0


@app.post("/api/drake/efile/close")
async def close_drake_efile(request: DrakeEfileCloseRequest = None):
    """No-op: close is handled inside run-batch. Kept for backward compatibility."""
    return {"status": "success"}

class EfileBatchSummaryRequest(BaseModel):
    totals: Dict[str, int]
    details: List[Dict[str, Any]]
    user_email: Optional[str] = None

@app.post("/api/drake/efile/send-summary")
async def send_efile_batch_summary(request: EfileBatchSummaryRequest, background_tasks: BackgroundTasks):
    """
    Sends a summary email after the Drake EF Batch process is complete.
    """
    subject, html, text = build_efile_batch_summary_email(
        totals=request.totals,
        details=request.details
    )
    
    user_email = request.user_email or os.getenv("USER_EMAIL", "")
    if user_email:
        logger.info(f"Sending EF Batch summary email to {user_email}")
        background_tasks.add_task(send_email, user_email, subject, html, text)
    
    return {"status": "email summary queued"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
