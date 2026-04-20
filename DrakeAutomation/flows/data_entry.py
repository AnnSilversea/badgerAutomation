# flows/data_entry.py
import time
import re
from DrakeAutomation.ui.logger import setup_logger
from DrakeAutomation.ui.waits import wait_form
from DrakeAutomation.forms.w2 import W2ListPage, W2_HEADER
from DrakeAutomation.forms.R1099 import R1099ListPage, R1099_HEADER
from DrakeAutomation.forms.SSA1099 import SSA1099ListPage, SSA1099_HEADER
from DrakeAutomation.forms.DIV1099 import Div1099ListPage, DIV_1099_HEADER
from DrakeAutomation.forms.INT1099 import Int1099ListPage, INT_1099_HEADER

from pywinauto import Desktop, findwindows, WindowSpecification

log = setup_logger("flows.data_entry")


class DataEntryFlow:
    def __init__(self, session):
        self.app = session.app
        self.main = session.main
        
    def _wait_for_window(self, title_re: str, timeout: int = 60) -> WindowSpecification:
        """Waits for a window matching the title regex and sets it as current."""
        end = time.time() + timeout
        while time.time() < end:
            hwnds = findwindows.find_windows(title_re=r"Drake \d{4} - Data Entry", top_level_only=True)
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
        

    def get_form_count(self, form_type: str):
        """
        Checks the number of instances of a specific form in the Data Entry window
        without opening the form.
        """
        main_entry_window = self._wait_for_window("Drake \d{4} - Data Entry")
        main_entry_window.set_focus()
        menu_tab = main_entry_window.child_window(auto_id="menuTabControl", control_type="Tab")
        menu_tab.wait('ready', timeout=10)
        
        if form_type == "W2":
            window_text = menu_tab.child_window(auto_id="LINK_0_Col0_Sel10", control_type="Button").window_text()
        elif form_type == "1099":
            window_text = menu_tab.child_window(auto_id="LINK_0_Col0_Sel12", control_type="Button").window_text()
        elif form_type == "SSA":
            window_text = menu_tab.child_window(auto_id="LINK_0_Col0_Sel18", control_type="Button").window_text()
        else:    
            return 0
        match = re.search(r"\((\d+)\)", window_text)
        if match:
            number = int(match.group(1))
            log.info(f"Found {number} instances of {form_type} -> List MODE")
            return number
        log.info(f"Found 0-1 instances of {form_type} -> Detail MODE")
        return 0
        
        
        

def _get_row_text(row, col_index):
    """Extract text from a specific column in a row (DataItem)"""
    try:
        children = row.children()
        if col_index < len(children):
            ctrl = children[col_index]
            if ctrl.children():
                return ctrl.children()[0].window_text()
            return ctrl.window_text()
    except Exception:
        pass
    return ""

def _parse_ts_value(text):
    """Parse TS/TSJ value from combobox text (e.g. 'T, T Belongs...' -> 'T')"""
    if not text: return ""
    value = text.strip()
    if value.startswith('['): value = value[1:]
    if ',' in value: value = value.split(',')[0]
    return value.strip().upper()

