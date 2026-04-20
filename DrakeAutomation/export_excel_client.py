# main.py
import sys
import os
# Add project root to sys.path to allow running this script directly
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import traceback
import threading

import pandas as pd
from DrakeAutomation.core.app import OpenDrake
from DrakeAutomation.flows.login import LoginFlow
from DrakeAutomation.flows.exportclient import ExportClientFlow
from DrakeAutomation.ui.logger import setup_logger
from DrakeAutomation.config import USERNAME, PASSWORD, EXPORT_FOLDER, DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE, DRAKE24_CWD, DRAKE24_EXE, DRAKE24_TITLE
import pandas as pd

log = setup_logger("main")


def run_automation_flow(session, results=None):
    """Run automation flow (Reports -> Report Manager -> My Reports -> Sample Client Report)."""
    try:
        log.info("=" * 60)
        log.info("Starting Drake Automation (Background Mode)")
        log.info("=" * 60)

        log.info("Logging in...")
        log.info("Username: %s", USERNAME)
        LoginFlow(session).login(USERNAME, PASSWORD)

        log.info("Opening Reports -> Report Manager -> My Reports -> Sample Client Report...")
        efile_status = ExportClientFlow(session)
        export_path = efile_status.open_efile_reports()
        
        if export_path:
            log.info("File ready for processing: %s", export_path)
            # Save results to shared list so main() can retrieve it
            if results is not None:
                results.append(export_path)
            
            # Read CSV file into pandas DataFrame
            try:
                df = pd.read_csv(export_path)
                log.info("Loaded CSV into pandas DataFrame. Shape: %s", df.shape)
                log.info("Columns: %s", df.columns.tolist())
            except Exception as e:
                log.error("Failed to read CSV with pandas: %s", e)

    except Exception as e:
        log.error("=" * 60)
        log.error("Error in automation flow: %s", e)
        log.error("=" * 60)
        log.debug(traceback.format_exc())
        raise

def main(run_in_background=False):
    """Main automation flow
    
    Args:
        run_in_background: If True, run automation in background thread to avoid blocking user interaction
    """
    t1 = time.time()
    session = None
    results = []  # Container to catch results from thread or function
    
    try:
        log.info("=" * 60)
        log.info("Starting Drake Automation")
        log.info("Background mode: %s", run_in_background)
        log.info("=" * 60)
        
        
        # Open Drake (reuse cached session if available)
        log.info("Opening Drake application...")
        session = OpenDrake(DRAKE_EXE, DRAKE_CWD, DRAKE_TITLE).open()
        
        if run_in_background:
            # Run automation in background thread
            log.info("Running automation in background thread...")
            log.info("You can continue using your computer while automation runs.")
            automation_thread = threading.Thread(
                target=run_automation_flow,
                args=(session, results),
                daemon=True  # Daemon thread will automatically exit when main thread exits
            )
            automation_thread.start()
            
            # Wait for thread to complete (or can return immediately to not block)
            automation_thread.join()
            log.info("Background automation completed")
        else:
            # Run automation in main thread (blocking)
            run_automation_flow(session, results)
            
        # Close Drake
        if session and session.main.exists():
            session.main.close()
        
        # Return file path if available
        if results:
            return results[0]
        
    except Exception as e:
        elapsed = time.time() - t1
        log.error("=" * 60)
        log.error("Error after %.2fs: %s", elapsed, e)
        log.error("=" * 60)
        log.debug(traceback.format_exc())
        raise
        
    finally:
        if session:
            try:
                log.info("Session kept alive for reuse")
            except Exception as ex:
                log.warning("Error during cleanup: %s", ex)
                
def get_latest_file(folder):
    files = [
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
    ]
    if not files:
        return None
    return max(files, key=os.path.getmtime)

def get_lastest_file_path():
    return get_latest_file(EXPORT_FOLDER)
