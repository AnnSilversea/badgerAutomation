from DrakeAutomation.ui.control import (
    edit_text,
    select_combobox,
    select_checkbox,
    fill_table,
    fill_box14,
    clear_control_cache,
    get_control,
)
from DrakeAutomation.ui.waits import safe_wait
from DrakeAutomation.ui.logger import setup_logger
from pywinauto.application import WindowSpecification
from typing import List, Tuple

log = setup_logger("ssa_1099_entrys.1099-SSA")

SSA1099_HEADER = {
    "TS": {
        "auto_id": "Dropdown_1",
        "control_type": "ComboBox"
    },
    "F": {
        "auto_id": "Textbox_2",
        "control_type": "Edit"
    },
    "ST": {
        "auto_id": "Dropdown_3",
        "control_type": "ComboBox"
    }
}

SSA1099_BOXES = {
    "benefits": {
        "auto_id": "Textbox_4",
        "control_type": "Edit"
    },
    "medicare_premiums": {
        "auto_id": "Textbox_5",
        "control_type": "Edit"
    },
    "federal_withheld": {
        "auto_id": "Textbox_7",
        "control_type": "Edit"
    }
}

SSA1099_CHECKBOXES = {
    "treat_medicare_as_sehi": {
        "auto_id": "CheckboxTextRight_6",
        "control_type": "CheckBox"
    },
    "treaty_country_resident": {
        "auto_id": "CheckboxTextRight_9",
        "control_type": "CheckBox"
    }
}

SSA1099_STATE = {
    "designate_benefit_type": {
        "auto_id": "Dropdown_8",
        "control_type": "ComboBox"
    }
}

def v(fields, key, default=None):
    """Extract value from nested structure with .get("value")"""
    if not isinstance(fields, dict):
        return default
    val = fields.get(key, default)
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val

