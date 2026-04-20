"""Celery app configuration for Drake Service (Service B)."""
from celery import Celery
from kombu import Queue
import os

# Load broker URL from environment or default to local Redis
# This ensures both the web app and the worker use the same broker
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "drake_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["drake_service.tasks.automation_tasks"],  # This tells the worker which modules contain tasks
)

# --- Configuration ---

# This is the critical setting. It MUST be False for the worker to receive tasks.
# If True, tasks are executed synchronously in the process that called .delay(),
# which is why the worker process was idle.
celery_app.conf.task_always_eager = False

# Define the queue that the worker listens to.
# This matches the `-Q drake_queue` argument in the worker startup command.
celery_app.conf.task_queues = (
    Queue("drake_queue", routing_key="drake_queue"),
)
# Set the default queue for all tasks to be 'drake_queue'
celery_app.conf.task_default_queue = "drake_queue"
celery_app.conf.task_default_exchange = "drake_queue"
celery_app.conf.task_default_routing_key = "drake_queue"


# Standard Celery settings for reliability and compatibility.
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Acknowledge tasks after they complete, not when they are received.
    # This prevents tasks from being lost if the worker crashes during execution.
    task_acks_late=True,
    # Worker will prefetch 1 task at a time. Since automations are long-running
    # and resource-intensive (using pywinauto), this is a safe setting.
    worker_prefetch_multiplier=1,
)
