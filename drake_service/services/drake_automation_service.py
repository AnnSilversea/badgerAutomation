"""
Drake automation execution service.
Wraps existing DrakeAutomation logic - DO NOT modify internal logic.
"""
import logging
import time
import os
import json
import threading
import asyncio
from typing import Any, Dict, List, Optional, Tuple, Set
from dotenv import load_dotenv

load_dotenv()

# Add parent to path so we can import from DrakeAutomation
import sys
from pathlib import Path
_root = Path(__file__).resolve().parent.parent.parent
import pandas as pd
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

_outputs_dir = Path(os.getenv("AUTOMATION_OUTPUTS_DIR", _root / "outputs"))
if not _outputs_dir.exists():
    _outputs_dir.mkdir(parents=True, exist_ok=True)

import pyautogui
from pywinauto import findwindows

from DrakeAutomation.drake_fill_in_flow import run_drake_fill_in_flow
from DrakeAutomation.ocr_normalization import normalize_id
from DrakeAutomation.export_excel_client import main as run_export_client_flow, get_latest_file, EXPORT_FOLDER
from DrakeAutomation.config import DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE, USERNAME, PASSWORD
from DrakeAutomation.core.app import OpenDrake
from DrakeAutomation.flows.login import LoginFlow
from DrakeAutomation.flows.efile_status import EfileStatus
from DrakeAutomation.flows.package import PackagePDF
from DrakeAutomation.flows.client import ClientFlow
from DrakeAutomation.flows.efile import EFPrepareFlow
from DrakeAutomation.flows.search_clientID import ClientSelectionFlow
from DrakeAutomation.ui.waits import wait_data_entry

from services.drake_service import check_clients_status_in_drake, open_efile_session, clear_find_client_dialog

logger = logging.getLogger(__name__)

_EFILE_STATUS_SESSION_CACHE = {
    "session": None,
    "win": None,
    "efile": None,
    "lock": threading.RLock(),
}

_EFILE_BATCH_CACHE = {
    "session": None,
    "total_success": 0,
    "lock": threading.RLock(),
}


def _verify_karbon_update_for_efile_status(work_item_key: str, drake_status: str) -> Tuple[bool, str]:
    """
    Update Karbon WorkItem status and verify update success.
    Returns (ok, message). ok=True only when Karbon update is confirmed.
    """
    try:
        from services.karbon_service import update_work_items_for_efile_status
    except Exception as e:
        return False, f"Cannot import karbon update service: {e}"

    try:
        payload = [{"workItemKey": work_item_key, "efileStatus": drake_status}]
        result = asyncio.run(update_work_items_for_efile_status(payload))
    except Exception as e:
        return False, f"Karbon update exception: {e}"

    if not isinstance(result, dict):
        return False, "Karbon update returned invalid response"

    if int(result.get("updated", 0)) > 0 and int(result.get("failed", 0)) == 0:
        return True, "Karbon updated"

    detail_reason = None
    for d in result.get("details", []) or []:
        if str(d.get("workItemKey")) == str(work_item_key):
            detail_reason = d.get("reason") or d.get("status")
            break
    return False, f"{detail_reason or result}"

def _get_latest_drake_clients_from_file() -> List[Dict[str, Any]]:
    """
    Gets client data from the most recently exported CSV file.
    """
    try:
        logger.info("Reading latest Drake client list from existing file.")
        export_path = Path(EXPORT_FOLDER)
        if not export_path.exists():
            logger.warning(f"Export folder does not exist: {EXPORT_FOLDER}")
            return []

        csv_files = list(export_path.glob("*.csv"))
        if not csv_files:
            logger.warning("No CSV files found in export folder.")
            return []

        latest_file = max(csv_files, key=lambda p: p.stat().st_mtime)
        logger.info(f"Loading data from latest file: {latest_file}")

        try:
            df = pd.read_csv(str(latest_file), encoding="utf-8", sep=",", skiprows=2)
            df = df.iloc[:-1]
            df.columns = df.columns.str.strip()

            required_cols = ["Taxpayer ID", "Taxpayer Name", "Return Type"]
            if all(col in df.columns for col in required_cols):
                result_df = df[required_cols].copy()
                result_df = result_df.astype(object).where(pd.notna(result_df), None)
                result = result_df.to_dict(orient='records')
                logger.info(f"Successfully loaded {len(result)} records from {latest_file.name}")
                return result
            else:
                available_cols = df.columns.tolist()
                logger.error(f"CSV file is missing required columns. Expected: {required_cols}, Available: {available_cols}")
                return []
        except Exception as csv_error:
            logger.error(f"Failed to read CSV file {latest_file}: {csv_error}")
            return []

    except Exception as e:
        logger.error(f"Error getting latest Drake clients from file: {e}", exc_info=True)
        return []


