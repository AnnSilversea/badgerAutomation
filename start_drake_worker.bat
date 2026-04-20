@echo off
REM Start Celery worker for Drake automation (from project root)
cd /d "%~dp0"
celery -A drake_service.core.celery_app:celery_app worker --loglevel=info -Q drake_queue --pool=solo
