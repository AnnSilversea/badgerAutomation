"""Queue activity metadata helper.

Queue/broker inspection has been intentionally removed to avoid coupling
status APIs to Celery broker queue state.
"""
from typing import Dict


def get_queue_activity(queue_name: str | None = None) -> Dict[str, int | bool | str]:
    """
    Return a neutral queue metadata payload without broker inspection.

    queue_empty is kept as informational metadata only and defaults to False.
    """
    q_name = queue_name or "drake_queue"
    return {
        "queue_name": q_name,
        "pending_count": 0,
        "running_count": 0,
        "queue_empty": False,
    }
