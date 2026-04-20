# drake/ui/waits.py

import time
import re
from pywinauto import findwindows
from pywinauto.timings import wait_until, TimeoutError
from DrakeAutomation.ui.logger import setup_logger

log = setup_logger("ui.waits")

# ---------------------------
# Generic safe wait
# ---------------------------

def safe_wait(predicate, timeout=30, interval=0.5, desc="condition"):
    log.info(f"WAIT start: {desc} (timeout={timeout}s)")

    def _wrapped():
        try:
            ok = predicate()
            log.debug(f"WAIT check [{desc}] -> {ok}")
            return ok
        except Exception as e:
            log.debug(f"WAIT check [{desc}] exception: {e}")
            return False

    try:
        wait_until(timeout, interval, _wrapped)
        log.info(f"WAIT done: {desc}")
    except TimeoutError:
        log.error(f"WAIT timeout: {desc}")
        raise


# ---------------------------
# Window-level waits
# ---------------------------

def wait_main_window(app, title_re=r"Drake \d{4} Tax Software", timeout=60):
    log.info(f"Wait main window title_re='{title_re}'")

    hwnd = _wait_window_handle(app, title_re, timeout)
    win = app.window(handle=hwnd)
    win.wait("visible enabled ready", timeout=10)

    log.info("Main window ready")
    return win


def wait_data_entry(app, client_id= None, timeout=60):
    log.info("Wait Data Entry window")

    if client_id:
        # title_re = r"DRAKE \d{4} - Data Entry \(" + str(client_id)
        title_re = r"Drake \d{4} - Data Entry \(" + str(client_id)
    else:
        # title_re = r"DRAKE \d{4} - Data Entry"
        title_re = r"Drake \d{4} - Data Entry"
    hwnd = _wait_window_handle(app, title_re, timeout)
    win = app.window(handle=hwnd)
    win.wait("visible enabled ready", timeout=10)

    log.info("Data Entry window ready")
    return win


def check_client_data_entry(app, client_id=None, timeout=5):
    """
    Check if the main Client Data Entry window (the form list) is open and ready.
    This is identified by having a 'menuScreenWindow' but NOT a 'taxScreenWindow'.
    Returns window object if found, None otherwise.
    """
    log.info(f"Checking for main Client Data Entry window (timeout={timeout}s)")
    
    end = time.time() + timeout
    while time.time() < end:
        try:
            if client_id:
                title_re = r"Drake \d{4} - Data Entry \(" + str(client_id)
            else:
                title_re = r"Drake \d{4} - Data Entry"
            hwnds = findwindows.find_windows(title_re=title_re, top_level_only=True)
            if hwnds:
                for hwnd in hwnds:
                    try:
                        win = app.window(handle=hwnd)
                        # Check for the Search Box (MenuScreenWindow_TextBoxSearch)
                        # This confirms we are in the Data Entry window structure
                        if win.child_window(auto_id="MenuScreenWindow_TextBoxSearch").exists() and \
                           not win.child_window(auto_id="taxScreenWindow").exists():
                            if win.is_visible() and win.is_enabled():
                                log.info("Main Client Data Entry window is READY")
                                return win
                    except Exception:
                        continue
        except Exception:
            pass
        time.sleep(0.2)

    log.info("Main Client Data Entry window is NOT READY")
    return None


def check_form_is_open(app, form_name, client_id=None, timeout=2):
    """
    Check if a specific Data Entry form is already open.
    Returns the window object if found and ready, otherwise None.
    """
    log.info(f"Checking if form '{form_name}' is already open (timeout={timeout}s)")
    
    end_time = time.time() + timeout
    while time.time() < end_time:
        try:
            if client_id:
                title_re = r"Drake \d{4} - Data Entry \(" + str(client_id)
            else:
                title_re = r"Drake \d{4} - Data Entry"
            hwnds = findwindows.find_windows(title_re=title_re, top_level_only=True)
            if not hwnds:
                time.sleep(0.2)
                continue

            for hwnd in hwnds:
                try:
                    win = app.window(handle=hwnd)
                    # A form window has auto_id="taxScreenWindow" and contains the form name text
                    if win.child_window(auto_id="taxScreenWindow").exists():
                        if win.is_visible() and win.is_enabled() and _has_form(win, form_name):
                            log.info(f"Form '{form_name}' is already open.")
                            return win
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(0.2)

    log.info(f"Form '{form_name}' is not currently open.")
    return None


