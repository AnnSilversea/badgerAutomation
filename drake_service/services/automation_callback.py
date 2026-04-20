"""
Update workitem status in database directly.
Service B owns the database - no HTTP callbacks to Service A.
Used by Celery worker during automation execution.
"""
import logging
from typing import Optional

from drake_service.database.session import get_db_context
from drake_service.repositories.automation_repository import upsert_status

logger = logging.getLogger(__name__)


def update_workitem_status(perma_key: str, status: str, message: Optional[str] = None) -> None:
    """
    Update workitem status in database. Called by Celery worker.
    """
    try:
        with get_db_context() as db:
            upsert_status(db, perma_key, status, message)
        logger.info(
            "Updated workitem status",
            extra={"perma_key": perma_key, "status": status},
        )
    except Exception as e:
        logger.error(
            "Failed to update workitem status",
            extra={"perma_key": perma_key, "status": status, "error": str(e)},
            exc_info=True,
        )


def notify_queued(perma_key: str) -> None:
    """Mark job as queued."""
    update_workitem_status(perma_key, "IN_QUEUE")


def notify_processing(perma_key: str) -> None:
    """Mark automation as started (IN_PROCESSING)."""
    update_workitem_status(perma_key, "IN_PROCESSING")


def notify_result(perma_key: str, status: str, message: Optional[str] = None) -> None:
    """
    Mark automation completed.
    status: SUCCESS | FAIL | CLIENT_NOT_FOUND | MISSING_TAX_ID
    """
    update_workitem_status(perma_key, status, message=message)
