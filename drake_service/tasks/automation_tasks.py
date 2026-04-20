"""Celery tasks for Drake automation - all execution goes through these tasks."""
import logging
from typing import Any, Dict

from drake_service.core.celery_app import celery_app
from drake_service.services import drake_automation_service

logger = logging.getLogger(__name__)


@celery_app.task(name="drake_service.tasks.automation_tasks.run_drake_launch", bind=True)
def run_drake_launch(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Drake fill-in flow."""
    try:
        return drake_automation_service.execute_drake_launch(payload_dict)
    except Exception as e:
        logger.exception("run_drake_launch failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_query_clients", bind=True)
def run_query_clients(self) -> list:
    """Execute Drake client export flow."""
    try:
        return drake_automation_service.execute_query_clients()
    except Exception as e:
        logger.exception("run_query_clients failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_print_return", bind=True)
def run_print_return(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Drake print return flow."""
    try:
        return drake_automation_service.execute_print_return(payload_dict)
    except Exception as e:
        logger.exception("run_print_return failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_efile_batch", bind=True)
def run_efile_batch(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Drake efile open + select clients + close."""
    try:
        return drake_automation_service.execute_efile_batch(payload_dict)
    except Exception as e:
        logger.exception("run_efile_batch failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_efile_status_batch", bind=True)
def run_efile_status_batch(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Execute efile status check for multiple targets."""
    try:
        return drake_automation_service.execute_efile_status_batch(payload_dict)
    except Exception as e:
        logger.exception("run_efile_status_batch failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_fi_batch", bind=True)
def run_fi_batch(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Filing Instructions batch."""
    try:
        return drake_automation_service.execute_fi_batch(payload_dict)
    except Exception as e:
        logger.exception("run_fi_batch failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_efile_status_open_session", bind=True)
def run_efile_status_open_session(self) -> Dict[str, Any]:
    """Opens a persistent Drake e-file status session."""
    try:
        return drake_automation_service.execute_efile_status_open_session()
    except Exception as e:
        logger.exception("run_efile_status_open_session failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_efile_status_check_client", bind=True)
def run_efile_status_check_client(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Checks a single client's e-file status using the cached session."""
    try:
        return drake_automation_service.execute_efile_status_check_client(payload_dict)
    except Exception as e:
        logger.exception("run_efile_status_check_client failed")
        raise


@celery_app.task(name="drake_service.tasks.automation_tasks.run_efile_status_close_session", bind=True)
def run_efile_status_close_session(self) -> Dict[str, Any]:
    """Closes the cached Drake e-file status session."""
    try:
        return drake_automation_service.execute_efile_status_close_session()
    except Exception as e:
        logger.exception("run_efile_status_close_session failed")
        raise
