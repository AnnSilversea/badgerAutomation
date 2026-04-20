from __future__ import annotations

from datetime import datetime
import os
import time
from typing import Iterable, Optional

from pywinauto import Desktop


def safe_invoke(ctrl, desc: str = "control") -> None:
    """
    Prefer non-mouse UIA actions so user can move mouse freely.
    Falls back to click_input only if needed.
    """
    last_err: Exception | None = None
    for fn_name in ("invoke", "click"):
        try:
            fn = getattr(ctrl, fn_name, None)
            if callable(fn):
                fn()
                return
        except Exception as e:
            last_err = e

    # Last resort: click_input (uses mouse)
    try:
        ctrl.click_input()
        return
    except Exception as e:
        last_err = e

    raise RuntimeError(f"Failed to activate {desc}. Last error: {last_err}")


def safe_focus(ctrl, desc: str = "control", attempts: int = 3) -> None:
    """
    Best-effort focus without using the mouse.
    Useful when you must send keys to a specific window/control.
    """
    last_err: Exception | None = None
    for _ in range(max(1, attempts)):
        try:
            ctrl.set_focus()
            return
        except Exception as e:
            last_err = e
            time.sleep(0.2)
    raise RuntimeError(f"Failed to set focus to {desc}. Last error: {last_err}")


def safe_set_edit_text(edit, text: str) -> None:
    """Set text without focusing / mouse if possible."""
    try:
        edit.set_edit_text(text)
        return
    except Exception:
        # Fallback: focus + type_keys (still no mouse)
        try:
            safe_focus(edit, desc="edit control")
        except Exception:
            pass
        try:
            edit.type_keys("^a{DELETE}", set_foreground=False)
        except Exception:
            pass
        edit.type_keys(text, with_spaces=True, set_foreground=False)


def window_title(w) -> str:
    """Get best-effort window title/name."""
    try:
        ei = getattr(w, "element_info", None)
        name = getattr(ei, "name", "") if ei else ""
        if name:
            return name
    except Exception:
        pass
    try:
        return (w.window_text() or "").strip()
    except Exception:
        return ""


def list_visible_windows_snapshot(tag: str, app_pid: Optional[int] = None) -> str:
    """
    Debug helper: write visible windows snapshot to print_identifiers/.
    Does NOT filter by pid (but marks same_pid=True/False).
    """
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("./print_identifiers", exist_ok=True)
    path = f"./print_identifiers/{tag}_{ts}.txt"

    desk = Desktop(backend="uia")
    try:
        wins = desk.windows(visible_only=True)
    except Exception:
        wins = []

    lines: list[str] = []
    for w in wins:
        try:
            ei = getattr(w, "element_info", None)
            w_pid = getattr(ei, "process_id", None) if ei else None
            auto_id = getattr(ei, "automation_id", "") if ei else ""
            ctype = getattr(ei, "control_type", "") if ei else ""
            title = window_title(w)
            same_pid = (app_pid is not None and w_pid == app_pid)
            lines.append(
                f"- title={title!r} auto_id={auto_id!r} control_type={ctype!r} pid={w_pid!r} same_pid={same_pid}"
            )
        except Exception:
            continue

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) if lines else "(no visible windows)\n")

    return path


def dump_visible_window_titles(tag: str, include_empty: bool = False) -> str:
    """Dump titles of all visible top-level windows to print_identifiers/."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("./print_identifiers", exist_ok=True)
    path = f"./print_identifiers/{tag}_{ts}.txt"

    desk = Desktop(backend="uia")
    try:
        wins = desk.windows(visible_only=True)
    except Exception:
        wins = []

    titles: list[str] = []
    for w in wins:
        try:
            t = window_title(w)
            if t or include_empty:
                titles.append(t)
        except Exception:
            continue

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(titles) if titles else "(no visible windows)\n")

    return path


def wait_until(predicate, timeout: float = 20.0, interval: float = 0.2):
    """Simple polling wait; returns predicate result when truthy."""
    end = time.time() + timeout
    last = None
    while time.time() < end:
        try:
            last = predicate()
            if last:
                return last
        except Exception:
            pass
        time.sleep(interval)
    return None

