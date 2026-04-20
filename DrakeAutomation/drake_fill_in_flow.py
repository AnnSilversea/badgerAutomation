import json
from pywinauto import findwindows
import psutil
 
from DrakeAutomation.core.app import OpenDrake
from DrakeAutomation.flows.data_entry import DataEntryFlow
from DrakeAutomation.flows.login import LoginFlow
from DrakeAutomation.flows.client import ClientFlow
from DrakeAutomation.ui.waits import wait_form, check_client_data_entry, wait_data_entry
from DrakeAutomation.forms.w2 import fill_w2, W2ListPage
from DrakeAutomation.forms.R1099 import fill_r_1099, R1099ListPage
from DrakeAutomation.forms.SSA1099 import fill_ssa_1099, SSA1099ListPage
from DrakeAutomation.forms.DIV1099 import Div1099ListPage, fill_div_1099
from DrakeAutomation.forms.INT1099 import Int1099ListPage, fill_int_1099
from DrakeAutomation.ui.control import clear_control_cache
from DrakeAutomation.ui.logger import setup_logger
from DrakeAutomation.config import DRAKE_EXE, DRAKE_CWD, USERNAME, PASSWORD, TIMEOUT_DEFAULT
from DrakeAutomation.ocr_normalization import normalize_id

import pyautogui
import time
from typing import Dict, Any

log = setup_logger("fill in list forms")