def get_form_counts(session, main_entry_window, cleint_id=None):
    """
    Opens supported forms to count records by TS (T, S) or TSJ (T, S, J).

    Args:
        session: The current automation session object.
        main_entry_window: The pywinauto window wrapper for the main data entry screen.

    Returns:
        A dictionary with form names as keys and a dictionary of counts as values.
        Example: {'W-2': {'T': 2, 'S': 1}, '1099-INT': {'T': 1, 'S': 0, 'J': 1}}
    """
    log.info("Counting existing forms with TS/TSJ breakdown...")
    
    # Configuration for forms to check
    # Type: "TS" (T, S) or "TSJ" (T, S, J)
    form_config = {
        "W-2":      {"prefix": "W2",   "code": "W2",   "type": "TS",  "header": W2_HEADER,       "key": "TS",  "grid": {"TS": 1, "Name": 2}, "detail": {"TS": "Dropdown_1", "Name": "Textbox_5", "ID": "Textbox_4"}},
        "1099-R":   {"prefix": "1099", "code": "1099", "type": "TS",  "header": R1099_HEADER,    "key": "TS",  "grid": {"TS": 1, "Name": 3}, "detail": {"TS": "Dropdown_1", "Name": "Textbox_6", "ID": "Textbox_5"}},
        "SSA-1099": {"prefix": "SSA",  "code": "SSA",  "type": "TS",  "header": SSA1099_HEADER,  "key": "TS",  "grid": {"TS": 1}, "detail": {"TS": "Dropdown_1"}},
        "1099-DIV": {"prefix": "DIV",  "code": "DIV",  "type": "TSJ", "header": DIV_1099_HEADER, "key": "TSJ", "grid": {"TSJ": 1, "ID": 2, "Name": 3}, "detail": {"TSJ": "Dropdown_1", "ID": "Textbox_6", "Name": "Textbox_8"}},
        "1099-INT": {"prefix": "INT",  "code": "INT",  "type": "TSJ", "header": INT_1099_HEADER, "key": "TSJ", "grid": {"TSJ": 1, "ID": 2, "Name": 3}, "detail": {"TSJ": "Dropdown_1", "ID": "Textbox_7", "Name": "Textbox_9"}},
    }
    
    forms_found = []

    try:
        menu_tab = main_entry_window.child_window(auto_id="menuTabControl", control_type="Tab")
        menu_tab.wait('ready', timeout=10)
        
        # Get all button texts once to identify which forms are present
        buttons_text = [btn.window_text() for btn in menu_tab.descendants(control_type="Button")]
        
        for form_name, config in form_config.items():
            if any(t.startswith(config["prefix"]) for t in buttons_text):
                forms_found.append(form_name)
                
    except Exception as e:
        log.error(f"Error scanning form list: {e}")
        return {}

    results = {}

    for form_name in forms_found:
        config = form_config[form_name]
        records = []
        log.info(f"Inspecting {form_name} for existing records...")
        
        try:
            # Open form
            main_entry_window.set_focus()
            main_entry_window.type_keys(f"{config['code']}{{ENTER}}")
            
            # Wait for form window
            form_win = wait_form(session.app, form_name, cleint_id, timeout=10)
            
            # Check for List Mode (Grid)
            # Determine Grid ID based on form type
            grid_id = "MultiInstanceDataGrid"
            if config["code"] in ["DIV", "INT"]:
                grid_id = "MacrosWindow_Macros"
            
            grid = form_win.child_window(auto_id=grid_id, control_type="DataGrid")

            if grid.exists(timeout=2) and grid.is_visible():
                # List Mode: Iterate rows
                rows = grid.children(control_type="DataItem")
                for row in rows:
                    try:
                        rec = {}
                        for field, col_idx in config["grid"].items():
                            val = _get_row_text(row, col_idx).strip()
                            if field in ["TS", "TSJ"]: val = val.upper()
                            rec[field] = val
                        
                        # Filter out "New Record" placeholder rows
                        ts_val = rec.get("TS") or rec.get("TSJ")
                        if ts_val and "NEW RECORD" in ts_val:
                            continue

                        if any(rec.values()):
                            records.append(rec)
                    except Exception:
                        pass
            else:
                # Detail Mode (Single Record): Read Dropdown_1
                try:
                    rec = {}
                    for field, auto_id in config["detail"].items():
                        val = ""
                        if field in ["TS", "TSJ"]:
                            combo = form_win.child_window(auto_id=auto_id, control_type="ComboBox")
                            if combo.exists(timeout=1):
                                for _ in range(3):
                                    txt = combo.selected_text()
                                    if txt:
                                        val = _parse_ts_value(txt)
                                        break
                                    time.sleep(0.3)
                        else:
                            edit = form_win.child_window(auto_id=auto_id, control_type="Edit")
                            if edit.exists(timeout=0.5):
                                val = edit.window_text().strip()
                        rec[field] = val
                    
                    # Check if valid record (must have TS/TSJ)
                    ts_key = "TS" if "TS" in rec else "TSJ"
                    if rec.get(ts_key):
                        records.append(rec)
                except Exception:
                    pass

            results[form_name] = records
            
            # Close form
            form_win.set_focus()
            form_win.type_keys("{ESC}")
            main_entry_window.wait('active', timeout=10)
            
        except Exception as e:
            log.error(f"Error processing {form_name}: {e}")
            # Attempt to return to main screen
            try:
                if session.app.top_window().handle != main_entry_window.handle:
                    session.app.top_window().close()
                main_entry_window.set_focus()
            except:
                pass
    
    return results
