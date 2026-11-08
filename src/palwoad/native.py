"""Browser <-> Palwoad pairing without any copy/paste (Chrome 'native messaging').

The installer registers a tiny helper (palwoad-host.exe) with Chrome, Edge, Brave and
Chromium. Only the Palwoad extension (fixed ID below) is allowed by the browser to talk
to it, so ordinary web pages can never obtain the service token.
"""
import json
import struct
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from . import config

EXT_ID = "jjdbheiinbebhgejboaolhfibkemdicp"
HOST_NAME = "com.palwoad.host"
_REG_KEYS = (
    r"Software\Google\Chrome\NativeMessagingHosts",
    r"Software\Microsoft\Edge\NativeMessagingHosts",
    r"Software\BraveSoftware\Brave-Browser\NativeMessagingHosts",
    r"Software\Chromium\NativeMessagingHosts",
)


def read_message(stream):
    raw = stream.read(4)
    if len(raw) < 4:
        return None
    (n,) = struct.unpack("<I", raw)
    return json.loads(stream.read(n).decode("utf-8"))


def write_message(stream, obj):
    data = json.dumps(obj).encode("utf-8")
    stream.write(struct.pack("<I", len(data)) + data)
    stream.flush()


def service_alive(cfg) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{cfg['port']}/api/ping", timeout=1) as r:
            return json.load(r).get("app") == "palwoad"
    except Exception:
        return False


def start_service() -> bool:
    """Launch Palwoad.exe (it sits next to the helper) detached and hidden."""
    exe = Path(sys.executable).resolve().parent / "Palwoad.exe"
    if not exe.is_file():
        return False
    flags = (0x00000008 | 0x08000000) if sys.platform == "win32" else 0  # DETACHED | NO_WINDOW
    subprocess.Popen([str(exe)], creationflags=flags, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def handle(msg) -> dict:
    if not isinstance(msg, dict) or msg.get("type") != "hello":
        return {"ok": False, "error": "unknown request"}
    cfg = config.load()
    if not service_alive(cfg):
        start_service()
        for _ in range(40):
            if service_alive(cfg):
                break
            time.sleep(0.25)
    return {"ok": True, "port": cfg["port"], "token": cfg["token"], "alive": service_alive(cfg)}


def run_host(stdin=None, stdout=None):
    stdin = stdin or sys.stdin.buffer
    stdout = stdout or sys.stdout.buffer
    while True:
        msg = read_message(stdin)
        if msg is None:
            return
        write_message(stdout, handle(msg))


def manifest(host_path: str) -> dict:
    return {
        "name": HOST_NAME,
        "description": "Palwoad pairing helper",
        "path": host_path,
        "type": "stdio",
        "allowed_origins": [f"chrome-extension://{EXT_ID}/"],
    }


def register(host_path: str) -> Path:
    """Write the host manifest and point every Chromium browser at it (per-user, no admin)."""
    d = config.config_dir()
    d.mkdir(parents=True, exist_ok=True)
    mpath = d / "native-host.json"
    mpath.write_text(json.dumps(manifest(host_path), indent=2))
    if sys.platform == "win32":
        import winreg
        for key in _REG_KEYS:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"{key}\{HOST_NAME}") as k:
                winreg.SetValue(k, "", winreg.REG_SZ, str(mpath))
    return mpath


def unregister():
    if sys.platform == "win32":
        import winreg
        for key in _REG_KEYS:
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, rf"{key}\{HOST_NAME}")
            except OSError:
                pass
    try:
        (config.config_dir() / "native-host.json").unlink()
    except OSError:
        pass


def host_main(argv):
    if "--register" in argv:
        print(register(str(Path(sys.executable).resolve())))
    elif "--unregister" in argv:
        unregister()
    else:
        run_host()
