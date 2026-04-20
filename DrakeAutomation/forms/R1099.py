from DrakeAutomation.ui.control import (
    edit_text,
    select_combobox,
    fill_table,
    fill_box14,
    clear_control_cache,
    get_control,
)
from DrakeAutomation.ui.waits import safe_wait
from DrakeAutomation.ui.logger import setup_logger
from pywinauto.application import WindowSpecification
from typing import List, Tuple

log = setup_logger("forms.1099-R")


R1099_HEADER = {
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
    
    "Pesion type":{
        "auto_id": "Dropdown_3",
        "control_type": "ComboBox"
    },
}

PAYER_INFORMATION = {
    "TIN":{
        "auto_id": "Textbox_5",
        "control_type": "Edit"
    },
    "NAME":{
        "auto_id": "Textbox_6",
        "control_type": "Edit"
    },
    "Name continued":{
        "auto_id": "Textbox_7",
        "control_type": "Edit"
    },
    "Street":{
        "auto_id": "Textbox_8",
        "control_type": "Edit"
    },
    "City":{
        "auto_id": "Textbox_9",
        "control_type": "Edit"
    },
    
    # U.S.ONLY
    "State":{
        "auto_id": "Dropdown_10",
        "control_type": "ComboBox"
    },
    "ZIP":{
        "auto_id": "Textbox_11", 
        "control_type": "Edit"
    },
    
    # Foreign ONLY
    "Province/state":{
        "auto_id": "Textbox_12",
        "control_type": "Edit"
    },
    
    "Country":{
        "auto_id": "Dropdown_13",
        "control_type": "ComboBox"
    },
    
    "Postal code":{
        "auto_id": "Textbox_14",
        "control_type": "Edit"
    },
    "Phone":{
        "auto_id": "Textbox_15",
        "control_type": "Edit"
    },
}

RECIPIENT_INFORMATION = {
    # Name
    "First Name":{
        "auto_id": "TextboxOverride_16",
        "control_type": "Edit"
    },
    "Last Name":{
        "auto_id": "TextboxOverride_17",
        "control_type": "Edit"
    },
    "Street":{
        "auto_id": "TextboxOverride_18",
        "control_type": "Edit"
    },
    "City":{
        "auto_id": "TextboxOverride_19",
        "control_type": "Edit"
    },
    
    # U.S.ONLY
    "State":{
        "auto_id": "DropdownOverride_20",
        "control_type": "ComboBox"
    },
    "ZIP":{
        "auto_id": "TextboxOverride_21",
        "control_type": "Edit"
    },
    
    # Foreign ONLY
    
    "Province/state":{
        "auto_id": "TextboxOverride_22",
        "control_type": "Edit"
    },
    
    "Country":{
        "auto_id": "DropdownOverride_23",
        "control_type": "ComboBox"
    },
    
    "Postal code":{
        "auto_id": "TextboxOverride_24",
        "control_type": "Edit"
    },
}

BOX_1_TO_13 = {
    "box1":{
        "auto_id": "Textbox_25",
        "control_type": "Edit"
    },
    "box2a":{
        "auto_id": "Textbox_26",
        "control_type": "Edit"
    },
    "box3":{
        "auto_id": "Textbox_29",
        "control_type": "Edit"
    },
    "box4":{
        "auto_id": "Textbox_30",
        "control_type": "Edit"
    },
    "box5":{
        "auto_id": "Textbox_31",
        "control_type": "Edit"
    },
    "box6":{
        "auto_id": "Textbox_32",
        "control_type": "Edit"
    },
    "box7":{
        "auto_id": ["Dropdown_33", "Dropdown_34"],
        "control_type": "ComboBox"
    },
    "box8":{
        "auto_id": ["Textbox_36", "Textbox_37"],
        "control_type": "Edit"
    },
    "box9a":{
        "auto_id": "Textbox_38",
        "control_type": "Edit"
    },
    "box9b":{
        "auto_id": "Textbox_39",
        "control_type": "Edit"
    },
    "box10":{
        "auto_id": "Textbox_40",
        "control_type": "Edit"
    },
    "box11":{
        "auto_id": "Textbox_41",
        "control_type": "Edit"
    },
}