def _list_outputs_child_dirs(outputs_root: Path) -> Set[str]:
    """Return direct child directory names under outputs root."""
    if not outputs_root.exists():
        return set()
    names: Set[str] = set()
    for item in outputs_root.iterdir():
        if item.is_dir():
            names.add(item.name)
    return names


def _extract_outputs_parent_folder_from_pdf_path(
    generated_pdf_path: Optional[str],
    outputs_root: Path,
) -> Optional[str]:
    """
    Best-effort extraction for relative outputs/<client-folder>.
    Never returns outputs/printers.
    """
    if not generated_pdf_path:
        return None
    try:
        p = Path(generated_pdf_path).resolve()
    except Exception:
        return None

    # If path is under outputs root, prefer the first child directory under outputs.
    try:
        rel = p.relative_to(outputs_root.resolve())
        rel_parts = list(rel.parts)
        if rel_parts:
            first = str(rel_parts[0])
            if first.lower() not in {"printers", "printer"}:
                return os.path.normpath(str(Path("outputs") / first))
            # Path under outputs/printers/<client-folder>/file.pdf
            if len(rel_parts) >= 3:
                second = str(rel_parts[1])
                if second:
                    return os.path.normpath(str(Path("outputs") / second))
    except Exception:
        pass

    # Generic fallback by scanning for "outputs" segment.
    parts = list(p.parts)
    for i, seg in enumerate(parts):
        if str(seg).lower() != "outputs":
            continue
        if i + 1 >= len(parts):
            continue
        first = str(parts[i + 1])
        if first.lower() not in {"printers", "printer"}:
            return os.path.normpath(str(Path("outputs") / first))
        if i + 3 < len(parts):
            second = str(parts[i + 2])
            if second:
                return os.path.normpath(str(Path("outputs") / second))
        if i + 2 < len(parts):
            second_candidate_path = Path(*parts[: i + 3])
            if second_candidate_path.exists() and second_candidate_path.is_dir():
                return os.path.normpath(str(Path("outputs") / parts[i + 2]))
            return None

    # Final fallback requested by business rule:
    # D:\...\printers\2025 1040 (... )_timestamp.pdf -> outputs\2025 1040 (... )_timestamp
    stem = p.stem.strip()
    if stem:
        return os.path.normpath(str(Path("outputs") / stem))
    return None


