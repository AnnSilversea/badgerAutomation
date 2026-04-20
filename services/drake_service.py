# services/drake_service.py
import time
import logging
import pyautogui
from typing import Any, Dict, List, Optional, Tuple

from DrakeAutomation.config import (
    DRAKE24_CWD, DRAKE24_EXE, DRAKE24_TITLE, USERNAME, PASSWORD, DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE
)
from DrakeAutomation.core.app import OpenDrake
from DrakeAutomation.flows.login import LoginFlow
from DrakeAutomation.flows.efile_status import EfileStatus
from DrakeAutomation.ocr_normalization import normalize_id

logger = logging.getLogger(__name__)


# -----------------------------
# Helpers for better logs
# -----------------------------
def _mask_id(value: Optional[str], keep_last: int = 4) -> str:
    """Mask SSN/EIN for logging (shows only last N digits)."""
    if not value:
        return "None"
    s = str(value).strip()
    if len(s) <= keep_last:
        return "*" * len(s)
    return "*" * (len(s) - keep_last) + s[-keep_last:]


class StepTimer:
    """Context manager to time and log step duration."""
    def __init__(self, label: str, level: int = logging.INFO):
        self.label = label
        self.level = level
        self.t0 = None

    def __enter__(self):
        self.t0 = time.perf_counter()
        logger.log(self.level, f"[Drake] START: {self.label}")
        return self

    def __exit__(self, exc_type, exc, tb):
        dt = (time.perf_counter() - self.t0) if self.t0 else 0
        if exc:
            logger.error(f"[Drake] FAILED: {self.label} ({dt:.2f}s) -> {exc}", exc_info=True)
        else:
            logger.log(self.level, f"[Drake] DONE: {self.label} ({dt:.2f}s)")


# -----------------------------
# Drake open & navigation
# -----------------------------
def open_efile_session() -> Tuple[Any, Any, EfileStatus]:
    """Open Drake, log in, and navigate to the E-File Status search dialog."""
    with StepTimer("Launch Drake"):
        session = OpenDrake(DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE).open()

    with StepTimer("Log in"):
        LoginFlow(session=session).login(USERNAME, PASSWORD)
    
    from pywinauto import findwindows
    win_update = findwindows.find_windows(title_re=r"Drake 20\d{2} Tax Software Updates")
    if win_update:
        win_update = session.app.window(handle=win_update[0])
        btn_cancel = win_update.child_window(title="Cancel", control_type="Button")
        if btn_cancel:
            btn_cancel.set_focus()
            btn_cancel.invoke()
            time.sleep(0.5)

    efile = EfileStatus(session=session)

    with StepTimer("Open E-File Status report"):
        efile._click_CSM()

    with StepTimer("Open Client Status Manager and Search dialog"):
        win = efile.dialog_client_status()
        efile.open_search_dialog(win=win)

    logger.info("[Drake] Session ready: E-File Status dialog is open.")
    return session, win, efile


def clear_find_client_dialog(efile: EfileStatus) -> None:
    """Clear the 'Find Client Record' dialog input."""
    win_search = efile._wait_for_window(title_re=r"Drake \d{4} CSM - \s*Find Client Record")
    win_search.set_focus()
    win_search.type_keys("^A")
    win_search.type_keys("{DEL}")
    time.sleep(0.3)


