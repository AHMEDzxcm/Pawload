"""Settings and the pairing token, stored in a per-user config directory."""
import json
import os
import secrets
import sys
from pathlib import Path

DEFAULTS = {
    "port": 9614,
    "download_dir": str(Path.home() / "Downloads" / "Pawload"),
    "connections": 8,
    "max_concurrent": 3,
}


def config_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return Path(os.environ.get("PAWLOAD_HOME", base / "pawload"))


def load() -> dict:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / "config.json"
    cfg = dict(DEFAULTS)
    if path.exists():
        try:
            cfg.update(json.loads(path.read_text()))
        except (OSError, ValueError):
            pass
    if not cfg.get("token"):
        cfg["token"] = secrets.token_urlsafe(24)
        save(cfg)
    return cfg


def save(cfg: dict) -> None:
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    path = d / "config.json"
    path.write_text(json.dumps(cfg, indent=2))
    try:
        path.chmod(0o600)  # the token is a secret
    except OSError:
        pass
