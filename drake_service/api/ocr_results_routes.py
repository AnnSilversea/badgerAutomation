"""OCR results API - Service B owns OCR persistence."""

import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from drake_service.database.session import get_db
from drake_service.database.models import OCR_TAX_RETURN_STATUS_VALUES
from drake_service.repositories.ocr_tax_return_repository import get_by_tax_ids, upsert_result

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ocr-results", tags=["OCR Results"])


class OcrResultUpsertRequest(BaseModel):
    tax_id: str = Field(..., description="Drake client identifier (Taxpayer ID)")
    outputs_parent_folder: str = Field(..., description="Relative outputs/<client-folder>")
    ocr_status: str = Field(..., description="EXTRACTED | EXTRACTED_FAIL")
    client_name: Optional[str] = None
    error_message: Optional[str] = None
    processed_at: Optional[datetime] = None


@router.get("")
async def list_ocr_results(
    tax_ids: str = Query(..., description="Comma-separated tax_ids"),
    db: Session = Depends(get_db),
):
    """
    Query OCR results by tax_id list.
    Returns a list of records (one per tax_id when present).
    """
    keys = [k.strip() for k in tax_ids.split(",") if k.strip()]
    if not keys:
        return []
    rows = get_by_tax_ids(db, keys)
    return [
        {
            "tax_id": r.tax_id,
            "client_name": r.client_name,
            "outputs_parent_folder": r.outputs_parent_folder,
            "ocr_status": r.ocr_status,
            "processed_at": r.processed_at.isoformat() if r.processed_at else None,
        }
        for r in rows
    ]


@router.post("/upsert")
async def upsert_ocr_result(
    payload: OcrResultUpsertRequest,
    db: Session = Depends(get_db),
):
    """
    Internal endpoint used by Service A when OCR completes/fails.
    """
    if payload.ocr_status not in OCR_TAX_RETURN_STATUS_VALUES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid ocr_status: {payload.ocr_status}. Must be one of {OCR_TAX_RETURN_STATUS_VALUES}",
        )
    if payload.ocr_status == "EXTRACTED_FAIL" and not (payload.error_message or "").strip():
        # error_message is optional in schema, but only makes sense on failure
        logger.info("OCR upsert failure without error_message", extra={"tax_id": payload.tax_id})

    rec = upsert_result(
        db,
        tax_id=payload.tax_id,
        outputs_parent_folder=payload.outputs_parent_folder,
        ocr_status=payload.ocr_status,
        processed_at=payload.processed_at,
        client_name=payload.client_name,
        error_message=payload.error_message,
    )
    return {
        "status": "ok",
        "tax_id": rec.tax_id,
        "ocr_status": rec.ocr_status,
        "outputs_parent_folder": rec.outputs_parent_folder,
    }

