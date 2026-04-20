"""Repository for ocr_tax_return_results table."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from drake_service.database.models import OcrTaxReturnResult


def get_by_tax_ids(db: Session, tax_ids: List[str]) -> List[OcrTaxReturnResult]:
    if not tax_ids:
        return []
    cleaned = [str(t).strip() for t in tax_ids if str(t).strip()]
    if not cleaned:
        return []
    return db.query(OcrTaxReturnResult).filter(OcrTaxReturnResult.tax_id.in_(cleaned)).all()


def upsert_result(
    db: Session,
    *,
    tax_id: str,
    outputs_parent_folder: str,
    ocr_status: str,
    processed_at: Optional[datetime] = None,
    client_name: Optional[str] = None,
    error_message: Optional[str] = None,
) -> OcrTaxReturnResult:
    """
    Upsert by tax_id (unique).

    Rules:
    - Always updates outputs_parent_folder + ocr_status + processed_at
    - Sets error_message only when provided; clears it on success (EXTRACTED)
    """
    now = datetime.utcnow()
    tax_id = (tax_id or "").strip()
    if not tax_id:
        raise ValueError("tax_id is required")

    outputs_parent_folder = (outputs_parent_folder or "").strip()
    if not outputs_parent_folder:
        raise ValueError("outputs_parent_folder is required")

    rec = db.query(OcrTaxReturnResult).filter(OcrTaxReturnResult.tax_id == tax_id).first()
    if rec:
        rec.outputs_parent_folder = outputs_parent_folder
        rec.ocr_status = ocr_status
        rec.updated_at = now
        rec.processed_at = processed_at or now
        if client_name is not None:
            rec.client_name = client_name
        # Clear error on success, set on fail when provided
        if ocr_status == "EXTRACTED":
            rec.error_message = None
        elif error_message is not None:
            rec.error_message = error_message
    else:
        rec = OcrTaxReturnResult(
            tax_id=tax_id,
            client_name=client_name,
            outputs_parent_folder=outputs_parent_folder,
            ocr_status=ocr_status,
            error_message=None if ocr_status == "EXTRACTED" else error_message,
            created_at=now,
            updated_at=now,
            processed_at=processed_at or now,
        )
        db.add(rec)

    db.commit()
    db.refresh(rec)
    return rec