TAX_INFOS = {
    "box14":{
        "auto_id": ["Textbox_43", "Textbox_50"],
        "control_type": "Edit"
    },
    "State":{
        "auto_id": ["Dropdown_44", "Dropdown_51"],
        "control_type": "ComboBox"
    },
    "PayerStateNumber":{
        "auto_id": ["Textbox_45", "Textbox_52"],
        "control_type": "Edit"
    },
    "box16":{
        "auto_id": ["Textbox_46", "Textbox_53"],
        "control_type": "Edit"
    },
    "box17":{
        "auto_id": ["Textbox_47", "Textbox_54"],
        "control_type": "Edit"
    },
    "box18":{
        "auto_id": ["Dropdown_48", "Dropdown_55"],
        "control_type": "ComboBox"
    },
    "box19":{
        "auto_id": ["Textbox_49", "Textbox_56"],
        "control_type": "Edit"
    },
}

def v(fields, key, default=None):
    """Extract value from nested structure with .get("value")"""
    if not isinstance(fields, dict):
        return default
    val = fields.get(key, default)
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val

class R1099ListPage:
    """
    Represents the 1099-R form window in 2 modes:
    - LIST MODE (2+ records): DataGrid
    - DETAIL MODE (0-1 record): Direct form
    """
    def __init__(self, win: WindowSpecification, form_count: int=0):
        self.win = win
        self.is_list_mode = False
        self.grid = None
        self.btn_next = None
        
        if form_count > 1:
            log.info(f"[OK] 1099-R is in LIST mode (detected by form count: {form_count})")
            self.is_list_mode = True
            self.grid = win.child_window(title_re="Existing Forms List - 1099: 1099-R, Retirement", control_type="Window")\
                .child_window(auto_id="MultiInstanceColumnView", control_type="Custom")\
                    .child_window(auto_id="MultiInstanceDataGrid", control_type="DataGrid")
                    
            log.info("[OK] 1099-R is in LIST mode (detected by form count)")
        
        # If not list mode, try to find Next button (DETAIL MODE)
        if form_count <= 1:
            try:
                self.btn_next = win.child_window(auto_id="mnuIcon_Next", control_type="MenuItem")
                if self.btn_next.exists():
                    log.info("[OK] 1099-R is in DETAIL mode (0-1 record with Next MenuItem)")
            except:
                pass

    def wait_loaded(self, timeout=30):
        if self.is_list_mode:
            safe_wait(lambda: self.grid.exists() and self.grid.is_visible(), timeout=timeout, desc="1099-R list grid ready")
            log.info("1099-R list page ready (2+ records)")
        else:
            log.info("1099-R detail form ready (0-1 record)")

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
                lambda: self.win.child_window(auto_id=R1099_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=3,
                desc="Wait for 1099-R detail view"
            )
        except Exception:
            log.warning("Double click might have failed. Retrying with ENTER key...")
            row.set_focus()
            row.type_keys("{ENTER}")
            # Wait again with longer timeout
            safe_wait(
                lambda: self.win.child_window(auto_id=R1099_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=10,
                desc="Wait for 1099-R detail view (retry)"
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
        try:
            ts_field = self.win.child_window(
                auto_id=R1099_HEADER["TS"]["auto_id"],
                control_type=R1099_HEADER["TS"]["control_type"]
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

    def get_current_payer_name(self) -> str:
        try:
            name_field = self.win.child_window(
                auto_id=PAYER_INFORMATION["NAME"]["auto_id"],
                control_type=PAYER_INFORMATION["NAME"]["control_type"]
            )
            if name_field.exists():
                name = name_field.window_text()
                log.debug(f"Current Payer Name in form: '{name}'")
                return name.strip()
        except Exception as e:
            log.debug(f"Could not read Payer Name from form: {e}")
        return ""

    def find_record_index(self, payer_name: str, ts: str) -> int | None:
        """
        Finds a record by Payer Name and TS.
        - In LIST mode, returns the row index if found, else None.
        - In DETAIL mode, returns 0 if the current form matches, else None.
        """
        target_ts = str(ts).strip().upper()
        target_name = str(payer_name).strip().upper()
        
        if not target_name and not target_ts:
            log.warning("No TS and Payer Name provided in data, cannot check for duplicates.")
            return None

        log.info(f"Checking for existing 1099-R: Target TS='{target_ts}', Target Name='{target_name}'")

        if self.is_list_mode:
            for i, row in enumerate(self.rows()):
                row_ts = self.get_row_text(row, 1).strip().upper()
                row_name = self.get_row_text(row, 2).strip().upper()
                
                log.info(f"  Row {i+1}: Grid TS='{row_ts}', Name='{row_name}'")
                
                if row_ts == target_ts and row_name == target_name:
                    log.info(f"  [MATCH] Found existing record at row index {i}")
                    return i
            log.info("  [NO MATCH] No existing record found in grid")
        else:
            curr_ts = self.get_current_ts()
            curr_name = self.get_current_payer_name().upper()

            log.info(f"  Detail View: Current TS='{curr_ts}', Name='{curr_name}'")

            if not curr_name and not curr_ts:
                log.info("  [EMPTY] Current form is empty")
                return None

            if curr_ts == target_ts and curr_name == target_name:
                log.info("  [MATCH] Found existing record in detail view")
                return 0
            
            log.info("  [NO MATCH] Current record does not match")
        
        return None

    def check_record_exists(self, data: dict) -> int | None:
        if not data:
            return None
        fields = data.get("fields", {})
        payer = v(fields, "Payer", {})
        ts = v(fields, "TS") or "T"
        name = v(payer, "Name")
        return self.find_record_index(name, ts)

    def create_new_record(self):
        if self.is_list_mode:
            log.info("Creating new 1099-R record (List Mode)")
            self.grid.set_focus()
            self.grid.type_keys("^{END}")
            self.grid.type_keys("{ENTER}")
            # Wait for detail view
            safe_wait(
                lambda: self.win.child_window(auto_id=R1099_HEADER["TS"]["auto_id"], control_type="ComboBox").exists(),
                timeout=10,
                desc="Wait for new 1099-R detail view"
            )
        else:
            # In detail mode (0-1 record): use Next button to create new record
            log.info("Creating new 1099-R record (Detail Mode)")
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
            curr_name = self.get_current_payer_name()
            curr_ts = self.get_current_ts()
            if not curr_name and not curr_ts:
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

def fill_r_1099(r1099_entry, data=None):
    """
    Fill 1099-R form on Drake.
    r1099_entry: Data Entry window of 1099-R
    """

    if data is None:
        log.warning("No data provided for fill_r_1099")
        return
    fields = data.get("fields", {})

    log.info("==== START FILL 1099-R ====")
    clear_control_cache()

    def fill_or_clear(ctrl, value):
        # Treat 0 as a valid value to fill
        if value is not None and value != "":
            # Convert to string to avoid '0 == False' issue in edit_text if it exists
            val_str = str(value)
            if ctrl["control_type"] == "Edit":
                edit_text(r1099_entry, ctrl, val_str)
            elif ctrl["control_type"] == "ComboBox":
                select_combobox(r1099_entry, ctrl, val_str)
        else:
            # Clear logic
            try:
                c = get_control(r1099_entry, ctrl["auto_id"], ctrl["control_type"])
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

    # ===============================
    # 1. Header
    # ===============================
    log.info("Header")
    header_data_map = {
        "TS": v(fields, "TS"),
        "F": v(fields, "F"),
        "Pesion type": v(fields, "PensionType"),
    }
    for key, ctrl in R1099_HEADER.items():
        val = header_data_map.get(key)
        fill_or_clear(ctrl, val)

    # ===============================
    # 2. Payer Information
    # ===============================
    log.info("Payer Info")
    payer = v(fields, "Payer", {})
    log.debug(f"Extracted Payer: {payer}")

    payer_mapping = {
        "TIN": "TIN",
        "NAME": "Name",
        "Name continued": "NameContinued",
        "Street": "Street",
        "City": "City",
        "State": "State",
        "ZIP": "ZIP",
        "Province/state": "Province",
        "Country": "Country",
        "Postal code": "PostalCode",
        "Phone": "PhoneNumber",
    }

    for ctrl_key, data_key in payer_mapping.items():
        if ctrl_key not in PAYER_INFORMATION:
            continue
        
        ctrl = PAYER_INFORMATION[ctrl_key]
        val = v(payer, data_key)
        fill_or_clear(ctrl, val)

    # ===============================
    # 3. Boxes 1–11
    # ===============================
    log.info("Boxes 1–11")
    boxes = v(fields, "Entries", {})
    ci_boxes = {k.lower(): v for k, v in boxes.items()}
    
    for key, field in BOX_1_TO_13.items():
        value = v(ci_boxes, key)
        log.debug(f"  {key}: {value}")

        # Check for empty values. `0` and `0.0` are valid and should be filled.
        if value is not None and value != "":
            # Multi-control fields (box7, box8)
            if isinstance(field["auto_id"], list):
                for idx, auto_id in enumerate(field["auto_id"]):
                    item_val = None
                    if isinstance(value, (list, tuple)):
                        item_val = value[idx] if idx < len(value) else None
                    elif idx == 0:
                        item_val = value

                    fill_or_clear(
                        {"auto_id": auto_id, "control_type": field["control_type"]}, 
                        item_val
                    )
            else:
                fill_or_clear(field, value)

    # ===============================
    # 4. State / Local Tax (TaxInfos)
    # ===============================
    log.info("State & Local Tax")
    tax_infos_data = v(boxes, "TaxInfos", []) or []
    log.debug(f"Raw TaxInfos data: {tax_infos_data}")

    # Determine max rows supported by UI
    max_rows = 0
    for ctrl in TAX_INFOS.values():
        if isinstance(ctrl["auto_id"], list):
            max_rows = max(max_rows, len(ctrl["auto_id"]))
    if max_rows == 0:
        max_rows = 1

    if len(tax_infos_data) > max_rows:
        log.warning(f"TaxInfos count ({len(tax_infos_data)}) exceeds UI slots ({max_rows}). Truncating extra rows.")

    # Loop through the UI rows (max_rows)
    for i in range(max_rows):
        # Get the corresponding data row, or an empty dict if no data
        raw_row_data = tax_infos_data[i] if i < len(tax_infos_data) else {}
        # Handle potential nested 'value' key for the whole row
        row_data = raw_row_data.get("value", raw_row_data) if isinstance(raw_row_data, dict) else raw_row_data

        # Loop through the fields for the current row
        for key, ctrl in TAX_INFOS.items():
            # Get the auto_id for the current UI row and field
            if isinstance(ctrl["auto_id"], list):
                if i >= len(ctrl["auto_id"]):
                    continue
                aid = ctrl["auto_id"][i]
            else:
                # If the control is not a list, it only applies to the first row
                if i > 0:
                    continue
                aid = ctrl["auto_id"]

            # Get the value for the field, using the 'v' helper to handle potential nested 'value' on the field itself
            val = v(row_data, key)

            fill_or_clear({"auto_id": aid, "control_type": ctrl["control_type"]}, val)

    log.info("==== END FILL 1099-R ====")