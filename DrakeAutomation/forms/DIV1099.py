# forms/div1099_list.py
from DrakeAutomation.ui.control import (
    edit_text,
    select_combobox,
    fill_table,
    clear_control_cache,
    get_control,
)

from DrakeAutomation.ui.waits import safe_wait
from DrakeAutomation.ui.logger import setup_logger
from typing import List, Tuple
from pywinauto.application import WindowSpecification

log = setup_logger("forms.div1099_list")

def v(fields, key, default=None):
    """Extract value from nested structure with .get("value")"""
    if not isinstance(fields, dict):
        return default
    val = fields.get(key, default)
    if isinstance(val, dict) and "value" in val:
        return val["value"]
    return val

class Div1099ListPage:
    def __init__(self, win: WindowSpecification):
        self.win = win

        # ---- main grid ----
        self.grid = win.child_window(
            auto_id="MacrosWindow_Macros",
            control_type="DataGrid"
        )

        # ---- buttons ----
        self.btn_item_detail = win.child_window(
            title="Item Detail",
            auto_id="ButtonItemDetail",
            control_type="Button"
        )

        self.btn_save = win.child_window(
            title="Save",
            auto_id="ButtonSave",
            control_type="Button"
        )

        self.btn_delete = win.child_window(
            title="Delete Row(s)",
            auto_id="ButtonDeleteRows",
            control_type="Button"
        )

        self.btn_cancel = win.child_window(
            title="Cancel",
            auto_id="ButtonCancel",
            control_type="Button"
        )

    # --------------------------------------------------
    # waits
    # --------------------------------------------------
    def wait_loaded(self, timeout=30):
        def _ready():
            try:
                # Check if parent window still exists
                if not self.win.exists():
                    log.debug("Parent window no longer exists")
                    return False
                    
                # Re-find grid each check to avoid stale references
                grid = self.win.child_window(
                    auto_id="MacrosWindow_Macros",
                    control_type="DataGrid"
                )
                exists = grid.exists()
                is_visible = grid.is_visible() if exists else False
                is_enabled = grid.is_enabled() if exists else False
                
                log.debug(f"Grid check: exists={exists}, visible={is_visible}, enabled={is_enabled}")
                return exists and is_visible and is_enabled
            except Exception as e:
                log.debug(f"wait_loaded check failed: {e}")
                return False

        safe_wait(
            _ready,
            timeout=timeout,
            desc="1099-DIV list grid ready"
        )

        # Refresh cached grid reference after waiting
        try:
            self.grid = self.win.child_window(
                auto_id="MacrosWindow_Macros",
                control_type="DataGrid"
            )
        except Exception as e:
            log.warning(f"Failed to refresh grid reference: {e}")

        log.info("1099-DIV list page ready")

    # --------------------------------------------------
    # grid helpers
    # --------------------------------------------------
    def rows(self):
        try:
            # Re-find grid to avoid stale references
            self.grid = self.win.child_window(
                auto_id="MacrosWindow_Macros",
                control_type="DataGrid"
            )
            return self.grid.children(control_type="DataItem")
        except Exception as e:
            log.warning(f"rows(): Error accessing grid rows: {e}")
            return []

    def row_count(self) -> int:
        return len(self.rows())

    def select_row(self, index: int):
        rows = self.rows()
        if index >= len(rows):
            raise IndexError(f"Row index {index} out of range")

        row = rows[index]
        row.click_input()
        log.info(f"Selected row {index}")

    # --------------------------------------------------
    # open detail
    # --------------------------------------------------
    def open_detail(self, index: int):
        self.select_row(index)

        # cách an toàn nhất: click Item Detail button
        self.btn_item_detail.click_input()
        log.info(f"Opened Item Detail for row {index}")

    def open_detail_by_double_click(self, index: int):
        rows = self.rows()
        if index >= len(rows):
            raise IndexError(f"Row index {index} out of range")

        rows[index].double_click_input()
        log.info(f"Opened Item Detail (double click) for row {index}")

    # --------------------------------------------------
    # duplicate check & creation
    # --------------------------------------------------
    def get_row_text(self, row, col_index):
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

    def find_payer_index(self, data):
        fields = data.get("fields", {})
        payer = v(fields, "Payer", {})
        
        target_tsj = str(v(fields, "TSJ") or "T").strip().upper()
        target_tin = str(v(payer, "TIN") or "").replace("-", "").strip()
        target_name = str(v(payer, "Name") or "").strip().upper()
        
        if not target_tin and not target_name:
            return None

        log.info(f"Checking for existing Payer: TSJ={target_tsj}, TIN={target_tin}, Name={target_name}")
        
        rows = self.rows()
        for i, row in enumerate(rows):
            # Columns: TSJ (1), Tax ID Number (2), Name (3)
            row_tsj = self.get_row_text(row, 1).strip().upper()
            row_tin = self.get_row_text(row, 2).replace("-", "").strip()
            row_name = self.get_row_text(row, 3).strip().upper()
            
            log.info(f"Row {i+1}: Grid TSJ='{row_tsj}', TIN='{row_tin}', Name='{row_name}' vs Target TSJ='{target_tsj}', TIN='{target_tin}', Name='{target_name}'")

            if not row_tin and not row_name:
                continue

            if row_tsj == target_tsj and row_tin == target_tin and row_name == target_name:
                log.info(f"Found existing record at row {i+1}: TSJ={row_tsj}, TIN={row_tin}, Name={row_name}")
                return i
        
        return None

    def create_new(self):
        log.info("Creating new 1099-DIV form")
        self.grid.set_focus()
        self.grid.type_keys("^{END}")
        self.btn_item_detail.click_input()

    def add_if_not_exists(self, data):
        idx = self.find_payer_index(data)
        if idx is not None:
            log.info(f"Record already exists at row {idx}. Opening it.")
            # self.open_detail(idx)
            return idx
        
        log.info("Record does not exist. Creating new.")
        # self.create_new()
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
            

