import time
from pywinauto import Desktop, findwindows, WindowSpecification
from DrakeAutomation.core.session import DrakeSession
from DrakeAutomation.ui.logger import setup_logger
from DrakeAutomation.config import FOLDER_PRINTER
from datetime import datetime
import os
import re

log = setup_logger("flows.package_pdf")

class PackagePDF:
    def __init__(self, session: DrakeSession, return_type: str= None, FI: bool = False):
        self.app = session.app
        self.main = session.main
        self.form_patterns_FI = None
        self.form_patterns = []
        self.FI = FI
        
        rt = return_type.upper() if return_type else ""
        
        if rt == "1040":
            self.form_patterns = [
                "Form 1040",
            ]
            
        if rt == "1120S":
            self.form_patterns = [
            "Form 1120S",
            "Form 1120S pg 4",
            "Form 1120S pg 5",
            ]
            
        if rt == "1120":
            self.form_patterns = [
            "Form 1120",
            "Form 1120 pg 6",
            ]
            
        if rt == "1065":
            self.form_patterns = [
                "Form 1065",           
                "Form 1065 pg 6"
            ]
        
        if FI == True:
            self.form_patterns_FI = [
                "Filing Instructions",
                "INST",
                "1040ES"
            ]
        
        self.tree_item = ["Federal"]
        self.num_form_selected = 0
        self.reset()
        
    def reset(self):
        self.view_print_entry = None
        self.print_entry = None
        self.win_save_as = None
        self.file_name = None
        self.path = None
        
    def _wait_for_window(self, title_re: str, timeout: int = 60) -> WindowSpecification:
        """Waits for a window matching the title regex and sets it as current."""
        end = time.time() + timeout
        while time.time() < end:
            hwnds = findwindows.find_windows(title_re=title_re)
            if hwnds:
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
    
    def select_forms(self):
        log.info("Selecting forms in View/Print window...")
        self.view_print_entry = self._wait_for_window(
            title_re=r"Drake \d{4} View/Print Client Return"
        )
        self.view_print_entry.set_focus()
        self._check_tree_item()
        
        saved_path = None
        log.info(f"Total forms selected: {self.num_form_selected}")
        if self.num_form_selected > 0:
            log.info("Initiating print dialog (Ctrl+D)...")
            self.view_print_entry.set_focus()
            self.view_print_entry.type_keys("^D")
            time.sleep(1)
            self.print_entry = self._wait_for_window(
                title_re=r"Drake \d{4} - Print Document"
            )
            self.print_pdf()
            self._save_as_pdf()
            self._close_file_pdf()
            saved_path = self.path
        else:
            log.warning("No forms matched keywords. Skipping print.")
            
        if self.view_print_entry.exists():
            log.info("Closing View/Print window...")
            self.view_print_entry.set_focus()
            self.view_print_entry.type_keys("{ESC}")
        return saved_path
    
    def print_pdf(self):
        log.info("Handling Print Document dialog...")
        if self.print_entry:
            self.print_entry.set_focus()
            
            cb_pwd = self.print_entry.child_window(
                title="Password Protect PDF Documents", 
                auto_id="2027", 
                control_type="CheckBox"
                ).wrapper_object()
            
            if cb_pwd.get_toggle_state() == 1:
                log.info("Unchecking 'Password Protect PDF Documents'...")
                cb_pwd.set_focus()
                cb_pwd.toggle()
                
            self.print_entry.set_focus()
            self.print_entry.type_keys("{ENTER}")
            time.sleep(1)

    def _save_as_pdf(self):
        log.info("Handling Save As dialog...")
        if self.print_entry:
            self.win_save_as = self._wait_for_window(
                title_re=r"Save As"
            )
            if self.win_save_as:
                self.win_save_as.set_focus()
                self.win_save_as.type_keys("{END}")

                edit_file_name = self.win_save_as.child_window(
                    title="File name:", 
                    auto_id="1001", 
                    control_type="Edit"
                    ).wrapper_object()
                
                edit_file_name.set_focus()
                self.file_name = edit_file_name.get_value().replace(".pdf", f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
                
                if self.FI == True:
                    self.file_name = self.file_name.replace("Tax Return Documents", "Filing Instructions")
                
                self.path = os.path.normpath(os.path.join(FOLDER_PRINTER, self.file_name))
                
                log.info(f"Saving PDF to: {self.path}")
                
                edit_file_name.set_focus()
                edit_file_name.set_edit_text(self.path)
                
                self.win_save_as.set_focus()
                self.win_save_as.type_keys("{ENTER}")

    def _close_file_pdf(self):
        log.info("Waiting for PDF viewer to close...")
        if not self.file_name:
            return
            
        filename = self.file_name.replace(".pdf", "")
        time.sleep(2)

        safe_filename = re.escape(filename)
        for _ in range(5):
            try:
                hwnds = findwindows.find_windows(title_re=f".*{safe_filename}.*")

                if hwnds:
                    for hwnd in hwnds:
                        try:
                            win = Desktop(backend="uia").window(handle=hwnd)
                            title = win.window_text()
                            log.info(f"Closing PDF viewer window: {title}")
                            win.close()
                            return
                        except Exception:
                            pass
            except Exception:
                pass
            time.sleep(0.5)    
        log.warning("PDF viewer window not found or could not be closed.")

    def _check_tree_item(self) -> None:
        log.info("Checking tree items for forms...")

        patterns = set(self.form_patterns)

        for category in self.tree_item:
            log.info(f"Checking category: {category}")
            tree_item_ctrl = self.view_print_entry.child_window(title=category, control_type="TreeItem")

            if not tree_item_ctrl.exists():
                continue

            children = tree_item_ctrl.children(control_type="TreeItem")

            matched_items = []
            matched_names = []
            for it in children:
                name = it.window_text()
                if name in patterns:
                    matched_items.append(it)
                    matched_names.append(name)

            count = len(matched_items)
            self.num_form_selected += count

            if count > 0:
                log.info(f"Found {count} forms in '{category}': {matched_names}")

            for it, name in zip(matched_items, matched_names):
                log.info(f"Selecting form: {name}")
                it.set_focus()
                it.type_keys("{SPACE}")        
        
        if self.form_patterns_FI:
            log.info("Checking tree items for Filing Instructions...")
            tree_items = self.view_print_entry.descendants(control_type="TreeItem")

            items_by_text = {}
            for it in tree_items:
                txt = it.window_text()
                if any(p in txt for p in self.form_patterns_FI):
                    items_by_text.setdefault(txt, []).append(it)

            filtered_texts = [t for t, lst in items_by_text.items() for _ in lst]
            count = len(filtered_texts)
            self.num_form_selected += count
            log.info(f"Found {count} Filing Instructions: {filtered_texts}")

            for text, items in items_by_text.items():
                if len(items) == 1:
                    log.info(f"Selecting Filing Instructions: {text}")
                else:
                    log.info(f"Selecting {len(items)} Filing Instructions: {text}")

                for idx, item in enumerate(items):
                    item.set_focus()
                    item.type_keys("{SPACE}")