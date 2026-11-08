"""Start Palwoad with Windows (per-user, no admin)."""
import sys

_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY) as k:
            winreg.QueryValueEx(k, "Palwoad")
        return True
    except OSError:
        return False


def set_enabled(on: bool) -> None:
    if sys.platform != "win32":
        return
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, "Palwoad", 0, winreg.REG_SZ, f'"{sys.executable}"')
        else:
            try:
                winreg.DeleteValue(k, "Palwoad")
            except OSError:
                pass