def run_drake_fill_in_flow(form_type: str= None, client_id: str= None, list_data: Dict[str, Any]= None):
    # Open Drake
    log.info("Opening Drake application...")
    session = OpenDrake(DRAKE_EXE, DRAKE_CWD).open()
    
    # Login
    log.info("Logging in...")
    LoginFlow(session).login(USERNAME, PASSWORD)
    current_open_client_id = None
    
    win_update = findwindows.find_windows(title_re=r"Drake 20\d{2} Tax Software Updates")
    if win_update:
        win_update = session.app.window(handle=win_update[0])
        btn_cancel = win_update.child_window(title="Cancel", control_type="Button")
        if btn_cancel:
            btn_cancel.set_focus()
            btn_cancel.invoke()
            time.sleep(0.5)
        
    # ========== SELECT FORM TO RUN ==========

    data_entry = DataEntryFlow(session)
    data_entry_form = None

    # Check if we need to switch client
    if current_open_client_id != client_id:
        if current_open_client_id:
            log.info(f"Switching client from {current_open_client_id} to {client_id}")
            # Close previous client (assuming at main data entry)
            try:
                session.app.top_window().set_focus()
                session.app.top_window().type_keys("{ESC}")
                time.sleep(0.5)
            except Exception as e:
                log.warning(f"Error closing previous client: {e}")
        
        current_open_client_id = client_id

    # 2. If not, check if the main Data Entry (client level) is open
    if not data_entry_form:
        main_entry = check_client_data_entry(session.app, client_id, timeout=2)
        
        # 3. If main data entry is not open, do the full client search
        if not main_entry:
            # Before searching, ensure we are at the main screen.
            # If a data entry window for a *different* client is open, close it.
            try:
                # Check for and close "Calculation Results" window
                calc_results_windows = findwindows.find_windows(title_re=r"Drake \d{4} - \s*Calculation Results", top_level_only=True)
                if calc_results_windows:
                    calc_win = session.app.window(handle=calc_results_windows[0])
                    log.info(f"Found 'Calculation Results' window ('{calc_win.window_text()}'). Closing it.")
                    time.sleep(2.0)
                    calc_win.set_focus()
                    calc_win.type_keys("{ENTER}")
                    time.sleep(0.5)
                    session.main.wait('active', timeout=10)
                    log.info("Returned to main Drake window from Calculation Results.")

                # Find any open data entry window
                data_entry_windows = findwindows.find_windows(title_re=r"Drake \d{4} - Data Entry", top_level_only=True)
                if data_entry_windows:
                    win = session.app.window(handle=data_entry_windows[0])
                    if client_id not in win.window_text():
                        log.info(f"Data entry for another client is open ('{win.window_text()}'). Closing it.")
                        
                        # Press ESC to close the current form/screen
                        win.set_focus()
                        win.type_keys("{ESC}")
                        time.sleep(0.5) # allow time for state change
                        
                        # After first ESC, we might be at the client's form list. Check top window.
                        # If it's still a data entry window, press ESC again to close the client.
                        current_top = session.app.top_window()
                        if "Data Entry" in current_top.window_text():
                            log.info("Pressing ESC again to close the client.")
                            current_top.set_focus()
                            current_top.type_keys("{ESC}")
                            time.sleep(0.5)

                        session.main.wait('active', timeout=10)
                        log.info("Returned to main Drake window.")
            except Exception as e:
                log.warning(f"Could not check/close open data entry window. Error: {e}")

            if not client_id:
                raise ValueError("Client ID is missing. Cannot proceed with client search.")

            log.info(f"Opening client dialog for ID: {client_id}")
            client = ClientFlow(session)
            client.open_dialog()
            client.search(client_id)
            
            if not client.open_by_last4(client_id):
                log.error(f"Client {client_id} not found. Closing search dialog.")
                client.close_dialog()
                # continue
                raise ValueError(f"Client {client_id} not found in Drake.")

            log.info(f"Client {client_id} opened successfully")
            
            main_entry = wait_data_entry(session.app, client_id, timeout=TIMEOUT_DEFAULT)
            
        main_entry.type_keys(f"{1}{{ENTER}}")
        data_entry_form = wait_form(session.app, None, client_id, timeout=TIMEOUT_DEFAULT)
        t = normalize_id(data_entry_form.child_window(auto_id="Textbox_2", control_type="Edit").window_text())
        s= normalize_id(data_entry_form.child_window(auto_id="Textbox_24", control_type="Edit").window_text())
        log.info(f"TaxPayer's SSN: {t}")
        log.info(f"Spouse's SSN: {s}")
        
        data_entry_form.close()
        
        list_data = classify_TS_for_data(list_data=list_data, t=t, s=s) 
        log.info(len(list_data))
    
        
        
    for form in form_type:
        form_count = data_entry.get_form_count(form)
        log.info(f"Form count for {form}: {form_count}")
        
        FORM_NAME_MAP = {
            "W2": "W-2", "SSA": "SSA-1099", "1099": "1099-R",
            "INT": "1099-INT", "DIV": "1099-DIV",
            "MISC": "1099-MISC", "NEC": "1099-NEC", "W2G": "W-2G"
        }
        
        FORM_NAME = FORM_NAME_MAP.get(form)
        if not FORM_NAME:
            log.error(f"Invalid form_type: {form}")
            raise ValueError(f"Invalid form_type: {form}")
        
        # 4. Now, open the form from the main data entry screen
        log.info(f"Opening {form.upper()} form...")
        main_entry.type_keys(f"{form}{{ENTER}}")
        wait_timeout = 5 if form_count > 0 else TIMEOUT_DEFAULT
        data_entry_form = wait_form(session.app, FORM_NAME, client_id, timeout=wait_timeout)
        
        list_data_form = [ data for data in list_data if data.get("fields", {}).get("FormType", {}).get("value", "") == form]
        log.info(f"Number of list data in form {form}: {len(list_data_form)}")

        processed = False
        if form in ["DIV", "INT"]:
            processed = True
            if form == "DIV":
                page_list = Div1099ListPage(data_entry_form) # data_entry_form is the list window
                form_name = "Schedule B - Dividend Income"
            if form == "INT":
                page_list = Int1099ListPage(data_entry_form)
                form_name = "Schedule B - Interest Income"
            
            page_list.wait_loaded()
            log.info(f"Found {page_list.row_count()} rows")
            
            lst_exist, lst_new = page_list.classify_extract_data(list_data=list_data_form)
            
            if lst_exist:
                log.info(f"Found {len(lst_exist)} existing records")
                log.info("Opening existing records...")
                
                lst_exist = sorted(lst_exist, key=lambda x: x[0])

                for idx, data in lst_exist:
                    try:
                        log.info(f"Processing {idx+1}/{len(lst_new)}")
                        
                        log.info(f"Processing existing record at index {idx+1}")
                        page_list.open_detail(idx)
                        detail_win = wait_form(session.app, form_name, timeout=TIMEOUT_DEFAULT)
                        clear_control_cache()
                        
                        if form == "DIV":
                            fill_div_1099(detail_win, data=data)
                        if form == "INT":
                            fill_int_1099(detail_win, data=data)
                        
                        
                        log.info("Closing detail window with ESC...")
                        detail_win.type_keys("{ESC}")
                        time.sleep(0.5)  # Allow detail window to close and UI to settle
                        
                        # Re-find the data entry form window to avoid stale reference
                        log.info("Re-finding data entry form window...")
                        data_entry_form = wait_form(session.app, FORM_NAME, timeout=5)
                        
                        # Recreate page_list with fresh window reference
                        log.info("Recreating page_list object with fresh window...")
                        page_list = Div1099ListPage(data_entry_form)
                        log.info("Waiting for grid to load...")
                        page_list.wait_loaded(timeout=10)
                        log.info(f"Successfully processed record at index {idx}")
                        
                    except Exception as e:
                        log.error(f"Error processing record at index {idx+1}: {e}", exc_info=True)
                        raise

            else:
                log.info("No existing records found")
            
            if lst_new:
                log.info(f"Found {len(lst_new)} new records")
                log.info("Creating new records...")
                page_list.create_new()
                detail_win = wait_form(session.app, form_name)
                
                for idx, data in enumerate(lst_new):
                    log.info(f"Processing {idx+1}/{len(lst_new)}")
                    
                    if form == "DIV":
                        fill_div_1099(detail_win, data=data)
                    if form == "INT":
                        fill_int_1099(detail_win, data=data)

                    if idx < len(lst_new) - 1:
                        if detail_win.exists():
                            next_item = detail_win.child_window(
                                auto_id="mnuIcon_Next",
                                control_type="MenuItem"
                            )
                            if next_item.exists():
                                log.info("Clicking 'Next' MenuItem to navigate to new record...")
                                # next_item.click_input()
                                next_item.invoke()
                                log.info("[OK] Navigated to next record")
                        
                log.info("Closing detail window...")
                try:
                    detail_win.type_keys("{ESC}")
                except Exception:
                    pyautogui.press('esc')
            else:
                log.info("No new records found")
            
            try:
                if data_entry_form.exists(timeout=2):
                    data_entry_form.set_focus()
                    data_entry_form.type_keys("{ESC}")
                else:
                    pyautogui.press('esc')
                time.sleep(0.2)
            except Exception as e:
                pyautogui.press('esc')
                log.warning(f"Ignored error closing form window: {e}")
                
        if form in ["W2", "1099", "SSA"]:
            processed = True
            if form == "W2":
                page_list = W2ListPage(data_entry_form, form_count=form_count)
            if form == "1099":
                page_list = R1099ListPage(data_entry_form, form_count=form_count)
            if form == "SSA":
                page_list = SSA1099ListPage(data_entry_form, form_count=form_count)
                
            page_list.wait_loaded()

            lst_exist, lst_new = page_list.classify_extract_data(list_data=list_data_form)

            log.info(f"Found {len(lst_exist)} existing records")
            if lst_exist:
                
                log.info("Opening existing records...")
                
                if not page_list.is_list_mode:
                    log.info("In detail mode, opening existing records...")
                    if len(lst_exist) == 1:
                        
                        if form == "W2":
                            fill_w2(data_entry_form, data=lst_exist[0][1])
                        if form == "1099":
                            fill_r_1099(data_entry_form, data=lst_exist[0][1])
                        if form == "SSA":
                            fill_ssa_1099(data_entry_form, data=lst_exist[0][1])
                        
                        log.info("Update record successfully")
                    else:
                        log.warning("[Error]")
                else:
                    log.info("In list mode, opening existing records...")
                    len_rows = page_list.row_count()
                    
                    lst_exist.sort(key=lambda x: x[0])
                    root_idx = lst_exist[0][0]
                    
                    for i, (idx, data) in enumerate(lst_exist):
                        if (idx - root_idx) > 0:
                            log.info(f"Press button next: {idx - root_idx} times")
                            for _ in range(idx - root_idx):
                                page_list.next_record()
                                time.sleep(0.1)
                        
                        log.info(f"Processing {i+1}/{len(lst_exist)}")
                        log.info(f"Opening record at index {idx}")
                        if idx == root_idx:
                            page_list.open_detail(idx)
                        time.sleep(0.2)
                        
                        if form == "W2":
                            fill_w2(data_entry_form, data=data)
                        if form == "1099":
                            fill_r_1099(data_entry_form, data=data)
                        if form == "SSA":
                            fill_ssa_1099(data_entry_form, data=data)
                            
                        clear_control_cache()
                        time.sleep(0.1)
                        root_idx = idx
                        log.info(f"Update record {i+1}/{len(lst_exist)} successfully")
                        
                    # open new record
                    if len_rows - lst_exist[-1][0] > 0:
                        for _ in range(len_rows - lst_exist[-1][0]):
                            page_list.next_record()    
                            time.sleep(0.1)    
                page_list.next_record()      
                
                time.sleep(0.2)
                log.info("Processed all existing records")
            
            else:
                log.info("No existing records found")
                
            if lst_new:
                log.info(f"Found {len(lst_new)} new records to add")
                if not lst_exist:
                    page_list.create_new_record()
                    time.sleep(0.2)
                    
                for idx, data in enumerate(lst_new):
                    log.info(f"Processing {idx+1}/{len(lst_new)}")
                    
                    if form == "W2":
                        fill_w2(data_entry_form, data=data)
                    if form == "1099":
                        fill_r_1099(data_entry_form, data=data)
                    if form == "SSA":
                        fill_ssa_1099(data_entry_form, data=data)
                        
                    clear_control_cache()
                    time.sleep(0.1)
                    if idx < len(lst_new) - 1:
                        page_list.next_record()
                        time.sleep(0.1)
                    log.info("create new record successfully")
                pyautogui.press('esc')    
            else:
                log.info("No new records to add")
                pyautogui.press('esc')
    
    # if data_entry_form.exists(timeout=2):
                   
    #     data_entry_form.set_focus()
    #     data_entry_form.type_keys("{ESC}")
    # time.sleep(0.5)
        
    processed = True
           
    # Close Data Entry (Client) Window if open
    data_entry_windows = findwindows.find_windows(title_re=r"Drake \d{4} - Data Entry", top_level_only=True)
    if data_entry_windows:
        try:
            win = session.app.window(handle=data_entry_windows[0])
            log.info(f"Closing Data Entry window ('{win.window_text()}').")
            win.set_focus()
            win.type_keys("{ESC}")
            time.sleep(1.0)
        except Exception as e:
            log.warning(f"Error closing Data Entry window: {e}")
            pyautogui.press('esc')
    time.sleep(2)
    
    # Handle Calculation Results
    # Loop to ensure it is completely closed (retry up to 5 times)
    for i in range(5):
        calc_results_windows = findwindows.find_windows(
            title_re=r"DRAKE 2025\s*-\s*Calculation Results"
        )

        if not calc_results_windows:
            if i > 0:
                log.info("Calculation Results window closed successfully.")
            else:
                log.info("ℹNo 'Calculation Results' window found.")
            break

        log.info(f"Found 'Calculation Results' window (Attempt {i + 1}). Closing it...")

        try:
            calc_win = session.app.window(handle=calc_results_windows[0])
            calc_win.set_focus()
            
            btn_continue = calc_win.child_window(title="Continue", control_type="Button")
            if btn_continue.exists() and btn_continue.is_enabled():
                time.sleep(1)
                btn_continue.set_focus()
                btn_continue.invoke()
            
            try:
                calc_win.wait_not("visible", timeout=5)
            except Exception:
                pass

            still_exists = findwindows.find_windows(
                title_re=r"DRAKE 2025\s*-\s*Calculation Results"
            )

            if not still_exists:
                log.info("ENTER closed Calculation Results successfully.")
                break
            else:
                log.warning("ENTER pressed but Calculation Results still visible. Retrying...")

        except Exception as e:
            log.warning(f"Retrying close Calculation Results: {e}")

        time.sleep(1)
        
    # Close Main Window
    try:
        log.info("Attempting to close main Drake window")

        exists = session.main.exists(timeout=2)
        log.info(f"Main window exists: {exists}")

        if exists:
            log.info("Setting focus to main window")
            session.main.set_focus()

            log.info("Closing main window")
            session.main.close()

            log.info("Close command sent successfully")
        else:
            log.warning("Main window not found. Killing application...")
            session.app.kill()
            log.info("Application killed via else branch")
    except Exception as e:
        log.warning(f"Error closing main window: {e}")
        session.app.kill()
    
    if is_drake_running():
        log.warning("Drake is running. Attempting to close the application.")
        kill_drake()
        log.info("Drake has been successfully closed.")
    else:
        log.info("Drake is not running.")
        
    if not processed:
        raise ValueError(f"Automation logic for form type '{[form for form in form_type]}' is not implemented yet.")

    return list_data


