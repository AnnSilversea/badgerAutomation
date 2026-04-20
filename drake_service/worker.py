"""
Celery worker for Drake automation tasks.
Run from project root (BadgerAutomation):

  celery -A drake_service.core.celery_app:celery_app worker --loglevel=info -Q drake_queue

On Windows use --pool=solo:

  celery -A drake_service.core.celery_app:celery_app worker --loglevel=info -Q drake_queue --pool=solo
"""
# Ensure project root is in path when worker starts
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
