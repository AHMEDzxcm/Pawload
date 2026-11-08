"""Multi-connection, resumable HTTP(S) downloader for direct file links."""
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Dict, Optional

UA = "Mozilla/5.0 (compatible; Palwoad/0.1)"
BLOCK = 256 * 1024


class Cancelled(Exception):
    pass


def sanitize_filename(name: str) -> str:
    name = urllib.parse.unquote(name).replace("\\", "/").split("/")[-1]
    name = re.sub(r'[<>:"|?*\x00-\x1f]', "_", name).strip(" .")
    return name[:200] or "download"


def _open(url, headers, extra=None, method="GET"):
    h = {"User-Agent": UA, **(headers or {}), **(extra or {})}
    return urllib.request.urlopen(urllib.request.Request(url, headers=h, method=method), timeout=30)


def probe(url: str, headers: Optional[Dict[str, str]] = None):
    """Return (final_url, size|None, accepts_ranges, filename)."""
    try:
        r = _open(url, headers, {"Range": "bytes=0-0"})
    except urllib.error.HTTPError as e:
        if e.code == 416:  # empty file
            r = e
        else:
            raise
    with r:
        final = r.geturl()
        size, ranges = None, False
        cr = r.headers.get("Content-Range")
        if r.status == 206 and cr and "/" in cr and cr.rsplit("/", 1)[1].isdigit():
            size, ranges = int(cr.rsplit("/", 1)[1]), True
        elif r.headers.get("Content-Length", "").isdigit():
            size = int(r.headers["Content-Length"])
        cd = r.headers.get("Content-Disposition", "")
        m = re.search(r"filename\*=(?:UTF-8'')?([^;]+)", cd, re.I) or re.search(r'filename="?([^";]+)"?', cd, re.I)
        name = m.group(1).strip() if m else urllib.parse.urlparse(final).path.rsplit("/", 1)[-1]
        return final, size, ranges, sanitize_filename(name)


def unique_path(directory: Path, name: str) -> Path:
    p = directory / name
    stem, suffix, i = p.stem, p.suffix, 1
    while p.exists() or Path(str(p) + ".palwoad").exists():
        p = directory / f"{stem} ({i}){suffix}"
        i += 1
    return p


class Segmented:
    def __init__(self, url, dest_dir, headers=None, connections=8,
                 on_progress: Optional[Callable[[int, Optional[int]], None]] = None,
                 cancel: Optional[threading.Event] = None, filename: Optional[str] = None):
        self.url, self.headers = url, headers or {}
        self.dest_dir = Path(dest_dir)
        self.connections = max(1, connections)
        self.on_progress = on_progress or (lambda d, t: None)
        self.cancel = cancel or threading.Event()
        self.filename = filename
        self.path: Optional[Path] = None
        self._lock = threading.Lock()
        self._done = 0
        self._abort = threading.Event()  # set when one part fails

    # -- helpers ----------------------------------------------------------
    def _check(self):
        if self.cancel.is_set() or self._abort.is_set():
            raise Cancelled()

    def _report(self, n):
        with self._lock:
            self._done += n
            done = self._done
        self.on_progress(done, self.size)

    def _fetch_part(self, part):
        """part = [start, end, pos]; downloads until pos > end. Mutates pos."""
        retries = 0
        while part[2] <= part[1]:
            self._check()
            try:
                with _open(self.url, self.headers, {"Range": f"bytes={part[2]}-{part[1]}"}) as r:
                    if r.status != 206:
                        raise IOError("server ignored Range request")
                    with open(self.path, "r+b") as f:
                        while part[2] <= part[1]:
                            self._check()
                            chunk = r.read(min(BLOCK, part[1] - part[2] + 1))
                            if not chunk:
                                raise IOError("connection closed early")
                            f.seek(part[2])
                            f.write(chunk)
                            part[2] += len(chunk)
                            self._report(len(chunk))
                retries = 0
            except Cancelled:
                raise
            except Exception:
                retries += 1
                if retries > 5:
                    raise
                time.sleep(min(2 ** retries, 10))

    # -- main -------------------------------------------------------------
    def run(self) -> Path:
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        final, size, ranges, name = probe(self.url, self.headers)
        self.url, self.size = final, size
        name = sanitize_filename(self.filename) if self.filename else name
        state = self._load_state(name, size)
        if state:
            self.path, parts = state
        else:
            self.path = unique_path(self.dest_dir, name)
            parts = None

        if not (ranges and size and size > 0):
            return self._single()

        if parts is None:
            n = min(self.connections, max(1, size // (1024 * 1024)))
            step = -(-size // n)
            parts = [[i * step, min(size, (i + 1) * step) - 1, i * step] for i in range(n)]
            with open(self.path, "wb") as f:
                f.truncate(size)
        self._done = sum(p[2] - p[0] for p in parts)
        self.on_progress(self._done, size)

        sidecar = Path(str(self.path) + ".palwoad")
        stop_saver = threading.Event()

        def save():
            while not stop_saver.wait(1.0):
                self._save_state(sidecar, size, parts)

        saver = threading.Thread(target=save, daemon=True)
        saver.start()
        errors = []

        def work(p):
            try:
                self._fetch_part(p)
            except BaseException as e:  # noqa: BLE001
                errors.append(e)
                self._abort.set()  # stop siblings, keep user's cancel flag untouched

        threads = [threading.Thread(target=work, args=(p,), daemon=True) for p in parts]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stop_saver.set()
        saver.join()
        if errors:
            self._save_state(sidecar, size, parts)  # keep for resume
            real = [e for e in errors if not isinstance(e, Cancelled)]
            if self.cancel.is_set() or not real:
                raise Cancelled()
            raise real[0]
        sidecar.unlink(missing_ok=True)
        return self.path

    def _single(self) -> Path:
        tmp = Path(str(self.path) + ".part")
        done = 0
        try:
            with _open(self.url, self.headers) as r, open(tmp, "wb") as f:
                while True:
                    self._check()
                    chunk = r.read(BLOCK)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    self._done = done
                    self.on_progress(done, self.size)
        except BaseException:
            tmp.unlink(missing_ok=True)
            raise
        os.replace(tmp, self.path)
        return self.path

    # -- resume state -----------------------------------------------------
    def _save_state(self, sidecar, size, parts):
        try:
            sidecar.write_text(json.dumps({"url": self.url, "size": size, "parts": parts}))
        except OSError:
            pass

    def _load_state(self, name, size):
        if not size:
            return None
        target = self.dest_dir / name
        sidecar = Path(str(target) + ".palwoad")
        if target.exists() and sidecar.exists():
            try:
                s = json.loads(sidecar.read_text())
                if s["size"] == size and target.stat().st_size == size:
                    return target, s["parts"]
            except (OSError, ValueError, KeyError):
                pass
        return None