def execute_drake_launch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Drake fill-in flow. Logic unchanged from original app.py.
    """
    job_id = payload.get("job_id")
    client_id_raw = payload.get("client_id")
    raw_data = payload.get("data")

    if not raw_data:
        raise ValueError("No data provided for automation.")
    if not job_id:
        raise ValueError("Job ID is missing.")
    if not client_id_raw:
        raise ValueError("Client ID is missing.")

    client_id = normalize_id(client_id_raw)
    if not client_id:
        raise ValueError("The Client ID could not be processed.")

    # ========== VALIDATE CLIENT IN DRAKE LIST ==========
    client_tax_return_data = _get_latest_drake_clients_from_file()
    client_name = "Unknown"
    
    if client_tax_return_data:
        client_found = False
        for client in client_tax_return_data:
            if client.get("Taxpayer ID") == client_id:
                client_name = client.get("Taxpayer Name", "Unknown")
                client_found = True
                
                return_type = str(client.get("Return Type", "")).strip()
                if return_type != "1040":
                    return {
                        "status": "failed",
                        "message": f"Client Return Type is '{return_type}', expected '1040'.",
                        "job_id": job_id,
                        "client_id": client_id,
                        "items_processed": 0
                    }
                break

        if not client_found:
            from services.email_service import mask_id_last4
            return {
                "status": "failed",
                "message": f"Client ID {mask_id_last4(client_id)} was not found in the Drake client list.",
                "job_id": job_id,
                "client_id": client_id,
                "items_processed": 0
            }
    else:
        logger.warning("Could not retrieve latest client list to validate Client ID.")
        return {
            "status": "failed",
            "message": 'Could not retrieve the client list to validate the Client ID.\nPlease go to "Extract Drake Client List" to query Drake.',
            "job_id": job_id,
            "client_id": client_id,
            "items_processed": 0
        }

    # ========== END VALIDATION ==========
    data_items = raw_data if isinstance(raw_data, list) else [raw_data]
    if not data_items:
        raise ValueError("No records found to import.")

    form_type = []
    try:
        form_type = list({
            item.get("fields", {}).get("FormType", {}).get("value")
            for item in data_items
            if isinstance(item, dict) and item.get("fields", {}).get("FormType", {}).get("value")
        })
    except (IndexError, AttributeError, TypeError):
        pass
    
    if not form_type:
        raise ValueError("Could not determine the tax form type.")

    start_time = time.time()
    data_items = run_drake_fill_in_flow(
        form_type=form_type,
        client_id=client_id,
        list_data=data_items
    )
    elapsed_time = time.time() - start_time

    # Extract summary details to save to file (avoiding large payload in response)
    summary_details = []
    for item in data_items:
        try:
            fields = item.get("fields", {})
            def _get_val(obj):
                if isinstance(obj, dict) and "value" in obj: return obj["value"]
                return obj
            
            ft = _get_val(fields.get("FormType"))
            payer_name = None
            id_num = None
            
            if ft == "W2":
                emp = _get_val(fields.get("Employer", {})) or {}
                payer_name = emp.get("Name", {}).get("value", "")
                id_num = emp.get("EIN", {}).get("value", "")
            elif ft == "SSA":
                payer_name = "SOCIAL SECURITY ADMINISTRATION"
            else:
                # 1099 forms (DIV, INT, MISC, NEC, R, etc.)
                payer = _get_val(fields.get("Payer", {})) or {}
                payer_name = payer.get("Name", {}).get("value")
                id_num = payer.get("TIN", {}).get("value")
                
            summary_details.append({
                "FormType": ft,
                "PayerName": payer_name,
                "ID": id_num
            })
        except Exception:
            continue

    details_filename = None
    try:
        if job_id:
            job_dir = _outputs_dir / job_id
            if not job_dir.exists():
                job_dir.mkdir(parents=True, exist_ok=True)

            output_dir = job_dir / "output"
            output_dir.mkdir(exist_ok=True)
            
            dest_file = output_dir / "drake_import_details.json"
            with open(dest_file, "w", encoding="utf-8") as f:
                json.dump(summary_details, f, indent=2, ensure_ascii=False)
            details_filename = str(dest_file.resolve())
    except Exception as e:
        logger.warning(f"Failed to save import details to file: {e}")

    return {
        "status": "success",
        "message": f"Drake automation completed successfully for {len(data_items)} items.",
        "job_id": job_id,
        "client_id": client_id,
        "form_type": form_type,
        "items_processed": len(data_items),
        "execution_time_seconds": round(elapsed_time, 2),
        "details_file": details_filename
    }


def execute_query_clients() -> List[Dict[str, Any]]:
    """Execute Drake client export flow. Logic unchanged."""
    import pandas as pd

    exported_file_path = run_export_client_flow(run_in_background=False)
    if not exported_file_path:
        exported_file_path = get_latest_file(EXPORT_FOLDER)
    if not exported_file_path:
        raise RuntimeError("Unable to export client list from Drake.")
    import os
    if not os.path.exists(exported_file_path):
        raise RuntimeError("Exported file not found.")

    df = pd.read_csv(exported_file_path, encoding="utf-8", sep=",", skiprows=2)
    df = df.iloc[:-1]
    df.columns = df.columns.str.strip()
    required_cols = ["Taxpayer ID", "Taxpayer Name", "Return Type"]
    if not all(col in df.columns for col in required_cols):
        raise RuntimeError("The exported client list format is invalid.")
    result_df = df[required_cols].copy()
    result_df = result_df.astype(object).where(pd.notna(result_df), None)
    return result_df.to_dict(orient="records")


def execute_print_return(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Drake print return flow. Logic unchanged from app.py."""
    client_id = payload.get("client_id")
    return_type = payload.get("return_type")
    if not client_id or not return_type:
        raise ValueError("client_id and return_type required")

    generated_pdf_path = None
    outputs_root = _outputs_dir
    outputs_before = _list_outputs_child_dirs(outputs_root)

    session = OpenDrake(DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE).open()
    LoginFlow(session=session).login(USERNAME, PASSWORD)

    win_update = findwindows.find_windows(title_re=r"Drake 20\d{2} Tax Software Updates")
    if win_update:
        win_update = session.app.window(handle=win_update[0])
        btn_cancel = win_update.child_window(title="Cancel", control_type="Button")
        if btn_cancel:
            btn_cancel.set_focus()
            btn_cancel.invoke()
            time.sleep(0.5)

    client_flow = ClientFlow(session)
    client_flow.open_dialog()
    client_flow.search(client_id=client_id)

    if client_flow.open_by_last4(client_id=client_id):
        main_entry = wait_data_entry(session.app, client_id)
        main_entry.set_focus()
        main_entry.type_keys("^p")
        time.sleep(2)
        generated_pdf_path = PackagePDF(session, return_type=return_type).select_forms()
    else:
        logger.error(f"Client not found: {client_id}")
        try:
            if session.main.exists(timeout=2):
                session.main.close()
        except Exception:
            session.app.kill()
        return {"status": "failed", "message": f"Failed to generate PDF for client: {client_id}"}

    try:
        if main_entry.exists(timeout=2):
            main_entry.set_focus()
            main_entry.type_keys("{ESC}")
        if session.main.exists(timeout=2):
            session.main.set_focus()
            session.main.close()
        else:
            session.app.kill()
    except Exception as e:
        logger.warning(f"Error closing main window: {e}")
        session.app.kill()

    if generated_pdf_path:
        outputs_after = _list_outputs_child_dirs(outputs_root)
        newly_created = outputs_after - outputs_before
        outputs_parent_folder = None
        if newly_created:
            newest_dir = max(
                (outputs_root / folder_name for folder_name in newly_created),
                key=lambda p: p.stat().st_mtime if p.exists() else 0,
            )
            outputs_parent_folder = os.path.normpath(str(Path("outputs") / newest_dir.name))
        else:
            outputs_parent_folder = _extract_outputs_parent_folder_from_pdf_path(
                generated_pdf_path=generated_pdf_path,
                outputs_root=outputs_root,
            )

        return {
            "status": "success",
            "generated_pdf_path": generated_pdf_path,
            "outputs_parent_folder": outputs_parent_folder,
            "client_id": client_id,
            "return_type": return_type,
        }
    return {"status": "failed", "message": f"Failed to generate PDF for client: {client_id}"}