class SSA1099ListPage:
    def __init__(self, win: WindowSpecification, form_count: int=0):
        self.win = win
        self.is_list_mode = False
        self.grid = None
        self.btn_next = None
        
        # Optimization: Check window title first
        if form_count > 1:
            log.info(f"[OK] SSA-1099 is in LIST mode (detected by form count: {form_count})")
            self.is_list_mode = True
            self.grid = win.child_window(title_re="Existing Forms List - SSA: SSA-1099, Social Security", control_type="Window")\
                .child_window(auto_id="MultiInstanceColumnView", control_type="Custom")\
                    .child_window(auto_id="MultiInstanceDataGrid", control_type="DataGrid")
            
            log.info("[OK] SSA-1099 is in LIST mode (detected by form count)")    
        
        if form_count <=1:
            try:
                self.btn_next = win.child_window(auto_id="mnuIcon_Next", control_type="MenuItem")
            except:
                pass

    def wait_loaded(self, timeout=30):
        if self.is_list_mode:
            safe_wait(lambda: self.grid.exists() and self.grid.is_visible(), timeout=timeout, desc="SSA-1099 list grid ready")
            log.info("SSA-1099 list page ready")
        else:
            log.info("SSA-1099 detail form ready")
    
    def next_record(self) -> bool:
        """
        In detail mode, click Next button to create new record.
        Returns True if successful, False if button not found.
        """
        # Try to find and click the Next MenuItem
        try:
            # Look for the Next MenuItem in the menu
            next_item = self.win.child_window(
                auto_id="mnuIcon_Next",
                control_type="MenuItem"
            )
            if next_item.exists():
                log.info("Clicking 'Next' MenuItem to navigate to new record...")
                # next_item.click_input()
                next_item.invoke()
                log.info("[OK] Navigated to next record")
                return True
            else:
                log.warning("Next MenuItem not found")
                return False
        except Exception as e:
            log.warning(f"Failed to click Next: {e}")
            return False

    def rows(self):
        return self.grid.children(control_type="DataItem") if self.is_list_mode else []

    def row_count(self) -> int:
        """Get total number of rows (LIST MODE only)"""
        if not self.is_list_mode:
            return 0
        return len(self.rows())
    
    def select_row(self, index: int):
        """Select a row by index"""
        rows = self.rows()
        if index >= len(rows):
            raise IndexError(f"Row index {index} out of range")

        row = rows[index]
        row.click_input()
        log.info(f"Selected row {index + 1}")
        
    def open_detail(self, index: int):
        """Opens the detail view for a given row index."""
        if not self.is_list_mode:
            log.info("Already in detail view (0-1 record mode).")
            return
        
        rows = self.rows()
        if index >= len(rows):
            raise IndexError(f"Row index {index} out of range")

        # Ensure the row is focused and selected before action
        row = rows[index]
        row.set_focus()
        row.double_click_input()
        log.info(f"Double-clicked row {index + 1}")

        # Wait for detail view
        try:
            safe_wait(
                lambda: self.win.child_window(auto_id=SSA1099_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=3,
                desc="Wait for SSA-1099 detail view"
            )
        except Exception:
            log.warning("Double click might have failed. Retrying with ENTER key...")
            row.set_focus()
            row.type_keys("{ENTER}")
            # Wait again with longer timeout
            safe_wait(
                lambda: self.win.child_window(auto_id=SSA1099_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=10,
                desc="Wait for SSA-1099 detail view (retry)"
            )
        
        log.info(f"Opened detail for row {index + 1}")

    def get_row_text(self, row, col_index):
        try:
            children = row.children()
            if col_index < len(children):
                ctrl = children[col_index]
                return ctrl.children()[0].window_text() if ctrl.children() else ctrl.window_text()
        except:
            pass
        return ""

    def get_current_ts(self) -> str:
        """
        Get the TS (Tax Status) value from the current form (DETAIL MODE).
        Returns only the selected value (e.g., 'T'), not the full dropdown content.
        """
        try:
            ts_field = self.win.child_window(
                auto_id=SSA1099_HEADER["TS"]["auto_id"],
                control_type=SSA1099_HEADER["TS"]["control_type"]
            )
            if ts_field.exists():
                selected = ts_field.selected_text()
                if selected:
                    value = selected.strip()
                    if value.startswith('['):
                        value = value[1:]
                    if ',' in value:
                        value = value.split(',')[0]
                    value = value.strip()
                    log.debug(f"Current TS in form: '{value}'")
                    return value
        except Exception as e:
            log.debug(f"Could not read TS from form: {e}")
        return ""

    def check_ts_exists(self, ts: str) -> bool:
        target_ts = str(ts).strip().upper()
        log.info(f"Checking for existing SSA-1099: Target TS='{target_ts}'")
        
        if not target_ts:
            log.warning("No TS provided in data, cannot check for duplicates.")
            return None

        if self.is_list_mode:
            for i, row in enumerate(self.rows()):
                row_ts = self.get_row_text(row, 1).strip().upper()
                log.info(f"  Row {i+1}: Grid TS='{row_ts}'")
                if row_ts == target_ts:
                    log.info(f"  [MATCH] Found existing record at row {i+1}")
                    return i
            log.info("  [NO MATCH] No existing record found in grid")
        else:
            curr_ts = self.get_current_ts()
            log.info(f"  Detail View: Current TS='{curr_ts}'")
            
            if not curr_ts:
                log.info("  [EMPTY] Current form is empty")
                return None

            if curr_ts == target_ts:
                log.info("  [MATCH] Found existing record in detail view")
                return 0
            
            log.info("  [NO MATCH] Current record does not match")
        
        return None

    def check_record_exists(self, data: dict) -> bool:
        if not data:
            return False
        fields = data.get("fields", {})
        ts = v(fields, "TS")
        return self.check_ts_exists(ts)

    def create_new_record(self):
        if self.is_list_mode:
            log.info("Creating new SSA-1099 record (List Mode)")
            self.grid.set_focus()
            self.grid.type_keys("^{END}")
            self.grid.type_keys("{ENTER}")
            # Wait for detail view
            safe_wait(
                lambda: self.win.child_window(auto_id=SSA1099_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=10,
                desc="Wait for new SSA-1099 detail view"
            )
        else:
            log.info("Creating new SSA-1099 record (Detail Mode)")
            self.next_record()

    def add_if_not_exists(self, data):
        idx = self.check_record_exists(data)
        if idx is not None:
            log.info(f"Record already exists at index {idx}. Opening it for update.")
            if self.is_list_mode:
                # self.open_detail(idx)
                return idx
            else:
                log.info("Already in detail view for the existing record.")
            return idx
        
        # Record does not exist, create a new one.
        log.info("Record does not exist. Creating new.")
        if not self.is_list_mode:
            curr_ts = self.get_current_ts()
            if not curr_ts:
                log.info("Current form is empty, using it.")
                return None
            
        # self.create_new_record()
        return None
    
    def classify_extract_data(self, list_data: List) -> Tuple[List, List]:
        self.lst_exist = []
        self.lst_new = []
        for idx, data in enumerate(list_data):
            grid_idx = self.add_if_not_exists(data)
            if grid_idx is not None:
                self.lst_exist.append([grid_idx, data])
            else:
                self.lst_new.append(data)

        log.info(f"      [DETECT] - Exist records: {len(self.lst_exist)} - New records: {len(self.lst_new)}")
        for idx, _ in self.lst_exist:
            log.info(f"      [DETECT] - Exist record at index {idx}")
        
        return self.lst_exist, self.lst_new   

def fill_ssa_1099(ssa_1099_entry, data=None):
    if data is None:
        log.warning("No data provided for fill_ssa_1099")
        return
    log.info("==== START FILL 1099-SSA ====")
    fields = data.get("fields", {})

    # Optimization: Check if we're in Existing Forms List (faster than findwindows)
    if "Existing Forms List" in ssa_1099_entry.window_text():
        log.warning("Window 'Existing Forms List' detected. Aborting fill.")
        return

    clear_control_cache()

    def fill_or_clear(ctrl, value):
        if value:
            if ctrl["control_type"] == "Edit":
                edit_text(ssa_1099_entry, ctrl, value)
            elif ctrl["control_type"] == "ComboBox":
                select_combobox(ssa_1099_entry, ctrl, value)
        else:
            try:
                c = get_control(ssa_1099_entry, ctrl["auto_id"], ctrl["control_type"])
                c.set_focus()
                if ctrl["control_type"] == "Edit":
                    c.set_text("")
                elif ctrl["control_type"] == "ComboBox":
                    try:
                        c.child_window(control_type="Edit").set_text("")
                    except Exception:
                        c.type_keys("{DEL}")
            except Exception:
                pass

    # Header
    log.info("Header")
    fill_or_clear(SSA1099_HEADER["TS"], v(fields, "TS"))
    fill_or_clear(SSA1099_HEADER["F"], v(fields, "F"))
    fill_or_clear(SSA1099_HEADER["ST"], v(fields, "ST"))

    # Boxes
    log.info("Boxes")
    boxes = v(fields, "Entries", {})
    
    val_benefits = v(boxes, "box5")
    val_medicare = v(boxes, "medicare_premiums")
    val_federal = v(boxes, "box6")
    
    log.debug(f"Filling Boxes: benefits={val_benefits}, medicare={val_medicare}, federal={val_federal}")
    fill_or_clear(SSA1099_BOXES["benefits"], val_benefits)
    fill_or_clear(SSA1099_BOXES["medicare_premiums"], val_medicare)
    fill_or_clear(SSA1099_BOXES["federal_withheld"], val_federal)

    # Checkboxes
    # select_checkbox(ssa_1099_entry, SSA1099_CHECKBOXES["treat_medicare_as_sehi"], data["sehi"])
    # select_checkbox(ssa_1099_entry, SSA1099_CHECKBOXES["treaty_country_resident"], data["treaty"])

    # State
    log.info("State Info")
    fill_or_clear(SSA1099_STATE["designate_benefit_type"], v(fields, "designate_benefit_type"))
    
    log.info("==== END FILL 1099-SSA ====")
