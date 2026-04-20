# core/app.py
from pywinauto import Application, findwindows
import win32gui, win32process, time
from DrakeAutomation.core.session import DrakeSession
from DrakeAutomation.config import DRAKE_TITLE

class OpenDrake:
    def __init__(self, exe, cwd, title: str= None):
        self.exe = exe
        self.cwd = cwd
        if title is None:
            title = DRAKE_TITLE
        self.title = title

    def _find_main_hwnd(self, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            for hwnd in findwindows.find_windows():
                if self.title in win32gui.GetWindowText(hwnd):
                    return hwnd
            time.sleep(0.5)
        raise TimeoutError("Drake window not found")

    def open(self):
        try:
            hwnd = self._find_main_hwnd(5)
            app = Application(backend="uia").connect(handle=hwnd)
        except TimeoutError:
            app = Application(backend="uia").start(
                cmd_line=f'"{self.exe}"',
                work_dir=self.cwd
            )
            hwnd = self._find_main_hwnd()

        main = app.window(handle=hwnd)
        return DrakeSession(app, main)
