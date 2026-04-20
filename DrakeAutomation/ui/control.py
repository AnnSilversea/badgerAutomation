from pywinauto.timings import wait_until, TimeoutError
import re
import time
from DrakeAutomation.ui.logger import setup_logger

log = setup_logger("ui.control")

# ======================================================
# WAIT
# ======================================================

def wait_ready(ctrl, timeout=5):
    def _ready():
        try:
            return ctrl.exists()
        except Exception:
            return False

    wait_until(timeout, 0.2, _ready)


# ======================================================
# CACHE
# ======================================================

_CONTROL_CACHE = {}

def clear_control_cache():
    log.info("Clear control cache")
    _CONTROL_CACHE.clear()


def get_control(parent, auto_id, control_type, timeout=5):
    key = (parent.handle, auto_id, control_type)

    # Validate cached control before using
    if key in _CONTROL_CACHE:
        try:
            ctrl = _CONTROL_CACHE[key]
            if ctrl.exists():
                return ctrl
            else:
                log.debug(f"Cached control no longer exists: {control_type} auto_id={auto_id}")
                del _CONTROL_CACHE[key]
        except Exception as e:
            log.debug(f"Cached control validation failed: {e}")
            del _CONTROL_CACHE[key]

    # Find fresh control
    ctrl = parent.child_window(
        auto_id=auto_id,
        control_type=control_type
    )

    try:
        wait_ready(ctrl, timeout)
    except TimeoutError:
        log.error(f"NOT READY: {control_type} auto_id={auto_id}")
        raise

    _CONTROL_CACHE[key] = ctrl
    return ctrl


# ======================================================
# SAFE EDIT (NO DATA MIX)
# ======================================================

def edit_text(parent, field_def, value, verify=True):
    if value in (None, "", False):
        return

    ctrl = get_control(
        parent,
        field_def["auto_id"],
        field_def["control_type"]
    )

    # # FORCE FOCUS (REQUIRED)
    ctrl.set_focus()

    # FAST PATH - Direct set_edit_text
    value_str = str(value)
    try:
        ctrl.set_edit_text(value_str)
        return  # Skip verification if successful
    except Exception:
        pass

    # FALLBACK - Clear and type
    try:
        ctrl.select()
        ctrl.type_keys("{DEL}")
        ctrl.type_keys(value_str, with_spaces=True)
    except Exception:
        pass

    # VERIFY – prevent confusion (only if needed)
    if verify:
        try:
            current = ctrl.window_text().strip()
            if current != value_str:
                ctrl.select()
                ctrl.type_keys("{DEL}")
                ctrl.type_keys(value_str, with_spaces=True)
        except Exception:
            pass


# ======================================================
# SAFE COMBOBOX (NO FAST PATH)
# ======================================================

def select_combobox(parent, field_def, value, wait_commit=True):
    if value in (None, "", False):
        return

    combo = get_control(
        parent,
        field_def["auto_id"],
        "ComboBox"
    )

    combo.set_focus()
    value_str = str(value)

    try:
        # Try direct set_edit_text first
        try:
            edit = combo.child_window(control_type="Edit").wrapper_object()
            edit.set_edit_text(value_str)
            return  # Success, no wait needed
        except Exception:
            pass

        # Fallback to typing
        edit = combo.child_window(control_type="Edit").wrapper_object()
        edit.select()
        edit.type_keys("{DEL}")
        edit.type_keys(value_str, with_spaces=True)

        #  WAIT FOR COMMENT (optional)
        if wait_commit:
            wait_until(
                1,  # Reduce timeout
                0.05,  # Increase check frequency
                lambda: edit.window_text().strip() != ""
            )

    except Exception:
        raise RuntimeError(
            f"Cannot select ComboBox value '{value}' "
            f"(auto_id={field_def['auto_id']})"
        )


# ======================================================
# CHECKBOX
# ======================================================