def execute_efile_open() -> Dict[str, Any]:
    """Execute Drake efile open flow. Logic unchanged."""
    session = OpenDrake(DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE).open()
    LoginFlow(session=session).login(USERNAME, PASSWORD)
    win_update = findwindows.find_windows(title_re=r"Drake 20\d{2} Tax Software Updates")
    if win_update:
        win_update = session.app.window(handle=win_update[0])
        btn_cancel = win_update.child_window(title="Cancel", control_type="Button")
        if btn_cancel:
            btn_cancel.set_focus()
            btn_cancel.invoke()
            time.sleep(0.5)
    ef_flow = EFPrepareFlow(session)
    ef_flow.open_efile()
    ef_flow.click_after_prepare_extensions()
    return {"status": "success", "session_id": id(session)}


def execute_efile_select_clients(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Drake efile select clients. Requires session - runs as part of composite flow."""
    raise NotImplementedError("Use execute_efile_batch for open+select+close")


def execute_efile_close(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Execute Drake efile close. Requires session - runs as part of composite flow."""
    raise NotImplementedError("Use execute_efile_batch for open+select+close")


def execute_efile_batch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Composite: open Drake efile, select clients, then close.
    Replicates open -> select-clients -> close flow from app.py.
    """
    client_ids = payload.get("client_ids", [])
    do_open = payload.get("open", True)
    do_close = payload.get("close", True)

    with _EFILE_BATCH_CACHE["lock"]:
        session = _EFILE_BATCH_CACHE["session"]

        if not client_ids and not do_open and not do_close:
            return {"status": "skipped", "message": "No client IDs provided", "processed_count": 0, "client_status": "Unknown"}
        
        if do_open:
            _EFILE_BATCH_CACHE["total_success"] = 0
            if session:
                try:
                    session.app.kill()
                except Exception:
                    pass
                session = None

            session = OpenDrake(DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE).open()
            LoginFlow(session=session).login(USERNAME, PASSWORD)
            win_update = findwindows.find_windows(title_re=r"Drake 20\d{2} Tax Software Updates")
            if win_update:
                win_update = session.app.window(handle=win_update[0])
                btn_cancel = win_update.child_window(title="Cancel", control_type="Button")
                if btn_cancel:
                    btn_cancel.set_focus()
                    btn_cancel.invoke()
                    time.sleep(0.5)
            ef_flow = EFPrepareFlow(session)
            ef_flow.open_efile()
            ef_flow.click_after_prepare_extensions()
            
            _EFILE_BATCH_CACHE["session"] = session
        
        if not session:
            raise RuntimeError("Drake E-File session is not active. Please restart the batch process.")

        results = {}
        success_count = 0
        try:
            for client_id in client_ids:
                status = ClientSelectionFlow(session).run(client_id=client_id)
                results[client_id] = status
                if status == "Success":
                    success_count += 1
                    _EFILE_BATCH_CACHE["total_success"] = _EFILE_BATCH_CACHE.get("total_success", 0) + 1
        except Exception as e:
            logger.error(f"EF Selection Automation failed: {e}")
            try:
                session.main.close() if session.main.exists(timeout=2) else session.app.kill()
                _EFILE_BATCH_CACHE["session"] = None
            except Exception:
                pass
            raise

        if do_close:
            first_error = None
            pid = None
            try:
                pid = session.app.process
            except Exception:
                pass
            
            try:
                dialog = ClientSelectionFlow(session=session)._get_client_selection_dialog()
                if dialog:
                    if _EFILE_BATCH_CACHE.get("total_success", 0) > 0:
                        ClientSelectionFlow(session=session)._click_next_after_client_selection(dialog=dialog)
            except Exception as e:
                first_error = e

            time.sleep(2)
            for _ in range(50):
                try:
                    handles = findwindows.find_windows(title_re=r"Drake 20\d{2} - EF Return Selector.*")
                    if not handles:
                        break
                    win = session.app.window(handle=handles[0])
                    win.set_focus()
                    win.close()
                    time.sleep(1)
                except Exception as e:
                    if not first_error: first_error = e
                    break
            
            time.sleep(2)
            try:
                handles = findwindows.find_windows(title_re=r"Drake 20\d{2} - Batch Extensions Client Selection.*")
                if handles:
                    win = session.app.window(handle=handles[0])
                    win.set_focus()
                    win.close()
            except Exception as e:
                if not first_error:
                    first_error = e
            time.sleep(2)
            try:
                handles = findwindows.find_windows(title_re=r"Drake 20\d{2} - Batch Extensions.*")
                if handles:
                    win = session.app.window(handle=handles[0])
                    win.set_focus()
                    win.close()
            except Exception as e:
                if not first_error:
                    first_error = e
            try:
                if session.main.exists(timeout=2):
                    session.main.close()
            except Exception as e:
                if not first_error:
                    first_error = e
            time.sleep(2)
            try:
                if pid:
                    import subprocess
                    subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, text=True)
                else:
                    session.app.kill()
            except Exception as e:
                if not first_error:
                    first_error = e
            
            # Clear cache
            _EFILE_BATCH_CACHE["session"] = None

            if first_error:
                raise first_error

    client_status = results.get(client_ids[0], "Unknown") if client_ids else "Unknown"
    return {"status": "success", "processed_count": len(client_ids), "client_status": client_status, "results": results}



def execute_efile_status_batch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute efile status check for multiple targets.
    Each workitem is processed independently - failure of one never stops the batch.
    Always updates database (SUCCESS/CLIENT_NOT_FOUND/FAIL) for each item.
    Returns updates and details - Karbon update is done by Service A.
    Calls Service A callbacks for status/result updates.
    """
    targets = payload.get("targets", [])
    if not targets:
        return {"updates": [], "details": []}

    try:
        from .automation_callback import notify_queued, notify_processing, notify_result
    except ImportError:
        import sys
        from pathlib import Path
        _root = Path(__file__).resolve().parent.parent.parent
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        from drake_service.services.automation_callback import notify_queued, notify_processing, notify_result

    target_keys = [str(item.get("workItemKey")) for item in targets if item.get("workItemKey")]

    # Per-record lifecycle: IN_QUEUE when queued, IN_PROCESSING when starting
    for key in target_keys:
        try:
            notify_queued(key)
        except Exception as e:
            logger.warning("Failed to mark workitem queued", extra={"workitem_id": key, "error": str(e)})
    for key in target_keys:
        try:
            notify_processing(key)
        except Exception as e:
            logger.warning("Failed to mark workitem processing", extra={"workitem_id": key, "error": str(e)})

    updates: List[Dict[str, Any]] = []
    details: List[Dict[str, Any]] = []

    try:
        updates, details = check_clients_status_in_drake(targets)
    except Exception as e:
        # Session open failed - mark ALL as FAIL, do not re-raise (batch must not crash)
        err_msg = str(e)
        if hasattr(e, "response") and hasattr(e.response, "status_code"):
            err_msg = f"HTTP {e.response.status_code}: {err_msg}"
        logger.error(
            "Batch session failed - marking all workitems as FAIL",
            extra={"error": err_msg, "workitem_count": len(target_keys)},
            exc_info=True,
        )
        for key in target_keys:
            try:
                notify_result(key, "FAIL", err_msg)
            except Exception as db_e:
                logger.warning("Failed to update DB for workitem", extra={"workitem_id": key, "error": str(db_e)})
        return {"updates": [], "details": []}

    # Map Drake result -> DB status (CLIENT_NOT_FOUND is NOT a failure)
    keys_with_result = set()
    for d in details:
        key = d.get("workItemKey")
        if not key:
            continue
        key_str = str(key)
        keys_with_result.add(key_str)
        result = d.get("result", "")
        reason = d.get("reason", "")
        drake_status = d.get("drake_status")
        try:
            if result == "successful":
                # Only mark SUCCESS if the status is one we can actually sync
                if drake_status in ("EF Accepted", "EF Rejected"):
                    ok, msg = _verify_karbon_update_for_efile_status(key_str, drake_status)
                    if ok:
                        notify_result(key_str, "SUCCESS", drake_status)
                    else:
                        notify_result(key_str, "FAIL", msg)
                else:
                    notify_result(key_str, "FAIL", f"Status '{drake_status}' not valid for Karbon sync")
            elif reason == "client_not_found":
                notify_result(key_str, "CLIENT_NOT_FOUND", "Client not found in Drake")
            elif reason == "missing_registration_number":
                notify_result(key_str, "MISSING_TAX_ID", "Missing Tax ID/SSN")
            else:
                msg = d.get("error") or d.get("status") or reason or "Error"
                notify_result(key_str, "FAIL", str(msg))
        except Exception as db_e:
            logger.warning("Failed to update DB for workitem", extra={"workitem_id": key_str, "error": str(db_e)})

    # Any target not in details gets FAIL (e.g. malformed item)
    for key in target_keys:
        if key not in keys_with_result:
            try:
                notify_result(key, "FAIL", "Processing did not complete")
            except Exception as db_e:
                logger.warning("Failed to update DB for workitem", extra={"workitem_id": key, "error": str(db_e)})

    return {"updates": updates, "details": details}


def _update_fi_job(
    work_item_key: str | None,
    tax_id: str | None,
    client_name: str | None,
    status: str,
    message: str | None,
) -> None:
    """Update Filing Instruction job status in database."""
    try:
        from drake_service.database.session import get_db_context
        from drake_service.repositories.fi_job_repository import set_in_progress, update_status
        wk = str(work_item_key) if work_item_key else None
        if not wk:
            return
        with get_db_context() as db:
            if status in ("SUCCESS", "FAIL"):
                update_status(db, wk, status, message, tax_id=tax_id, client_name=client_name)
            else:
                set_in_progress(db, wk, tax_id=tax_id, client_name=client_name)
    except Exception as e:
        logger.warning("Failed to update FI job status: %s", e)


def execute_fi_batch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute Filing Instructions batch: open Drake, print FI for each client, upload to Karbon.
    Tracks job status in karbon_filing_instruction_jobs.
    """
    targets = payload.get("targets", [])
    close_drake = payload.get("close_drake", True)

    if not targets:
        return {"processed_count": 0, "totals": {"updated": 0, "failed_drake": 0, "failed_karbon": 0, "skipped": 0}, "details": []}

    results = []
    stats = {"updated": 0, "failed_drake": 0, "failed_karbon": 0, "skipped": 0}

    from karbon_api.client import KarbonClient
    from karbon_api.files import upload_file
    from services.karbon_service import env

    session = OpenDrake(DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE).open()
    LoginFlow(session=session).login(USERNAME, PASSWORD)
    win_update = findwindows.find_windows(title_re=r"Drake 20\d{2} Tax Software Updates")
    if win_update:
        win_update = session.app.window(handle=win_update[0])
        btn_cancel = win_update.child_window(title="Cancel", control_type="Button")
        if btn_cancel:
            btn_cancel.set_focus()
            btn_cancel.invoke()
            time.sleep(0.5)

    karbon_client = KarbonClient(
        access_key=env("KARBON_ACCESS_KEY"),
        bearer_token=env("KARBON_BEARER_TOKEN")
    )

    try:
        client_flow = ClientFlow(session)
        for item in targets:
            tax_id = item.get("registrationNumber")
            client_name = item.get("clientName")
            work_item_key = item.get("workItemKey")

            if not tax_id:
                _update_fi_job(work_item_key, None, client_name, "FAIL", "Missing Tax ID")
                results.append({"client": client_name, "registrationNumber": None, "workItemKey": work_item_key, "status": "failed", "message": "Missing Tax ID"})
                stats["skipped"] += 1
                continue

            _update_fi_job(work_item_key, tax_id, client_name, "IN_PROGRESS", None)
            try:
                client_flow.open_dialog()
                client_flow.search(tax_id)
                if not client_flow.open_by_last4(tax_id):
                    _update_fi_job(work_item_key, tax_id, client_name, "FAIL", "Client not found in Drake")
                    results.append({"client": client_name, "registrationNumber": tax_id, "workItemKey": work_item_key, "status": "failed", "message": "Client not found in Drake"})
                    stats["failed_drake"] += 1
                    client_flow.close_dialog()
                    continue

                main_entry = wait_data_entry(session.app, tax_id)
                main_entry.set_focus()
                main_entry.type_keys("^p")
                time.sleep(2)
                pdf_path = PackagePDF(session, FI=True).select_forms()

                if pdf_path and __import__("os").path.exists(pdf_path):
                    try:
                        upload_file(karbon_client, pdf_path, workitem_keys=work_item_key)
                        _update_fi_job(work_item_key, tax_id, client_name, "SUCCESS", "FI uploaded to Karbon")
                        results.append({"client": client_name, "registrationNumber": tax_id, "workItemKey": work_item_key, "status": "success", "message": "FI uploaded to Karbon"})
                        stats["updated"] += 1
                    except Exception as e:
                        msg = f"Fail updating karbon: {str(e)}"
                        _update_fi_job(work_item_key, tax_id, client_name, "FAIL", msg)
                        results.append({"client": client_name, "registrationNumber": tax_id, "workItemKey": work_item_key, "status": "failed", "message": msg})
                        stats["failed_karbon"] += 1
                else:
                    _update_fi_job(work_item_key, tax_id, client_name, "FAIL", "No FI generated")
                    results.append({"client": client_name, "registrationNumber": tax_id, "workItemKey": work_item_key, "status": "failed", "message": "No FI generated"})
                    stats["failed_drake"] += 1

                try:
                    if main_entry.exists():
                        main_entry.set_focus()
                        main_entry.type_keys("{ESC}")
                except Exception as cleanup_e:
                    logger.warning(f"Failed to close data entry window for {client_name}: {cleanup_e}")

            except Exception as e:
                logger.error(f"Error processing FI for {client_name}: {e}", exc_info=True)
                err_msg = str(e)
                _update_fi_job(work_item_key, tax_id, client_name, "FAIL", err_msg)
                results.append({"client": client_name, "registrationNumber": tax_id, "workItemKey": work_item_key, "status": "failed", "message": err_msg})
                stats["failed_drake"] += 1
                try:
                    session.app.type_keys("{ESC}")
                except Exception:
                    pass
    finally:
        if close_drake:
            try:
                if session.main.exists(timeout=2):
                    session.main.set_focus()
                    session.main.close()
                else:
                    session.app.kill()
            except Exception:
                try:
                    session.app.kill()
                except Exception:
                    pass

    return {"processed_count": len(targets), "totals": stats, "details": results}


def _efile_status_open() -> Dict[str, Any]:
    """
    Internal helper to open or reuse a Drake e-file status session.
    MUST be called within the asyncio lock.
    Returns the context dictionary.
    """
    # Check if session is already active and valid
    if (
        _EFILE_STATUS_SESSION_CACHE["session"]
        and _EFILE_STATUS_SESSION_CACHE["win"]
        and _EFILE_STATUS_SESSION_CACHE["efile"]
        and _EFILE_STATUS_SESSION_CACHE["win"].exists(timeout=2)
    ):
        logger.info("[Drake] Reusing existing E-File Status session.")
        return _EFILE_STATUS_SESSION_CACHE

    logger.info("[Drake] No active session found. Opening a new E-File Status session.")
    session, win, efile = open_efile_session()
    _EFILE_STATUS_SESSION_CACHE["session"] = session
    _EFILE_STATUS_SESSION_CACHE["win"] = win
    _EFILE_STATUS_SESSION_CACHE["efile"] = efile
    logger.info("[Drake] Session ready: E-File Status dialog is open.")
    return _EFILE_STATUS_SESSION_CACHE


def _efile_status_check(context: Dict, client_id: str, client_name: Optional[str]) -> Optional[str]:
    """Internal helper to perform a status check using a given context."""
    efile = context["efile"]
    win = context["win"]
    status = efile.get_client_status(win=win, client_id=client_id, client_name=client_name)
    try:
        clear_find_client_dialog(efile)
    except Exception as e:
        logger.warning(f"Could not clear search dialog: {e}")
    return status


def _efile_status_force_close():
    """
    Internal helper to forcefully close the Drake session and clear the cache.
    MUST be called within the asyncio lock.
    """
    session = _EFILE_STATUS_SESSION_CACHE.get("session")
    if not session:
        logger.info("[Drake] No active session to close.")
        return

    logger.info("[Drake] Force closing Drake session.")
    try:
        # Attempt graceful close of windows first
        efile = _EFILE_STATUS_SESSION_CACHE.get("efile")
        if efile:
            try:
                win_search = efile._wait_for_window(title_re=r"Drake \d{4} CSM - \s*Find Client Record", timeout=2)
                if win_search and win_search.exists():
                    win_search.close()
            except Exception:
                pyautogui.press('esc') # Fallback

        win = _EFILE_STATUS_SESSION_CACHE.get("win")
        if win and win.exists(timeout=2):
            win.close()

        if session.main and session.main.exists(timeout=2):
            session.main.close()
    except Exception as e:
        logger.warning(f"[Drake] Graceful close failed, killing process: {e}")
        try:
            session.app.kill()
        except Exception as kill_e:
            logger.error(f"Failed to kill process: {kill_e}")
    finally:
        # Clear the cache regardless of close success
        _EFILE_STATUS_SESSION_CACHE["session"] = None
        _EFILE_STATUS_SESSION_CACHE["win"] = None
        _EFILE_STATUS_SESSION_CACHE["efile"] = None
        logger.info("[Drake] Session cache cleared.")


def execute_efile_status_open_session() -> Dict[str, Any]:
    """Opens and caches a persistent Drake e-file status session."""
    with _EFILE_STATUS_SESSION_CACHE["lock"]:
        _efile_status_open()
    return {"status": "success", "message": "E-file status session is active."}


def execute_efile_status_check_client(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Checks a single client's e-file status using the cached session."""
    client_id = payload.get("client_id")
    client_name = payload.get("client_name")
    work_item_key = payload.get("work_item_key")

    if not client_id:
        raise ValueError("client_id is required for e-file status check.")

    try:
        from .automation_callback import notify_queued, notify_processing, notify_result
    except ImportError:
        import sys
        from pathlib import Path
        _root = Path(__file__).resolve().parent.parent.parent
        if str(_root) not in sys.path:
            sys.path.insert(0, str(_root))
        from drake_service.services.automation_callback import notify_queued, notify_processing, notify_result

    if work_item_key:
        notify_queued(str(work_item_key))
        notify_processing(str(work_item_key))

    status = None
    try:
        with _EFILE_STATUS_SESSION_CACHE["lock"]:
            # _efile_status_open will either open a new session or return the cached one.
            context = _efile_status_open()
            status = _efile_status_check(context, client_id, client_name)

        if work_item_key:
            if status in ("EF Accepted", "EF Rejected"):   
                ok, msg = _verify_karbon_update_for_efile_status(str(work_item_key), status)
                if ok:
                    notify_result(str(work_item_key), "SUCCESS", status)
                else:
                    notify_result(str(work_item_key), "FAIL", msg)
            elif status is None or (isinstance(status, str) and "not found" in status.lower()):
                notify_result(str(work_item_key), "CLIENT_NOT_FOUND", "Client not found in Drake")
            else:
                notify_result(str(work_item_key), "FAIL", status)

        return {"status": "success", "drake_status": status}
    except Exception as e:
        if work_item_key:
            logger.error(
                "E-file status check failed for workitem",
                extra={"perma_key": work_item_key, "client_name": client_name, "error": str(e)},
                exc_info=True,
            )
            err_msg = str(e)
            notify_result(str(work_item_key), "FAIL", err_msg)
        raise  # Re-raise to let caller return consistent error response


def execute_efile_status_close_session() -> Dict[str, Any]:
    """Closes the cached Drake e-file status session."""
    with _EFILE_STATUS_SESSION_CACHE["lock"]:
        _efile_status_force_close()
    return {"status": "success", "message": "E-file status session closed."}


def execute_efile_status_open_check_close_DEPRECATED(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Efile status: open session, check one client, close.
    For interactive check-client flow.
    Always sends final status callback (SUCCESS, CLIENT_NOT_FOUND, or FAIL).
    """
    client_id = payload.get("client_id")
    client_name = payload.get("client_name")
    work_item_key = payload.get("work_item_key")