def classify_TS_for_data(list_data: Dict[str, Any], t: str, s: str):
    list_final = []
    
    for data in list_data:   
        form_type = data.get("fields", {}).get("FormType", {}).get("value", "")
       
        if form_type == "W2":
            if data.get("fields", {}).get("Employee", {}).get("SSN", {}).get("value") == t:
                data["fields"]["TS"] = {
                    "value": "T"
                }
                
                list_final.append(data)
                
            if data.get("fields", {}).get("Employee", {}).get("SSN", {}).get("value") == s:
                data["fields"]["TS"] = {
                    "value": "S"
                }
                
                list_final.append(data)
        
        if form_type in ["DIV", "INT"]:
            if data.get("fields", {}).get("Recipient", {}).get("TIN", {}).get("value") == t:
                data["fields"]["TSJ"] = {
                    "value": "T"
                }
                
                list_final.append(data)
            
            if data.get("fields", {}).get("Recipient", {}).get("TIN", {}).get("value") == s:
                data["fields"]["TSJ"] = {
                    "value": "S"
                }
                
                list_final.append(data)
                
        if form_type == "SSA":
            if data.get("fields", {}).get("Beneficiary", {}).get("SSN", {}).get("value") == t:
                data["fields"]["TS"] = {
                    "value": "T"
                }
                
                list_final.append(data)
            
            if data.get("fields", {}).get("Beneficiary", {}).get("SSN", {}).get("value") == s:
                data["fields"]["TS"] = {
                    "value": "S"
                }
                
                list_final.append(data)
                
        if form_type == "1099":
            if data.get("fields", {}).get("Recipient", {}).get("TIN", {}).get("value") == t:
                data["fields"]["TS"] = {
                    "value": "T"
                }
                
                list_final.append(data)
            
            if data.get("fields", {}).get("Recipient", {}).get("TIN", {}).get("value") == s:
                data["fields"]["TS"] = {
                    "value": "S"
                }
                
                list_final.append(data)
            
    return list_final
        
def kill_drake():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            if proc.info['name'] and 'drake' in proc.info['name'].lower():
                p = psutil.Process(proc.info['pid'])

                for child in p.children(recursive=True):
                    child.kill()

                p.kill()

        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass


def is_drake_running():
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'drake' in proc.info['name'].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False