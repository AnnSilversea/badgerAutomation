# flows/client.py
import warnings
import time

warnings.filterwarnings("ignore", category=RuntimeWarning, module="pywinauto.controls.uiawrapper")

class ClientFlow:
    def __init__(self, session):
        self.app = session.app
        self.main = session.main # Main Drake window

    def open_dialog(self):
        """Open client search dialog with Ctrl+O"""
        # Check if already open
        try:
            self._get_dialog(timeout=1)
            return
        except Exception:
            pass

        for _ in range(3):
            self.main.set_focus()
            time.sleep(1)
            self.main.type_keys("^o", set_foreground=True)
            try:
                self._get_dialog(timeout=5)
                return
            except Exception:
                pass
        
        raise RuntimeError("Failed to open 'Open / Create' dialog")

    def _get_dialog(self, timeout=15):
        """Find and return the 'Open/Create' dialog window."""
        dialog = self.main.child_window(auto_id="FileOpenCreateWindow_Window", control_type="Window")
        dialog.wait("visible", timeout=timeout)
        return dialog

    def search(self, client_id):
        """Search for client by ID in the dialog"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                dialog = self._get_dialog()
                box = dialog.child_window(
                    auto_id="ClearableWatermarkTextbox_TextBoxInput",
                    control_type="Edit"
                ).wait("ready", timeout=10)
                box.set_focus()
                box.type_keys("^a{DELETE}", set_foreground=False)
                box.type_keys(client_id, with_spaces=True, set_foreground=False)
                time.sleep(1)
                return
            except Exception as e:
                # On the last attempt, re-raise the exception
                if attempt < max_retries - 1:
                    continue
                raise

    def open_by_last4(self, client_id):
        """Selects and opens a client from the search results grid."""
        last4 = client_id[-4:]
        dialog = self._get_dialog()
        grid = dialog.child_window(
            auto_id="ClientSelectionUC_DataGridSearchResultsClients",
            control_type="DataGrid"
        )
        grid.wait("ready", timeout=10)
        
        for row in grid.children(control_type="DataItem"):
            if any(t.window_text().endswith(last4)
                   for t in row.descendants(control_type="Text")):
                # row.click_input()
                time.sleep(0.5)
                dialog.type_keys("{ENTER}")
                
                time.sleep(1)
                from pywinauto import findwindows
                reminders  = findwindows.find_windows(title_re =r"Drake \d{4} - Data Entry")
                if reminders:
                    reminder = self.app.window(handle=reminders[0])
                    reminder.set_focus()
                    if reminder.child_window(title="Continue", control_type="Button").exists():
                        reminder.set_focus()
                        reminder.type_keys("{ENTER}")
                        time.sleep(1)
                return True
        return False

    def close_dialog(self):
        """Close the search dialog"""
        try:
            self._get_dialog(timeout=2).close()
        except Exception:
            pass