DIV_1099_HEADER = {
    # TSJ:
    # S, S  Belongs to the Spouse of the Primary Taxpayer
    # J, J  Belongs to each spouse equally 
    # T, T  Belongs to the Primary Taxpayer
    "TSJ": {
        "auto_id": "Dropdown_1",
        "control_type": "ComboBox"
    },
    
    "F": {
        "auto_id": "Textbox_2",
        "control_type": "Edit"
    },
    
    "ST":{
        "auto_id": "Dropdown_3",
        "control_type": "ComboBox"
    },
}

PAYER_INFORMATION = {
    "Tax ID number": {
        "auto_id": "Textbox_6",
        "control_type": "Edit"
    },
    "Name": {
        "auto_id": "Textbox_8",
        "control_type": "Edit"
    },
    "Street Address": {
        "auto_id": "Textbox_9",
        "control_type": "Edit"
    },
    "City": {
        "auto_id": "Textbox_10",
        "control_type": "Edit"
    },
    
    # U.S. ONLY
    "State": {
        "auto_id": "Dropdown_11",
        "control_type": "ComboBox"
    },
    "ZIP": {
        "auto_id": "Textbox_12",
        "control_type": "Edit"
    },
    
    # Foreign ONLY
    "Province/state":{
        "auto_id": "Textbox_13",
        "control_type": "Edit"
    },
    
    "Country":{
        "auto_id": "Dropdown_14",
        "control_type": "ComboBox"
    },
    
    "Postal code":{
        "auto_id": "Textbox_15",
        "control_type": "Edit"
    },
    
    "Account number":{
        "auto_id": "Textbox_16",
        "control_type": "Edit"
    },
}

