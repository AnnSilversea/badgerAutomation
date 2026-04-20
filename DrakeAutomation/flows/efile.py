import time
import ctypes
import os
import pyautogui
from datetime import datetime
from ctypes import wintypes
from pywinauto import findwindows
from pywinauto.timings import wait_until, Timings
from DrakeAutomation.ui.logger import setup_logger
from DrakeAutomation.drake_fill_in_flow import is_drake_running, kill_drake

from dotenv import load_dotenv
load_dotenv()

log = setup_logger("flows.ef")

Timings.after_clickinput_wait = 0.05
Timings.after_setfocus_wait = 0.05
Timings.after_sendkeys_key_wait = 0.01

BM_SETCHECK = 0x00F1
BST_UNCHECKED = 0
BST_CHECKED = 1

BM_GETCHECK  = 0x00F0
BM_SETCHECK  = 0x00F1
BM_CLICK     = 0x00F5

BST_UNCHECKED = 0
BST_CHECKED   = 1


LRESULT = ctypes.c_ssize_t

user32 = ctypes.WinDLL("user32", use_last_error=True)
SendMessageW = user32.SendMessageW
SendMessageW.argtypes = (wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
SendMessageW.restype = LRESULT



class EFPrepareFlow:
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

    def wait_window(self, title=None, title_re=None, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if title_re:
                    hwnds = findwindows.find_windows(title_re=title_re)
                else:
                    hwnds = findwindows.find_windows(title=title)

                if hwnds:
                    win = self.app.window(handle=hwnds[0])
                    win.wait("visible enabled", timeout=5)
                    return win
            except Exception:
                pass
            time.sleep(0.10)
        
        target = title or title_re
        screenshot = self._take_screenshot(target)

        try:
            recipient = os.getenv("USER_EMAIL")
            if recipient:
                from services.email_service import send_email
                subject = f"[Badger] Automation Error: Window not found - {target}"
                html_body = f"<p>Automation failed waiting for window: <b>{target}</b></p>"
                text_body = f"Automation failed waiting for window: {target}."
                send_email(recipient, subject, html_body, text_body, attachments=[screenshot] if screenshot else [])
        except Exception as e:
            log.error(f"Failed to send error email: {e}")
        
        raise TimeoutError(f"Window not found: {title or title_re}. Screenshot saved at: {screenshot}")
    
    def open_efile(self):
        # ---- menu items ----
        btn_ef = self.main.child_window(
            auto_id="MainWindow_MenuItemEF", 
            control_type="MenuItem")
    
        btn_ef.wait("exists enabled visible", timeout=10)

        _prepare_spec = dict(
            auto_id="MainWindow_MenuItemEFPrepareExtensions",
            control_type="MenuItem",
        )
        
        last_err = None
        for attempt in range(1):
            try:
                log.info(f"Opening EF menu (Attempt {attempt+1})...")
                btn_ef.set_focus()
                try:
                    btn_ef.invoke()
                except Exception:
                    btn_ef.type_keys("{ENTER}", set_foreground=False)
                
                time.sleep(1)

                for idx in (0, 1):
                    try:
                        mi = self.main.child_window(found_index=idx, **_prepare_spec)
                        mi.wait("exists enabled visible", timeout=3)
                        log.info(f"✓ 'Prepare Extensions' clicked (found_index={idx})")
                        mi.invoke()
                        return
                    except Exception as e:
                        last_err = e
            except Exception as e:
                log.warning(f"Error interacting with EF menu: {e}")
                last_err = e
            
            finally:
                # close any open menu to reset state before next attempt
                try:
                    self.main.set_focus()
                    self.main.type_keys("{ESC}", set_foreground=False)
                except Exception:
                    pass

            time.sleep(0.5)

        target = "Prepare Extensions"
        screenshot = self._take_screenshot(target)
        error_msg = f"Could not activate menu item: {target}. Please ensure Drake is open and the EF menu is accessible."
        if last_err:
            error_msg += f" (Details: {last_err})"
            
        try:
            recipient = os.getenv("USER_EMAIL")
            if recipient:
                from services.email_service import send_email
                subject = f"[Badger] Automation Error: {target}"
                html_body = f"<p>{error_msg}</p>"
                text_body = f"{error_msg}"
                send_email(recipient, subject, html_body, text_body, attachments=[screenshot] if screenshot else [])
        except Exception as e:
            log.error(f"Failed to send error email: {e}")
                    
        
        if is_drake_running():
            kill_drake()
                
        raise TimeoutError(f"{error_msg} Screenshot saved at: {screenshot}")


    def _map_checkboxes_by_auto_id(self, dlg):
        boxes = dlg.descendants(control_type="CheckBox")
        m = {}
        for b in boxes:
            try:
                aid = b.element_info.automation_id
                if aid:
                    m[aid] = b
            except Exception:
                continue
        return m
    
    def _set_checkbox_fast(self, cb_wrapper, checked=True):
        want = BST_CHECKED if checked else BST_UNCHECKED

        hwnd = None
        try:
            hwnd = cb_wrapper.element_info.handle
        except Exception:
            hwnd = None

        if hwnd:
            try:
                cur = SendMessageW(hwnd, BM_GETCHECK, 0, 0)
            except Exception:
                cur = None

            if cur is not None and int(cur) == want:
                return

            SendMessageW(hwnd, BM_CLICK, 0, 0)
            return

        try:
            cur = cb_wrapper.iface_toggle.CurrentToggleState  # 0/1/2
            if (cur == 1) == checked:
                return
        except Exception:
            pass

        try:
            cb_wrapper.set_focus()
            cb_wrapper.iface_toggle.Toggle()
        except Exception:
            try:
                cb_wrapper.set_toggle_state(1 if checked else 0)
            except Exception:
                cb_wrapper.set_focus()
                cb_wrapper.toggle()


    # ------------------------------------------------------------
    # STEP 1: tick + Next
    # ------------------------------------------------------------
    def click_after_prepare_extensions(self):
        dlg = self.wait_window(title_re=r"Drake 2025 - Batch Extensions", timeout=30)
        dlg.set_focus()
        log.info("Batch Extensions dialog found")

        t0 = time.time()

        cb_map = self._map_checkboxes_by_auto_id(dlg)

        ids = ["1040", "1041", "1042"]
        for aid in ids:
            cb = cb_map.get(aid)
            if not cb:
                cb = dlg.child_window(auto_id=aid, control_type="CheckBox").wrapper_object()
            self._set_checkbox_fast(cb, checked=True)

        log.info(f"Checkboxes set in {time.time() - t0:.2f}s")

        dlg.set_focus()
        dlg.type_keys("{ENTER}", set_foreground=False)
        log.info("✓ Next button clicked (Prepare Extensions)")
        