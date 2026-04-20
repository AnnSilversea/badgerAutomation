"""
Centralized automation status constants and mapping.
Used by backend, Drake service callbacks, and referenced by frontend mapping.

Standard status rules:
- IN_QUEUE: automation queued
- IN_PROCESSING: automation running
- SUCCESS: automation success (message = response)
- CLIENT_NOT_FOUND: client not in Drake (NOT an error)
- FAIL: any error (automation, HTTP, timeout, etc.)
"""
from typing import Tuple

# Canonical database status values
IN_QUEUE = "IN_QUEUE"
IN_PROCESSING = "IN_PROCESSING"
SUCCESS = "SUCCESS"
FAIL = "FAIL"
CLIENT_NOT_FOUND = "CLIENT_NOT_FOUND"
MISSING_TAX_ID = "MISSING_TAX_ID"
NOT_STARTED = "NOT_STARTED"

# Legacy aliases (backward compatibility)
PROCESSING = "PROCESSING"  # same as IN_PROCESSING
ERROR = "FAIL"  # alias - use FAIL
FAILED = "FAIL"  # alias

# All valid DB statuses
VALID_STATUSES: Tuple[str, ...] = (
    NOT_STARTED,
    IN_QUEUE,
    IN_PROCESSING,
    SUCCESS,
    FAIL,
    CLIENT_NOT_FOUND,
    MISSING_TAX_ID,
    "AGENCY_ACCEPTED",  # legacy - prefer SUCCESS + message
    "AGENCY_REJECTED",  # legacy - prefer SUCCESS + message
)

# Statuses that indicate "in progress" - do not re-trigger
IN_PROGRESS_STATUSES = (IN_QUEUE, IN_PROCESSING)

# Statuses that allow re-trigger
RE_TRIGGERABLE_STATUSES = (NOT_STARTED, FAIL)

# Terminal statuses (set completed_at)
TERMINAL_STATUSES = (SUCCESS, FAIL, CLIENT_NOT_FOUND, MISSING_TAX_ID)