BOX_1_TO_13 = {
    # box1a
    "box1a":{
        "auto_id": "Textbox_18",
        "control_type": "Edit"
    },
    # box1b
    "box1b":{
        "auto_id": "Textbox_19",
        "control_type": "Edit"
    },
    # box2a
    "box2a":{
        "auto_id": "Textbox_20",
        "control_type": "Edit"
    },
    # box2b
    "box2b":{
        "auto_id": "Textbox_21",
        "control_type": "Edit"
    },
    # box2cq: Q1,Q3,Q4
    "box2cq":{
        "auto_id": "Dropdown_22",
        "control_type": "ComboBox"
    },
    # box2c
    "box2c":{
        "auto_id": "Textbox_23",
        "control_type": "Edit"
    },
    # box2d
    "box2d":{
        "auto_id": "Textbox_24",
        "control_type": "Edit"
    },
    # box2e
    "box2e":{
        "auto_id": "Textbox_25",
        "control_type": "Edit"
    },
    # box2f
    "box2f":{
        "auto_id": "Textbox_26",
        "control_type": "Edit"
    },
    # box3
    "box3":{
        "auto_id": "Textbox_27",
        "control_type": "Edit"
    },
    # box4
    "box4":{
        "auto_id": "Textbox_28",
        "control_type": "Edit"
    },
    # box5
    "box5":{
        "auto_id": "Textbox_29",
        "control_type": "Edit"
    },
    # box6
    "box6":{
        "auto_id": "Textbox_30",
        "control_type": "Edit"
    },
    # box7
    "box7":{
        "auto_id": "Textbox_31",
        "control_type": "Edit"
    },
    # box8
    "box8":{
        "auto_id": "Dropdown_32",
        "control_type": "ComboBox"
    },
    "box9":{
        "auto_id": "Textbox_33",
        "control_type": "Edit"
    },
    # box10
    "box10":{
        "auto_id": "Textbox_34",
        "control_type": "Edit"
    },
    # box12
    "box12":{
        "auto_id": "Textbox_35",
        "control_type": "Edit"
    },
    # box13
    "box13":{
        "auto_id": "Textbox_36",
        "control_type": "Edit"
    },
}

TAX_INFOS = {
    "box14":{
        "auto_id":["Dropdown_37","Dropdown_40"], 
        "control_type":"ComboBox"
    },
    "box15":{
        "auto_id":["Textbox_38","Textbox_41"], 
        "control_type":"Edit"
    },
    "box16":{
        "auto_id":["Textbox_39","Textbox_42"], 
        "control_type":"Edit"
    },
}

