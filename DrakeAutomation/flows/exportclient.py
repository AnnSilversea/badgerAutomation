# flows/exportclient.py
import os
import time
import re
from datetime import datetime
from typing import Optional

from pywinauto import Desktop, findwindows, WindowSpecification
from DrakeAutomation.ui.logger import setup_logger
from DrakeAutomation.ui.control import select_checkbox

from DrakeAutomation.flows.uia_utils import safe_set_edit_text
from DrakeAutomation.config import EXPORT_FOLDER


log = setup_logger("flows.exportclient")


class ExportClientFlow:
    """
    Flow:
    - Click toolbar item Reports
    - Click dropdown item "Report Manager"
    - Select "My Reports" and "Sample Client Report"
    - Click "View Report"
    - Click "Basic Search Conditions"
    - Export report to Excel
    """
    
    # Constants for UI elements and titles
    TITLE_REPORT_MANAGER = r"Drake 2025.*Report Manager"
    TITLE_BASIC_SEARCH = r"Drake 2025.*Basic Search Conditions"
    TITLE_REPORT_VIEWER = r"Report Viewer"
    TITLE_SAVE_DIALOG = r"Save As|Export|Save|Lưu"
    
    ID_MENU_REPORTS = "MainWindow_MenuItemReports"
    ID_MENU_REPORT_MANAGER = "MainWindow_MenuItemReportsManager"
    ID_TREE_REPORTS = "208"
    ID_BTN_VIEW_REPORT = "200"

    def __init__(self, session):
        self.session = session
        self.app = session.app
        self.main = session.main
        self.current_window: Optional[WindowSpecification] = None

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

    def open_efile_reports(self) -> str:
        """Main entry point to open reports and export client list."""
        self._navigate_to_report_manager()
        self._select_sample_client_report()
        self._view_report()
        self._handle_basic_search_conditions()
        # return None
        return self._export_to_csv()

    def _navigate_to_report_manager(self):
        """Navigates from Main Window to Report Manager."""
        log.info("Navigating to Report Manager...")
        
        # Click Reports Menu
        btn_reports = self.main.child_window(auto_id=self.ID_MENU_REPORTS, control_type="MenuItem")
        btn_reports.click_input()

        # Click Report Manager MenuItem
        report_manager_criteria = dict(
            title="Report Manager",
            auto_id=self.ID_MENU_REPORT_MANAGER,
            control_type="MenuItem",
        )
        
        for idx in range(3):
            try:
                mi = self.main.child_window(found_index=idx, **report_manager_criteria)
                mi.wait("exists enabled visible", timeout=5)
                mi.click_input()
                log.info(f"Clicked 'Report Manager' (index={idx})")
                break
            except Exception:
                continue
        else:
            raise RuntimeError("Failed to click 'Report Manager' menu item.")

        self._wait_for_window(self.TITLE_REPORT_MANAGER)

    def _select_sample_client_report(self):
        """Selects 'My Reports' -> 'Sample Client Report' in the tree view."""
        log.info("Selecting Sample Client Report...")
        if not self.current_window:
            raise RuntimeError("Report Manager window not active")
            
        self.current_window.set_focus()
        tree = self.current_window.child_window(auto_id=self.ID_TREE_REPORTS, control_type="Tree")
        tree.wait("visible enabled", timeout=60)
        
        my_reports = tree.child_window(title="My Reports", control_type="TreeItem")
        my_reports.wait("visible enabled", timeout=10)

        # Try UIA selection first
        try:
            try:
                my_reports.expand()
            except Exception:
                pass # Might already be expanded
            
            sample = my_reports.child_window(title="Sample Client Report", control_type="TreeItem")
            
            if not sample.exists():
                # Fallback: Expand via keyboard
                my_reports.click_input()
                my_reports.type_keys("{RIGHT}", set_foreground=False)
            
            sample.wait("visible", timeout=5)
            sample.click_input()
            log.info("Selected 'Sample Client Report' via UIA")
            return
        except Exception as e:
            log.warning(f"UIA selection failed: {e}. Trying keyboard fallback.")

        # Keyboard fallback
        my_reports.click_input()
        time.sleep(0.3)
        self.current_window.type_keys("{RIGHT}", set_foreground=False) # Expand
        time.sleep(0.5)
        self.current_window.type_keys("{DOWN}", set_foreground=False)  # Move down to item
        time.sleep(0.15)
        self.current_window.type_keys("{ENTER}", set_foreground=False) # Select
        log.info("Selected 'Sample Client Report' via Keyboard")

    def _view_report(self):
        """Clicks 'View Report' button."""
        log.info("Clicking View Report...")
        if not self.current_window:
            raise RuntimeError("Report Manager window not active")

        btn = self.current_window.child_window(title="View Report", auto_id=self.ID_BTN_VIEW_REPORT, control_type="Button")
        btn.wait("visible enabled", timeout=10)
        btn.click_input()
        
        time.sleep(0.5)
        
        # Handle potential confirmation dialogs or focus issues
        try:
            win = self._wait_for_window(self.TITLE_REPORT_MANAGER, timeout=5)
            win.set_focus()
            win.type_keys("{ENTER}", set_foreground=True)
        except Exception:
            pass

    def _handle_basic_search_conditions(self):
        """Handles the 'Basic Search Conditions' window."""
        log.info("Handling Basic Search Conditions...")
        try:
            win = self._wait_for_window(self.TITLE_BASIC_SEARCH, timeout=15)
            # print(win.print_control_identifiers())
            
            
            # Allow Test/Sample Returns checkbox
            # -----------------------------------
            time.sleep(0.5)
            win.set_focus()
            btn_all_test_return = win.child_window(auto_id="2014", control_type="CheckBox")
            if btn_all_test_return.get_toggle_state() != 1:
                btn_all_test_return.toggle()
            # -----------------------------------
                
            # return
            win.set_focus()
            win.type_keys("{ENTER}", set_foreground=True) # Press Continue/OK
            time.sleep(0.5)
        except TimeoutError:
            log.info("Basic Search Conditions window did not appear (skipped or timed out).")

    def _export_to_csv(self) -> str:
        """Handles the export process in Report Viewer."""
        log.info("Exporting report to CSV...")
        
        # 1. Wait for Report Viewer
        report_win = self._wait_for_window(self.TITLE_REPORT_VIEWER)
        
        # 2. Trigger Export (Ctrl+C seems to be the shortcut for CSV export in this context)
        report_win.set_focus()
        time.sleep(0.5)
        report_win.type_keys("^c", set_foreground=True) 
        
        # 3. Handle Save Dialog
        path = self._handle_save_dialog()
        
        # 4. Close any auto-opened viewer (Excel/Notepad)
        self._close_csv_viewer(path)
        
        # 4. Cleanup
        self.close()
        
        return path

    def _handle_save_dialog(self) -> str:
        """Finds save dialog, enters path, and saves."""
        log.info("Waiting for Save Dialog...")
        save_dlg = None
        
        # Retry loop to find dialog
        for _ in range(20): # 10 seconds
            hwnds = findwindows.find_windows(title_re=self.TITLE_SAVE_DIALOG)
            if hwnds:
                try:
                    save_dlg = self.app.window(handle=hwnds[0])
                except Exception:
                    save_dlg = Desktop(backend="uia").window(handle=hwnds[0])
                
                if save_dlg.exists():
                    break
            time.sleep(0.5)
            
        if save_dlg is None:
            raise TimeoutError("Save As / Export dialog not found")

        # Generate Path
        filename = f"Sample_Client_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = os.path.normpath(os.path.join(EXPORT_FOLDER, filename))
        
        # Enter Path
        try:
            # Try ComboBox first (common in Save As dialogs)
            combo = save_dlg.child_window(control_type="ComboBox")
            combo.wait("visible enabled", timeout=5)
            safe_set_edit_text(combo, path)
        except Exception:
            try:
                # Try Edit control
                edit = save_dlg.child_window(control_type="Edit")
                edit.wait("visible enabled", timeout=5)
                safe_set_edit_text(edit, path)
            except Exception:
                # Fallback to typing
                log.warning("Could not set text via UIA, typing path...")
                save_dlg.type_keys(path, with_spaces=True, set_foreground=False)

        time.sleep(0.2)
        
        # Click Save
        try:
            save_btn = save_dlg.child_window(title_re="Save|&Save|Lưu", control_type="Button")
            save_btn.click_input()
        except Exception:
            save_dlg.type_keys("{ENTER}", set_foreground=True)

        # Wait for file creation
        self._wait_for_file(path)
        return path

    def _wait_for_file(self, path: str, timeout: int = 30):
        """Waits for file to appear on disk."""
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(path):
                log.info(f"Export successful: {path}")
                return
            time.sleep(0.5)
        log.error(f"File not found after export: {path}")
    
    def _close_csv_viewer(self, file_path: str):
        """Closes the application window that might have auto-opened the CSV file."""
        filename = os.path.basename(file_path)
        # Excel often displays the filename without extension in the title bar.
        filename_stem = os.path.splitext(filename)[0]
        log.info(f"Checking for auto-opened viewer for: {filename} (stem: {filename_stem})")
        
        # Wait briefly for the window to appear
        time.sleep(2)
        
        # Escape filename stem for regex
        safe_name = re.escape(filename_stem)
        
        # Try to find and close the window
        # We try for a few seconds
        for _ in range(5):
            try:
                # Find windows with title containing the filename
                hwnds = findwindows.find_windows(title_re=f".*{safe_name}.*")
                
                for hwnd in hwnds:
                    try:
                        # Connect to window
                        win = Desktop(backend="uia").window(handle=hwnd)
                        title = win.window_text()
                        
                        # Safety check: Don't close Drake windows
                        if "Drake" in title and "Report" in title:
                            continue
                            
                        log.info(f"Found auto-opened window: '{title}'. Closing it...")
                        win.close()
                        return # Assume only one window opens
                    except Exception as e:
                        log.debug(f"Failed to close window handle {hwnd}: {e}")
            except Exception:
                pass
            time.sleep(0.5)
        
        log.info("No auto-opened viewer window found.")

    def close(self):
        """Closes Report Viewer and Report Manager to return to Main Window."""
        log.info("Closing reports and returning to main menu...")
        
        # Close Report Viewer
        try:
            win = self._wait_for_window(self.TITLE_REPORT_VIEWER, timeout=5)
            win.type_keys("{ESC}", set_foreground=True)
        except TimeoutError:
            pass # Already closed

        # Close Report Manager
        try:
            win = self._wait_for_window(self.TITLE_REPORT_MANAGER, timeout=5)
            win.type_keys("{ESC}", set_foreground=True)
            time.sleep(0.5)

            # Check again if Report Manager is still visible, send ESC again
            try:
                if win.exists(timeout=1):
                    win.type_keys("{ESC}", set_foreground=True)
            except Exception:
                pass
        except TimeoutError:
            pass # Already closed

        # Verify Main Window
        try:
            self.main.wait("visible enabled ready", timeout=10)
            log.info("✓ Returned to Main Window")
        except Exception:
            log.warning("Main Window not active after closing reports")