# -----------------------------
# Main check loop
# -----------------------------
def check_clients_status_in_drake(
    targets: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Returns:
        updates: [{workItemKey, efileStatus}]
        logs: per-client processing logs (1 log per client)
    """
    updates: List[Dict[str, str]] = []
    logs: List[Dict[str, Any]] = []

    logger.info(f"[Drake] Starting processing for {len(targets)} target(s).")

    session = win = efile = None

    try:
        session, win, efile = open_efile_session()

        for idx, item in enumerate(targets, start=1):
            key = item.get("workItemKey")
            ui_name = (item.get("clientName") or "").strip()
            drake_name = (item.get("clientDrakeName") or ui_name).strip()
            reg = item.get("registrationNumber")

            try:
                logger.info(
                    f"[Drake] ({idx}/{len(targets)}) WorkItem={key} | "
                    f"UIName='{ui_name}' | DrakeName='{drake_name}' | Reg={_mask_id(reg)}"
                )

                # -----------------------------
                # Missing registration number
                # -----------------------------
                if not reg:
                    logs.append({
                        "workItemKey": key,
                        "registrationNumber": reg,
                        "client": ui_name,
                        "result": "skipped",
                        "reason": "missing_registration_number",
                        "drake_status": None,
                        "status": "Skipped (missing SSN/EIN)"
                    })
                    logger.warning(f"[Drake] Skipping WorkItem={key}: missing registrationNumber")
                    continue

                # -----------------------------
                # Normalize ID
                # -----------------------------
                try:
                    client_id = normalize_id(reg)
                    logger.debug(f"[Drake] Normalized ID for WorkItem={key}: {_mask_id(client_id)}")
                except Exception as e:
                    logs.append({
                        "workItemKey": key,
                        "registrationNumber": reg,
                        "client": ui_name,
                        "result": "failed",
                        "reason": "normalize_id_failed",
                        "drake_status": None,
                        "error": str(e)
                    })
                    logger.error(
                        "Workitem processing failed",
                        extra={"workitem_id": key, "error": str(e), "reason": "normalize_id_failed"},
                        exc_info=True,
                    )
                    continue

                # -----------------------------
                # Lookup Drake status
                # -----------------------------
                try:
                    with StepTimer(f"Lookup E-File status (WorkItem={key})"):
                        status = efile.get_client_status(
                            win=win,
                            client_id=client_id,
                            client_name=drake_name
                        )

                    log_entry = {
                        "workItemKey": key,
                        "registrationNumber": reg,
                        "client": ui_name,
                        "result": "successful",
                        "reason": None,
                        "drake_status": status
                    }

                    if status is None:
                        log_entry["result"] = "skipped"
                        log_entry["reason"] = "client_not_found"
                        log_entry["drake_status"] = "Client not found in Drake"
                        log_entry["status"] = "Skipped (client not found in Drake)"
                        logger.info(f"[Drake] Skipped WorkItem={key}: client not found in Drake")

                    elif status in ("EF Accepted", "EF Rejected"):
                        updates.append({"workItemKey": key, "efileStatus": status})
                        logger.info(f"[Drake] Queued for update: WorkItem={key} -> {status}")

                    else:
                        log_entry["result"] = "skipped"
                        log_entry["reason"] = "ineligible_status"
                        log_entry["status"] = f"Skipped (ineligible status: {status})"
                        logger.info(f"[Drake] No update required for WorkItem={key} (status={status})")

                    logs.append(log_entry)

                except Exception as e:
                    logs.append({
                        "workItemKey": key,
                        "registrationNumber": reg,
                        "client": ui_name,
                        "result": "failed",
                        "reason": "drake_lookup_error",
                        "drake_status": "Error",
                        "error": str(e)
                    })
                    logger.error(
                        "Workitem processing failed",
                        extra={"workitem_id": key, "error": str(e), "reason": "drake_lookup_error"},
                        exc_info=True,
                    )

                # Clear dialog for next iteration, regardless of success/failure
                try:
                    clear_find_client_dialog(efile)
                except Exception as clear_e:
                    logger.warning(
                        f"[Drake] Could not clear search input for WorkItem={key}: {clear_e}",
                        exc_info=True
                    )

            except Exception as e:
                # Outer catch: any unexpected exception - log FAIL and continue to next workitem
                logger.error(
                    f"[Drake] Unexpected error processing WorkItem={key}: {e}",
                    extra={"workitem_id": key, "error": str(e)},
                    exc_info=True,
                )
                logs.append({
                    "workItemKey": key,
                    "registrationNumber": reg,
                    "client": ui_name,
                    "result": "failed",
                    "reason": "unexpected_error",
                    "drake_status": None,
                    "error": str(e)
                })

    finally:
        # If DrakeAutomation exposes a close/quit method, call it here.
        if session:
            try:
                logger.info("[Drake] Closing Drake session.")
                # Attempt to close windows gracefully first.
                # The search dialog is likely a child of the CSM window, but we close it first to be safe.
                if efile:
                    try:
                        win_search = efile._wait_for_window(title_re=r"Drake \d{4} CSM - \s*Find Client Record", timeout=2)
                        if win_search and win_search.exists():
                            win_search.close()
                    except Exception:
                        pyautogui.press('esc') # Fallback for dialogs

                if win and win.exists(timeout=2):
                    win.close()

                # Close the main application window
                if session.main and session.main.exists(timeout=2):
                    session.main.close()

            except Exception as e:
                logger.warning(f"[Drake] Graceful close failed, attempting to kill process: {e}", exc_info=True)
                try:
                    session.app.kill()
                except Exception:
                    pass

        logger.info(f"[Drake] Finished. updates={len(updates)} logs={len(logs)}")

    return updates, logs