def fill_div_1099(div_entry, data):
    """
    Fill 1099-DIV form with extracted data from JSON
    
    Args:
        div_entry: Data Entry window of 1099-DIV
        data: Dictionary containing extracted 1099-DIV data with nested .value structure
    """
    if data is None:
        log.warning("No data provided for fill_div_1099")
        return
    
    fields = data.get("fields", {})

    log.info("==== START FILL 1099-DIV ====")
    clear_control_cache()

    # ===============================
    # 1. Header
    # ===============================
    log.info("Header")
    select_combobox(div_entry, DIV_1099_HEADER["TSJ"], v(fields, "TSJ"))
    payer = v(fields, "Payer", {})
    recipient = v(fields, "Recipient", {})
    log.debug(f"Extracted Payer: {payer}")
    log.debug(f"Extracted Recipient: {recipient}")

    if payer:
        edit_text(div_entry, PAYER_INFORMATION["Tax ID number"], v(payer, "TIN"))
        edit_text(div_entry, PAYER_INFORMATION["Name"], v(payer, "Name"))
        
        edit_text(div_entry, PAYER_INFORMATION["Street Address"], v(payer, "Street"))
            
        edit_text(div_entry, PAYER_INFORMATION["ZIP"], v(payer, "ZIP"))

    if recipient:
        edit_text(
            div_entry,
            PAYER_INFORMATION["Account number"],
            v(recipient, "AccountNumber"),
        )

    # ===============================
    # 3. Boxes 1–13
    # ===============================
    log.info("Boxes 1–13")

    # Normalization puts data in "Entries" (dict), not "Transactions" (list)
    txn = v(fields, "Entries", {})
    
    if not txn:
        log.warning("No entries found in JSON")
        log.info("==== END FILL 1099-DIV ====")
        return
    
    log.debug(f"Processing Transaction: {txn}")

    box_mappings = {
        "box1a": "Box1a",
        "box1b": "Box1b",
        "box2a": "Box2a",
        "box2b": "Box2b",
        "box2c": "Box2c",
        "box2d": "Box2d",
        "box2e": "Box2e",
        "box2f": "Box2f",
        "box3": "Box3",
        "box4": "Box4",
        "box5": "Box5",
        "box6": "Box6",
        "box7": "Box7",
        "box8": "Box8",
        "box9": "Box9",
        "box10": "Box10",
        "box12": "Box12",
        "box13": "Box13",
    }

    for box_key, json_key in box_mappings.items():
        if box_key not in BOX_1_TO_13:
            continue

        value = v(txn, json_key, "")
        log.debug(f"  {box_key} ({json_key}): {value}")

        ctrl = BOX_1_TO_13[box_key]

        if value in (None, 0, 0.0, "", False):
            try:
                c = get_control(div_entry, ctrl["auto_id"], ctrl["control_type"])
                c.set_focus()
                if ctrl["control_type"] == "Edit":
                    c.set_text("")
                elif ctrl["control_type"] == "ComboBox":
                    try:
                        c.child_window(control_type="Edit").set_text("")
                    except Exception:
                        pass
            except Exception:
                pass
            continue

        if ctrl["control_type"] == "Edit":
            edit_text(div_entry, ctrl, value)
        elif ctrl["control_type"] == "ComboBox":
            select_combobox(div_entry, ctrl, value)

    # ===============================
    # 4. State Tax Info (Box 14–16)
    # ===============================
    log.info("State Tax Info")

    taxinfo_rows = []
    state_taxes_raw = v(txn, "TaxInfos", [])
    log.debug(f"State Taxes Raw: {state_taxes_raw}")
    
    if state_taxes_raw:
        for row_raw in state_taxes_raw:
            if isinstance(row_raw, dict) and "value" in row_raw:
                row = row_raw["value"]
            else:
                row = row_raw
            
            if row is None:
                continue
                
            taxinfo_rows.append({
                "box14": v(row, "Box14"),
                "box15": v(row, "Box15"),
                "box16": v(row, "Box16"),
            })

    # Determine max rows
    max_rows = 0
    for ctrl in TAX_INFOS.values():
        if isinstance(ctrl["auto_id"], list):
            max_rows = max(max_rows, len(ctrl["auto_id"]))
    if max_rows == 0:
        max_rows = 1

    for i in range(max_rows):
        row_data = taxinfo_rows[i] if i < len(taxinfo_rows) else {}

        for key, ctrl in TAX_INFOS.items():
            if isinstance(ctrl["auto_id"], list):
                if i >= len(ctrl["auto_id"]):
                    continue
                aid = ctrl["auto_id"][i]
            else:
                if i > 0:
                    continue
                aid = ctrl["auto_id"]

            val = row_data.get(key)

            if val not in (None, "", 0, 0.0, False):
                if ctrl["control_type"] == "Edit":
                    edit_text(div_entry, {"auto_id": aid, "control_type": "Edit"}, val)
                elif ctrl["control_type"] == "ComboBox":
                    select_combobox(div_entry, {"auto_id": aid, "control_type": "ComboBox"}, val)
            else:
                try:
                    c = get_control(div_entry, aid, ctrl["control_type"])
                    c.set_focus()
                    if ctrl["control_type"] == "Edit":
                        c.set_text("")
                    elif ctrl["control_type"] == "ComboBox":
                        try:
                            c.child_window(control_type="Edit").set_text("")
                        except Exception:
                            pass
                except Exception:
                    pass

    log.info("==== END FILL 1099-DIV ====")