# core/session.py
from pywinauto import Application

class DrakeSession:
    def __init__(self, app: Application, main_window):
        self.app = app
        self.main = main_window

    def focus(self):
        self.main.wait("visible enabled ready", timeout=10)
        self.main.set_focus()
