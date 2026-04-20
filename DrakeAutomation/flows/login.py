# flows/login.py

class LoginFlow:
    def __init__(self, session):
        self.main = session.main

    def login(self, username: str, password: str):
        self.main.set_focus()

        btn_login = self.main.child_window(
            auto_id="MainWindow_ButtonLogin",
            control_type="Button"
        )

        # No login screen
        if not btn_login.exists(timeout=2):
            return

        username_edit = self.main.child_window(
            auto_id="MainWindow_TextBoxUserName",
            control_type="Edit"
        )

        password_edit = self.main.child_window(
            auto_id="MainWindow_PasswordBoxLoginPassword",
            control_type="Edit"
        )

        if username_edit.window_text() != username:
            username_edit.set_focus()
            username_edit.set_text(username)

        if password_edit.window_text() != password:
            password_edit.set_focus()
            password_edit.set_text(password)

        self.main.type_keys("{ENTER}", set_foreground=False)

        if btn_login.exists(timeout=5):
            raise RuntimeError("Login failed: Check credentials")