def wait_form(app, form_name, client_id=None, timeout=60):
    log.info(f"Wait form: {form_name}")

    if not form_name:
        log.warning("form_name is empty - waiting for any Data Entry form")

    # 1. Data Entry window
    if client_id:
        title_re = r"Drake \d{4} - Data Entry \(" + str(client_id)
    else:
        title_re = r"Drake \d{4} - Data Entry"
    hwnd = _wait_window_handle(app, title_re, timeout)
    win = app.window(handle=hwnd)

    # Retry wait if UIA fails (e.g. COMError)
    for i in range(3):
        try:
            win.wait("visible enabled ready", timeout=10)
            break
        except Exception as e:
            log.warning(f"Window wait failed (attempt {i+1}): {e}")
            if i == 2: raise
            time.sleep(1)
            try:
                hwnd = _wait_window_handle(app, title_re, timeout=5)
                win = app.window(handle=hwnd)
            except:
                pass

    log.debug("Data Entry window attached")

    # 2. Form loaded inside window - with debug output
    if form_name:
        def _form_loaded():
            ok = _has_form(win, form_name)
            if not ok:
                log.debug(f"Form '{form_name}' not loaded yet...")
            return ok

        try:
            wait_until(timeout, 0.5, _form_loaded)
        except TimeoutError:
            log.error(f"Timeout waiting for form: {form_name}")
            log.error("Proceeding anyway - form may still be loading...")
            # Uncomment to raise error: raise

    log.info(f"Form ready: {form_name if form_name else 'Data Entry'}")
    return win


# ---------------------------
# Internal helpers
# ---------------------------

def _wait_window_handle(app, title_re, timeout):
    log.info(f"Searching window: title_re='{title_re}'")
    main_drake_window_title_re = r"Drake \d{4} Tax Software"

    end = time.time() + timeout
    while time.time() < end:
        try:
            # 1. Check if the desired window exists.
            hwnds = findwindows.find_windows(title_re=title_re)
            if hwnds:
                log.info(f"Window found: hwnd={hwnds[0]}")
                return hwnds[0]
            
            log.debug("Window not found yet, checking for popups...")

            # 2. If not found, check for and dismiss unexpected pop-up windows.
            try:
                top_win = app.top_window()
                top_title = top_win.window_text()

                # If the top window is the target, it should be found on the next loop.
                if re.match(title_re, top_title):
                    time.sleep(0.5) # Give it a moment to become fully available
                    continue

                # If the top window is not the target and not the main Drake window, it's likely a popup.
                # Also ignore "Open / Create Returns" dialog as it might be in the process of closing/opening
                if not re.match(main_drake_window_title_re, top_title) and "Open / Create Returns" not in top_title:
                    log.warning(f"Unexpected window found: '{top_title}'. Pressing ESC.")
                    top_win.set_focus()
                    top_win.type_keys("{ESC}")
                    time.sleep(0.5) # Allow time for the window to close
                    continue # Retry the loop immediately
            except Exception as e:
                log.debug(f"Error while checking/dismissing top window: {e}")

        except Exception as e:
            log.debug(f"find_windows exception: {e}")

        time.sleep(0.2)

    log.error(f"Window not found: {title_re}")
    raise TimeoutError(f"Window not found: {title_re}")


def _has_form(win, form_name):
    """
    Detect form inside Data Entry window by visible Text
    Made more resilient to COMError.
    """
    # First, check the window title itself.
    if form_name.lower() in win.window_text().lower():
        log.debug(f"Form marker matched in window title: '{win.window_text()}'")
        return True

    # If not in title, search for a static text control with retries.
    for i in range(3):  # Retry up to 3 times
        try:
            texts = win.descendants(control_type="Text")
            all_texts = []
            for t in texts:
                try:
                    txt = t.window_text().strip()
                    if txt:
                        all_texts.append(txt)
                        if form_name.lower() in txt.lower():
                            log.debug(f"Form marker matched in text control: '{txt}'")
                            return True
                except Exception:
                    pass  # Ignore transient elements
            log.debug(f"Form '{form_name}' not found in this attempt. Available texts: {all_texts[:10]}")
            return False
        except Exception as e:
            log.warning(f"Exception in _has_form (attempt {i+1}/3): {e}. Retrying in 1s...")
            time.sleep(1)

    log.error(f"Could not execute 'win.descendants()' for form '{form_name}' after retries.")
    return False