def select_checkbox(parent, field_def, checked=True):
    cb = get_control(parent, field_def["auto_id"], "CheckBox")
    cb.set_focus()

    try:
        current = cb.get_toggle_state() == 1
        if current != checked:
            cb.toggle()
    except Exception:
        cb.toggle()


# ======================================================
# TABLE
# ======================================================

def fill_table(parent, table_def, rows, batch_wait=False):
    log.info(f"Fill table ({len(rows)} rows)")

    for row_index, row in enumerate(rows):
        for key, value in row.items():
            if key not in table_def:
                continue

            field = table_def[key]
            auto_id = field["auto_id"][row_index]
            ctype = field["control_type"]

            # Disable verification on batch mode
            verify = not batch_wait

            if ctype == "Edit":
                edit_text(
                    parent,
                    {"auto_id": auto_id, "control_type": "Edit"},
                    value,
                    verify=verify
                )
            elif ctype == "ComboBox":
                select_combobox(
                    parent,
                    {"auto_id": auto_id, "control_type": "ComboBox"},
                    value,
                    wait_commit=not batch_wait
                )
        
        # Batch wait after row (if needed)
        if batch_wait and row_index % 3 == 2:  # # Every 3 rows
            time.sleep(0.1)


# ======================================================
# BOX 14
# ======================================================

def parse_box14_multi(text):
    if not text:
        return []

    text = re.sub(r"(\d)\.\s+(\d)", r"\1.\2", text)
    pattern = re.compile(r"([A-Z\s]+?)\s+([\d,]+(?:\.\d+)?)")

    return [(t.strip(), a) for t, a in pattern.findall(text)]


def fill_box14(parent, box14_def, texts):
    # 1. Parse all items
    items = []
    if texts:
        for text in texts:
            items.extend(parse_box14_multi(text))

    # 2. Iterate all available slots
    max_rows = len(box14_def["1"]["auto_id"])

    for i in range(max_rows):
        id_1 = box14_def["1"]["auto_id"][i]
        id_2 = box14_def["2"]["auto_id"][i]

        if i < len(items):
            title, amount = items[i]
            edit_text(parent, {"auto_id": id_1, "control_type": "Edit"}, title, verify=False)
            edit_text(parent, {"auto_id": id_2, "control_type": "Edit"}, amount, verify=False)
        else:
            # Clear extra rows
            try:
                c = get_control(parent, id_1, "Edit")
                if c.window_text(): c.set_text("")
            except Exception: pass
            
            try:
                c = get_control(parent, id_2, "Edit")
                if c.window_text(): c.set_text("")
            except Exception: pass


# ======================================================
# BOX 12 (ROW SYNC)
# ======================================================

def fill_box12(parent, box12_def, rows):
    log.info(f"Fill Box 12 ({len(rows)} rows)")

    max_rows = len(box12_def["Amount"]["auto_id"])

    for i in range(max_rows):
        id_amt = box12_def["Amount"]["auto_id"][i]
        id_year = box12_def["Year"]["auto_id"][i]
        id_code = box12_def["leetcode"]["auto_id"][i]

        if i < len(rows):
            row = rows[i]
            if "amount" in row:
                edit_text(parent, {"auto_id": id_amt, "control_type": "Edit"}, row["amount"], verify=False)
            if "year" in row:
                edit_text(parent, {"auto_id": id_year, "control_type": "Edit"}, row["year"], verify=False)
            if "code" in row:
                select_combobox(parent, {"auto_id": id_code, "control_type": "ComboBox"}, row["code"], wait_commit=False)
        else:
            # Clear extra rows
            try:
                c = get_control(parent, id_amt, "Edit")
                if c.window_text(): c.set_text("")
            except Exception: pass

            try:
                c = get_control(parent, id_year, "Edit")
                if c.window_text(): c.set_text("")
            except Exception: pass

            try:
                c = get_control(parent, id_code, "ComboBox")
                try:
                    c.child_window(control_type="Edit").set_text("")
                except:
                    c.type_keys("{DEL}")
            except Exception: pass
