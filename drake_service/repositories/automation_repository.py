"""Backward-compatible wrapper for efile job repository. Use efile_job_repository directly for new code."""
from typing import List, Optional

from sqlalchemy.orm import Session

from drake_service.repositories import efile_job_repository as efile_repo


def get_by_permakey(db: Session, permakey: str):
    """Get efile job by workitem_id (permakey = Karbon workItemKey)."""
    return efile_repo.get_by_workitem_id(db, permakey)


def get_by_permakeys(db: Session, permakeys: List[str]):
    """Get efile jobs for multiple workitem_ids."""
    return efile_repo.get_by_workitem_ids(db, permakeys)


def list_paginated(db: Session, limit: int = 50, offset: int = 0, status_filter: Optional[str] = None):
    """List efile jobs with pagination."""
    return efile_repo.list_paginated(db, limit, offset, status_filter)


def upsert_queued(db: Session, permakey: str, triggered_by: Optional[str] = None):
    """Mark efile job as IN_QUEUE."""
    return efile_repo.upsert_queued(db, permakey, client_id=None)


def upsert_status(db: Session, permakey: str, status: str, message: Optional[str] = None):
    """Update efile job status."""
    return efile_repo.upsert_status(db, permakey, status, message, client_id=None)


def clear_in_queue(db: Session) -> int:
    """Delete stale efile rows with IN_QUEUE status."""
    return efile_repo.clear_in_queue(db)
