from pywinauto import findwindows
from DrakeAutomation.ui.control import (
    edit_text,
    select_combobox,
    fill_box12,
    fill_table,
    fill_box14,
    clear_control_cache,
    get_control,
)
from DrakeAutomation.ui.waits import safe_wait
from DrakeAutomation.ui.logger import setup_logger
from pywinauto.application import WindowSpecification
from typing import List, Tuple

log = setup_logger("forms.w2")

def v(fields, key, default=None):
    """Extract value from nested structure with .get("value")"""
    if not isinstance(fields, dict):
        return default
    val = fields.get(key, default)
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val

class W2ListPage:
    """
    Represents the W2 form window in 2 modes:
    - LIST MODE (2+ records): DataGrid "Existing Forms List - W2: Wages"
    - DETAIL MODE (0-1 record): Direct W2 form without grid
    """
    def __init__(self, win: WindowSpecification, form_count: int=0):
        self.win = win
        # self.win.print_control_identifiers()
        self.is_list_mode = False
        self.grid = None
        
        if form_count > 1:
            log.info(f"[OK] W2 is in LIST mode (detected by form count: {form_count})")
            self.is_list_mode = True
            self.grid = win.child_window(title="Existing Forms List - W2: Wages ", control_type="Window")\
                .child_window(auto_id="MultiInstanceColumnView", control_type="Custom")\
                    .child_window(auto_id="MultiInstanceDataGrid", control_type="DataGrid")
                    
            log.info("[OK] W2 is in LIST mode (detected by form count)")
                
        # If not list mode, try to find Next button (DETAIL MODE with 0-1 record)
        if form_count <=1:
            try:
                # Next is a MenuItem in the toolbar menu, not a Button
                self.btn_next = win.child_window(
                    auto_id="mnuIcon_Next",
                    control_type="MenuItem"
                )
                if self.btn_next.exists():
                    log.info("[OK] W2 is in DETAIL mode (0-1 record with Next MenuItem)")
            except:
                pass
            
    # --------------------------------------------------
    # waits & mode helpers
    # --------------------------------------------------
    def wait_loaded(self, timeout=30):
        """
        Wait for W2 form/grid to be loaded and ready.
        LIST MODE: Wait for DataGrid to be visible (2+ records)
        DETAIL MODE: Form is immediately ready (0-1 record)
        """
        if self.is_list_mode:
            # In list mode (2+ records), wait for grid to be visible
            def _ready():
                return self.grid.exists() and self.grid.is_visible()

            safe_wait(
                _ready,
                timeout=timeout,
                desc="W2 list grid ready"
            )
            log.info("W2 list page ready (2+ records)")
        else:
            # In detail mode (0-1 record), form is already displayed
            log.info("W2 detail form ready (0-1 record)")

    def is_in_list_mode(self) -> bool:
        """Check if W2 is in list mode (2+ records)"""
        return self.is_list_mode

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

    # --------------------------------------------------
    # grid helpers
    # --------------------------------------------------
    def rows(self):
        """Get all rows in the grid (LIST MODE only)"""
        if not self.is_list_mode:
            return []
        return self.grid.children(control_type="DataItem")

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
                lambda: self.win.child_window(auto_id=W2_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=3,
                desc="Wait for W2 detail view"
            )
        except Exception:
            log.warning("Double click might have failed. Retrying with ENTER key...")
            row.set_focus()
            row.type_keys("{ENTER}")
            # Wait again with longer timeout
            safe_wait(
                lambda: self.win.child_window(auto_id=W2_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=10,
                desc="Wait for W2 detail view (retry)"
            )
        
        log.info(f"Opened detail for row {index + 1}")

    def delete_row(self, index: int):
        """Delete a row by index"""
        self.select_row(index)
        
        if self.btn_delete:
            log.info(f"Deleting row {index + 1} using Delete button")
            self.btn_delete.click_input()
        else:
            log.info(f"Deleting row {index + 1} using keyboard shortcut")
            self.grid.set_focus()
            self.grid.type_keys("{DELETE}")

    # --------------------------------------------------
    # row text extraction
    # --------------------------------------------------
    def get_row_text(self, row, col_index):
        """Extract text from a specific column in a row"""
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

    # --------------------------------------------------
    # TS and employer info check
    # --------------------------------------------------
    def find_record_index(self, employer_name: str, ts: str) -> int | None:
        """
        Finds a record by Employer Name and TS.
        - In LIST mode, returns the row index if found, else None.
        - In DETAIL mode, returns 0 if the current form matches, else None.
        """
        target_ts = str(ts or "").strip().upper()
        target_name = str(employer_name or "").strip().upper()

        if not target_name or not target_ts:
            log.warning("No TS and Employer Name provided, cannot check for duplicates.")
            return None

        log.info(f"Checking for existing W2: Target TS='{target_ts}', Target Name='{target_name}'")

        if self.is_list_mode:
            # W2 grid columns: # (0), TS (1), Employer Name (2)
            for i, row in enumerate(self.rows()):
                row_ts = self.get_row_text(row, 1).strip().upper()
                row_name = self.get_row_text(row, 2).strip().upper()
                
                log.info(f"  Row {i+1}: Grid TS='{row_ts}', Name='{row_name}'")
                
                if row_ts == target_ts and row_name == target_name:
                    log.info(f"  [MATCH] Found existing record at row index {i}")
                    return i
            log.info("  [NO MATCH] No existing record found in grid")
        else:
            # DETAIL MODE
            curr_ts = self.get_current_ts().upper()
            curr_name = self.get_current_employer_name().upper()

            log.info(f"  Detail View: Current TS='{curr_ts}', Name='{curr_name}'")

            # If the form is empty, there's no record.
            if not curr_name and not curr_ts:
                log.info("  [EMPTY] Current form is empty")
                return None

            if curr_ts == target_ts and curr_name == target_name:
                log.info("  [MATCH] Found existing record in detail view")
                return 0
            
            log.info("  [NO MATCH] Current record does not match")
        
        return None

    def get_current_employer_name(self) -> str:
        """
        Get the employer name from the current form (DETAIL MODE).
        Returns empty string if not found.
        """
        try:
            employer_name_field = self.win.child_window(
                auto_id="Textbox_5",
                control_type="Edit"
            )
            if employer_name_field.exists():
                name = employer_name_field.get_value()
                log.debug(f"Current employer in form: '{name}'")
                return name.strip() if name else ""
        except Exception as e:
            log.debug(f"Could not read employer name from form: {e}")
        return ""
    
    def get_current_ts(self) -> str:
        """
        Get the TS (Tax Status) value from the current form (DETAIL MODE).
        Returns only the selected value (e.g., 'T'), not the full dropdown content.
        """
        try:
            ts_field = self.win.child_window(
                auto_id="Dropdown_1",
                control_type="ComboBox"
            )
            if ts_field.exists():
                # Get the selected text and extract only the first part (before the comma or space)
                selected = ts_field.selected_text()
                if selected:
                    # Extract first element if it's a list representation like "[T, T  Belongs to the Primary Taxpayer ]"
                    # Split by comma and take the first part, then strip brackets and spaces
                    value = selected.strip()
                    if value.startswith('['):
                        value = value[1:]  # Remove leading [
                    if ',' in value:
                        value = value.split(',')[0]  # Take first part
                    value = value.strip()
                    log.debug(f"Current TS in form: '{value}'")
                    return value
        except Exception as e:
            log.debug(f"Could not read TS from form: {e}")
        return ""

    def check_record_exists(self, data: dict) -> int | None:
        """
        Extracts key fields from data and checks if the record exists.
        Returns the index if found, otherwise None.
        """
        if not data:
            return None
        fields = data.get("fields", {})
        employer = v(fields, "Employer", {})
        employer_name = v(employer, "Name")
        ts = v(fields, "TS")
        return self.find_record_index(employer_name, ts)

    # --------------------------------------------------
    # record creation
    # --------------------------------------------------
    def create_new_record(self):
        """
        Create a new W2 form record.
        
        LIST MODE (2+ records): Navigate to end of grid and press Enter.
        DETAIL MODE (0-1 record): Click Next button.
        """
        if self.is_list_mode:
            # In list mode (2+ records): navigate to end and press Enter to create new record
            log.info("Creating new W2 record in list mode")
            self.grid.set_focus()
            self.grid.type_keys("^{END}")
            self.grid.type_keys("{ENTER}")
            log.info("New W2 record ready for input")
            safe_wait(
                lambda: self.win.child_window(auto_id=W2_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=10,
                desc="Wait for new W-2 detail view"
            )
        else:
            # In detail mode (0-1 record): use Next button to create new record
            log.info("Creating new W2 record in detail mode")
            self.next_record()

    def add_if_not_exists(self, data: dict):
        """
        Check if W2 record exists. If not, create a new one.
        Handles both LIST mode (2+ records) and DETAIL mode (0-1 record).
        
        Args:
            data: Dictionary with W2 data.
            
        Returns:
            True if a form is ready to be filled (either existing and opened, or new).
        """
        idx = self.check_record_exists(data)

        if idx is not None:
            log.info(f"Record already exists at index {idx}. Opening it for update.")
            if self.is_list_mode:
                # self.open_detail(idx)
                return idx
            else:
                # In detail mode, idx is 0, and we are already on the correct form.
                log.info("Already in detail view for the existing record.")
            return idx

        # Record does not exist, so create a new one.
        log.info("Record does not exist. Creating new.")
        
        # In detail mode, if the current form is empty, we can just use it.
        # Otherwise, we need to click "Next".
        if not self.is_list_mode:
            current_employer = self.get_current_employer_name()
            current_ts = self.get_current_ts()
            if not current_employer and not current_ts:
                log.info("Current form is empty, using it for the new record.")
                return None

        # This handles both creating a new record in list mode,
        # and clicking "Next" in detail mode if the form is not empty.
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

W2_HEADER = {
    # TS:
    # S, S  Belongs to the Spouse of the Primary Taxpayer
    # T, T  Belongs to the Primary Taxpayer
    "TS": {
        "auto_id": "Dropdown_1",
        "control_type": "ComboBox"
    },
    
    "F": {
        "auto_id": "Textbox_2",
        "control_type": "Edit"
    },
    
    # Special tax treatment: 1,2,3,4,5,6,7,8,9,A,C,F,G,H,I,M,N,O,P,Q,R,S,T,V,W,X,Y,Z,E,@
    "Special tax treatment":{
        "auto_id": "Dropdown_3",
        "control_type": "ComboBox"
    },
}

STATE_INFORMATION_GROUP = {
    "IN":{
        "auto_id":"Label_108", 
        "control_type":"Button"
    }, 
    "NJ":{
        "auto_id":"Label_109", 
        "control_type":"Button"
    },
    "ND":{
        "auto_id":"Label_117", 
        "control_type":"Button"
    },
    "NY":{
        "auto_id":"Label_114", 
        "control_type":"Button"
    },
    "PA":{
        "auto_id":"Label_110", 
        "control_type":"Button"
    },
}


EMPLOYER_INFO = {
    "EIN":{
        "auto_id": "Textbox_4",
        "control_type": "Edit"
    },
    "Name":{
        "auto_id": "Textbox_5",
        "control_type": "Edit"
    },
    "Name cont":{
        "auto_id": "Textbox_6",
        "control_type": "Edit"
    },
    "Street":{
        "auto_id": "Textbox_7",
        "control_type": "Edit"
    },
    "City":{
        "auto_id": "Textbox_8",
        "control_type": "Edit"
    },
    
    # U.S.ONLY
    "State":{
        "auto_id": "Dropdown_9",
        "control_type": "ComboBox"
    },
    "ZIP":{
        "auto_id": "Textbox_10", 
        "control_type": "Edit"
    },
    
    
    # Foreign ONLY
    
    "Province/state":{
        "auto_id": "Textbox_11",
        "control_type": "ComboBox"
    },
    
    "Country":{
        "auto_id": "Dropdown_12",
        "control_type": "ComboBox"
    },
    
    "Postal code":{
        "auto_id": "Textbox_13",
        "control_type": "Edit"
    },

}

EMPLOYEE_OVERRIDE = {
    # Name
    "First Name":{
        "auto_id": "TextboxOverride_14",
        "control_type": "Edit"
    },
    "Last Name":{
        "auto_id": "TextboxOverride_15",
        "control_type": "Edit"
    },
    "Street":{
        "auto_id": "TextboxOverride_16",
        "control_type": "Edit"
    },
    "City":{
        "auto_id": "TextboxOverride_17",
        "control_type": "Edit"
    },
    
    # U.S.ONLY
    "State":{
        "auto_id": "DropdownOverride_18",
        "control_type": "Edit"
    },
    "ZIP":{
        "auto_id": "TextboxOverride_19",
        "control_type": "Edit"
    },
    
    # Foreign ONLY
    
    "Province/state":{
        "auto_id": "TextboxOverride_20",
        "control_type": "ComboBox"
    },
    
    "Country":{
        "auto_id": "DropdownOverride_21",
        "control_type": "ComboBox"
    },
    
    "Postal code":{
        "auto_id": "TextboxOverride_22",
        "control_type": "Edit"
    },

}

BOX_1_TO_11 = {
    # box1
    "box1":{
        "auto_id": "Textbox_23",
        "control_type": "Edit"
    },
    # box2
    "box2":{
        "auto_id": "Textbox_24",
        "control_type": "Edit"
    },
    # box3
    "box3":{
        "auto_id": "Textbox_25",
        "control_type": "Edit"
    },
    # box4
    "box4":{
        "auto_id": "Textbox_26",
        "control_type": "Edit"
    },
    # box5
    "box5":{
        "auto_id": "Textbox_27",
        "control_type": "Edit"
    },
    # box6
    "box6":{
        "auto_id": "Textbox_28",
        "control_type": "Edit"
    },
    # box7
    "box7":{
        "auto_id": "Textbox_29",
        "control_type": "Edit"
    },
    # box8
    "box8":{
        "auto_id": "Textbox_30",
        "control_type": "Edit"
    },
    # box10
    "box10":{
        "auto_id": "Textbox_32",
        "control_type": "Edit"
    },
    
    # box11
    "box11":{
        "auto_id": "Textbox_33",
        "control_type": "Edit"
    },
}

BOX_12 = {
    # code: A,B,C,D,E,F,G,H,J,K,L,M,N,P,Q,R,S,T,V,W,Y,Z,AA,BB,DD,EE,FF,GG,HH,II
    "leetcode":{
        "auto_id": ["Dropdown_34","Dropdown_37","Dropdown_40","Dropdown_43"],
        "control_type": "ComboBox"
    },
    "Amount":{
        "auto_id": ["Textbox_35","Textbox_38","Textbox_41","Textbox_44"],
        "control_type": "Edit"
    },
    "Year":{
        "auto_id": ["Textbox_36","Textbox_39","Textbox_42","Textbox_45"],
        "control_type": "Edit" 
    },
}

CHECK_BOX_13 = {
    "Statutory employee":{
        "auto_id": "CheckboxTextRight_46",
        "control_type": "CheckBox"
    },
    "Retirement plan":{
        "auto_id": "CheckboxTextRight_47",
        "control_type": "CheckBox"
    },
    "Sick pay":{
        "auto_id": "CheckboxTextRight_48",
        "control_type": "CheckBox"
    },
}

BOX_14 = {
    "1": {
        "auto_id": ["Textbox_49", "Textbox_51", "Textbox_53", "Textbox_55"],
        "control_type": "Edit" 
    },
    "2":{
        "auto_id": ["Textbox_50", "Textbox_52", "Textbox_54", "Textbox_56"],
        "control_type": "Edit"
    },
}

TAX_INFOS = {
    "ST":{
        "auto_id":["Dropdown_57","Dropdown_64","Dropdown_71","Dropdown_78"], 
        "control_type":"ComboBox"
    },
    "IDNumber":{
        "auto_id":["Textbox_58","Textbox_65","Textbox_72","Textbox_79"], 
        "control_type":"Edit"
    },
    "box16":{
        "auto_id":["Textbox_59","Textbox_66","Textbox_73","Textbox_80"], 
        "control_type":"Edit"
    },
    "box17":{
        "auto_id":["Textbox_60","Textbox_67","Textbox_74","Textbox_81"], 
        "control_type":"Edit"
    },
    "box18":{
        "auto_id":["Textbox_61","Textbox_68","Textbox_75","Textbox_82"], 
        "control_type":"Edit"
    },
    "box19":{
        "auto_id":["Textbox_62","Textbox_69","Textbox_76","Textbox_83"], 
        "control_type":"Edit"
    },
    "box20":{
        "auto_id":["Dropdown_63","Dropdown_70","Dropdown_77","Dropdown_84"], 
        "control_type":"ComboBox"
    },
}
    
def fill_w2(w2_entry, data):
    fields = data.get("fields", {})

    log.info("==== START FILL W-2 ====")

    # Check for "Existing Forms List"
    if findwindows.find_windows(title="Existing Forms List"):
        log.warning("Window 'Existing Forms List' detected. Aborting fill.")
        return

    # Check if form is already filled (TS, Employer Name)
    # Optimization: Check if we're in Existing Forms List (faster than findwindows)
    if "Existing Forms List" in w2_entry.window_text():
        log.warning("Window 'Existing Forms List' detected. Aborting fill.")
        return

    log.debug(f"Available fields in data: {list(fields.keys())}")
    clear_control_cache()

    def fill_or_clear(ctrl, value):
        if value not in (None, "", 0, 0.0):
            if ctrl["control_type"] == "Edit":
                edit_text(w2_entry, ctrl, value)
            elif ctrl["control_type"] == "ComboBox":
                select_combobox(w2_entry, ctrl, value)
        else:
            try:
                c = get_control(w2_entry, ctrl["auto_id"], ctrl["control_type"])
                c.set_focus()
                if ctrl["control_type"] == "Edit":
                    c.set_text("")
                elif ctrl["control_type"] == "ComboBox":
                    try:
                        c.child_window(control_type="Edit").set_text("")
                    except:
                        c.type_keys("{DEL}")
            except:
                pass

    # Extract sub-structures
    employer = v(fields, "Employer", {})
    boxes = v(fields, "Entries", {})

    # ===============================
    # 1. Header
    # ===============================
    log.info("Header")
    fill_or_clear(W2_HEADER["TS"], v(fields, "TS"))
    fill_or_clear(W2_HEADER["F"], v(fields, "F"))
    fill_or_clear(W2_HEADER["Special tax treatment"], v(fields, "SpecialTaxTreatment"))

    # ===============================
    # 2. Employer Information
    # ===============================
    log.info("Employer Info")
    fill_or_clear(EMPLOYER_INFO["EIN"], v(employer, "EIN"))
    fill_or_clear(EMPLOYER_INFO["Name"], v(employer, "Name"))
    fill_or_clear(EMPLOYER_INFO["Name cont"], v(employer, "NameContinued"))
    fill_or_clear(EMPLOYER_INFO["Street"], v(employer, "Street"))
    fill_or_clear(EMPLOYER_INFO["City"], v(employer, "City"))
    fill_or_clear(EMPLOYER_INFO["State"], v(employer, "State"))
    fill_or_clear(EMPLOYER_INFO["ZIP"], v(employer, "ZIP"))

    # ===============================
    # 3. Boxes 1–11
    # ===============================
    log.info("Boxes 1–11")
    for box_key, ctrl in BOX_1_TO_11.items():
        value = v(boxes, box_key)
        log.debug(f"  {box_key}: value={value}, ctrl_id={ctrl.get('auto_id')}")
        fill_or_clear(ctrl, value)

    # ===============================
    # 4. Box 12
    # ===============================
    log.info("Box 12")
    box12_rows = []
    box12_data = v(boxes, "box12", [])
    log.debug(f"Raw Box 12 data: {box12_data}")
    for row in box12_data:
        if isinstance(row, dict) and "value" in row and isinstance(row["value"], dict):
            rv = row["value"]
        else:
            rv = row
        box12_rows.append({
            "code": v(rv, "LetterCode"),
            "amount": v(rv, "Amount"),
        })

    if box12_rows:
        fill_box12(w2_entry, BOX_12, box12_rows)

    # ===============================
    # 5. Box 14
    # ===============================
    log.info("Box 14")
    box14_value = v(boxes, "box14")
    if box14_value:
        fill_box14(w2_entry, BOX_14, [box14_value])

    # ===============================
    # 6. State & Local Tax
    # ===============================
    log.info("State & Local Tax")
    taxinfo_rows = []
    tax_infos_data = v(boxes, "TaxInfos", []) or []
    log.debug(f"Raw TaxInfos data: {tax_infos_data}")
    for row in tax_infos_data:
        if isinstance(row, dict) and "value" in row and isinstance(row["value"], dict):
            rv = row["value"]
        else:
            rv = row
        taxinfo_rows.append({
            "ST": v(rv, "State"),
            "IDNumber": v(rv, "IdNumber"),
            "box16": v(rv, "box16"),
            "box17": v(rv, "box17"),
            "box18": v(rv, "box18"),
            "box19": v(rv, "box19"),
            "box20": v(rv, "box20"),
        })

    # Use manual loop instead of fill_table to support clearing
    max_rows = 4 # W2 usually has 4 rows for state info
    
    for i in range(max_rows):
        row_data = taxinfo_rows[i] if i < len(taxinfo_rows) else {}
        
        for key, ctrl in TAX_INFOS.items():
            if isinstance(ctrl["auto_id"], list):
                if i >= len(ctrl["auto_id"]): continue
                aid = ctrl["auto_id"][i]
            else:
                if i > 0: continue
                aid = ctrl["auto_id"]
            
            val = row_data.get(key)
            fill_or_clear({"auto_id": aid, "control_type": ctrl["control_type"]}, val)

    log.info("==== END FILL W-2 ====")
