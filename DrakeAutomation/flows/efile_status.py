from DrakeAutomation.core.session import DrakeSession
from DrakeAutomation.ui.logger import setup_logger
log = setup_logger("flows.efile_status")

from pywinauto import Desktop, findwindows, WindowSpecification

import time
import re

class EfileStatus:
    def __init__(self, session: DrakeSession):
        self.app = session.app
        self.main = session.main
        
    def _wait_for_window(self, title_re: str, timeout: int = 60) -> WindowSpecification:
        """Waits for a window matching the title regex and sets it as current."""
        end = time.time() + timeout
        while time.time() < end:
            hwnds = findwindows.find_windows(title_re=title_re)
            if hwnds:
                # Use app.window if possible, fallback to Desktop if needed
                win = self.app.window(handle=hwnds[0])
                try:
                    win.wait("visible enabled ready", timeout=10)
                    self.current_window = win
                    log.info(f"Window found: {title_re}")
                    return win
                except Exception as e:
                    log.debug(f"Window found but not ready: {e}")
            time.sleep(0.5)
        raise TimeoutError(f"Window '{title_re}' not found within {timeout}s")
    
    def _click_CSM(self):
        self.main.set_focus()
        self.main.type_keys("^l")
        return None
    
    def dialog_client_status(self):
        win = self._wait_for_window(title_re=r"Drake \d{4} - \s*Client Status Manager")
        win.set_focus()
        # win.print_control_identifiers()
        return win
    
    def open_search_dialog(self, win):
        if win:
            win.set_focus()
            win.type_keys("^f")
            log.info("Search dialog opened.")
        return None
    

    def find_client_record(self, client_id: str = None, client_name: str = None):
        win = self._wait_for_window(title_re=r"Drake \d{4} CSM - \s*Find Client Record")
        win.set_focus()
        if client_id:
            win.type_keys(f"{client_id}")
        elif client_name:
            win.type_keys(f"{client_name}")
        return None
        
    def get_rows(self, win):
        list_box = win.child_window(auto_id="2011", control_type="List")
        if list_box.exists(timeout=2):
            return list_box.children(control_type="ListItem")
        return []

    def get_selected_row_data(self, win):
        rows = self.get_rows(win)
        for i, row in enumerate(rows):
            if row.is_selected():
                data = [c.window_text() for c in row.children(control_type="Text")]
                log.info(f"Selected row found at index {i}: {data}")
                return data
        log.info("No row is currently selected.")
        return None
    
    def get_client_status(self, win, client_id: str = None, client_name: str = None):
        """
        Finds a client, verifies the record, and returns the status.
        """
        log.info(f"Verifying client record for ID: {client_id}, Name: {client_name}")
        self.find_client_record(client_id=client_id, client_name=client_name)
        
        selected_data = self.get_selected_row_data(win)
        
        if not selected_data:
            log.warning("No row was selected after search.")
            return None

        # Assuming column order: ID (0), Client Name (1), Type (2), Preparer (3), Status (4)
        # This is based on your print_control_identifiers output
        record_id = selected_data[0] if len(selected_data) > 0 else ""
        record_name = selected_data[1] if len(selected_data) > 1 else ""
        record_status = selected_data[4] if len(selected_data) > 4 else ""
        
        log.info(f"Parsed Record - ID: '{record_id}', Name: '{record_name}', Status: '{record_status}'")
        
        # Verify by both ID (last 4 digits) and name if both are provided
        id_match = client_id and record_id and client_id[-4:] == record_id[-4:]
        
        name_match = False
        if client_name and record_name:
            # 1. Simple substring match (Old logic)
            if client_name.lower() in record_name.lower():
                name_match = True
            else:
                # 2. Robust match (word subset) - Handles "First Last" vs "Last, First"
                client_name_parts = set(re.sub(r'[,.]', '', client_name.lower()).split())
                record_name_parts = set(re.sub(r'[,.]', '', record_name.lower()).split())
                if client_name_parts and client_name_parts.issubset(record_name_parts):
                    name_match = True
                
        if id_match and name_match:
            log.info(f"Client record verified. Status: {record_status}")
            return record_status
        else:
            log.warning(f"Verification failed. Found ID: '{record_id}', Name: '{record_name}'")
            return None