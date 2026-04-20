# flows/search_clientID.py
import time
import os
import pyautogui
from datetime import datetime
from pywinauto import findwindows
from DrakeAutomation.ui.logger import setup_logger
from DrakeAutomation.ui.control import edit_text
from pywinauto.timings import wait_until
from pywinauto import Desktop

log = setup_logger("flows.search_clientID")

class ClientSelectionFlow:
    """
    EF Flow:
    - Open the EF menu -> Prepare Extensions
    - Tick the options in Batch Extensions (STEP 1) and click Next
    - On the Client Selection screen (STEP 2): manually enter CLIENT_ID, select the client, and click Next.
    """

    def __init__(self, session):
        self.app = session.app
        self.main = session.main
        
    def _take_screenshot(self, title):
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_title = "".join(c for c in str(title) if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
            filename = f"Error_{safe_title}_{timestamp}.png"
            log_dir = os.path.join(os.getcwd(), "logs", "screenshots")
            os.makedirs(log_dir, exist_ok=True)
            filepath = os.path.join(log_dir, filename)
            pyautogui.screenshot(filepath)
            log.info(f"Screenshot saved to {filepath}")
            return filepath
        except Exception as e:
            log.error(f"Failed to take screenshot: {e}")
            return None

    def wait(self, title, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            hwnds = findwindows.find_windows(title=title)
            if hwnds:
                win = self.app.window(handle=hwnds[0])
                win.wait("visible enabled", timeout=5)
                return win
            time.sleep(0.15)
            
        screenshot = self._take_screenshot(title)
        
        raise TimeoutError(f"Window not found: {title}. The automation could not locate the required window. Screenshot saved at: {screenshot}")

    def _get_client_selection_dialog(self, timeout=15):
        """Find and return the Client Selection dialog (STEP 2)."""
        log.info("Waiting for Client Selection dialog (STEP 2)...")
        title = "Drake 2025 - Batch Extensions Client Selection"
        wait = self.wait(title, timeout=timeout)
        
        return wait

    def _search_and_select_client(self, dialog, client_id: str):
        """Enter client_id, click 'Select Client', and choose the client from the list."""
        log.info(f"Searching for client ID: {client_id}")

        search_client = dialog.child_window(auto_id="8001", control_type="Edit")
        search_client.set_focus()
        search_client.type_keys(f"{client_id}")
        
        dialog.set_focus()
        dialog.type_keys("{ENTER}", set_foreground=False)
        
        time.sleep(1)
        
        win_error = findwindows.find_windows(title_re="Invalid File Type")
        if win_error:
            win_error = self.app.window(handle=win_error[0])
            
            win_error.set_focus()
            win_error.type_keys("{ENTER}")
            log.debug(f"{client_id} is not available")
            return "Invalid File Type"

        win_pay_per_return = findwindows.find_windows(title_re="Drake 2025 - Pay Per Return")
        if win_pay_per_return:
            win_pay_per_return = self.app.window(handle=win_pay_per_return[0])
            
            win_pay_per_return.set_focus()
            win_pay_per_return.type_keys("{ENTER}")
            log.debug(f"{client_id} has not been paid")
            return "Pay Per Return"

        win_file_not_found = findwindows.find_windows(title_re="File Not Found")
        if win_file_not_found:
            win_file_not_found = self.app.window(handle=win_file_not_found[0])
            
            win_file_not_found.set_focus()
            win_file_not_found.type_keys("{ENTER}")
            log.debug(f"{client_id} is not found")
            return "File Not Found"
        
        else:
        
            log.info("Enter button clicked")
            return "Success"
        

    def _click_next_after_client_selection(self, dialog):
        """Click the Next > button after selecting the client."""
        log.info("Clicking Next button to proceed after client selection...")
        dialog.set_focus()
        dialog.type_keys("{ENTER}", set_foreground=False)
        log.info("✓ Next button clicked (Client Selection)")

    def run(self, client_id: str = None):
        """Run flow: wait for Client Selection -> search and select client by CLIENT_ID -> Next."""
        log.info("Searching and selecting client by CLIENT_ID...")
        dialog = self._get_client_selection_dialog()
        log.info("Client Selection dialog found")
        result = self._search_and_select_client(dialog, client_id=client_id)
        log.info(f"Client selection result: {result}")
        return result
        # self._click_next_after_client_selection(dialog)
