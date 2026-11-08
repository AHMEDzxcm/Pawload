import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from pawload.manager import Manager
from pawload.segmented import Cancelled, Segmented, sanitize_filename
from pawload.server import make_server

DATA = os.urandom(5 * 1024 * 1024 + 123)


class FileHandler(BaseHTTPRequestHandler):
    ranges = True

    def log_message(self, *a): pass

    def do_GET(self):
        rng = self.headers.get("Range")
        m = re.match(r"bytes=(\d+)-(\d*)", rng or "")
        if m and self.ranges:
            s = int(m[1]); e = int(m[2]) if m[2] else len(DATA) - 1
            body = DATA[s:e + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {s}-{e}/{len(DATA)}")
        else:
            body = DATA
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", 'attachment; filename="../evil name.bin"')
        self.end_headers()
        self.wfile.write(body)


class NoRange(FileHandler):
    ranges = False


@pytest.fixture
def origin():
    servers = []

    def start(handler):
        s = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=s.serve_forever, daemon=True).start()
        servers.append(s)
        return f"http://127.0.0.1:{s.server_port}/f"
    yield start
    for s in servers:
        s.shutdown()


def sha(p): return hashlib.sha256(open(p, "rb").read()).hexdigest()


def test_segmented_download_matches(origin, tmp_path):
    p = Segmented(origin(FileHandler), tmp_path, connections=4).run()
    assert sha(p) == hashlib.sha256(DATA).hexdigest()
    assert p.name == "evil name.bin"  # path traversal stripped
    assert not list(tmp_path.glob("*.pawload"))


def test_fallback_without_ranges(origin, tmp_path):
    p = Segmented(origin(NoRange), tmp_path, connections=4).run()
    assert sha(p) == hashlib.sha256(DATA).hexdigest()


def test_cancel(origin, tmp_path):
    ev = threading.Event(); ev.set()
    with pytest.raises(Cancelled):
        Segmented(origin(FileHandler), tmp_path, cancel=ev).run()


def test_sanitize():
    assert sanitize_filename("..\\..\\a:b?.txt") == "a_b_.txt"
    assert sanitize_filename("%2e%2e/x") == "x"


@pytest.fixture
def api(tmp_path):
    s = socket_free_port()
    cfg = {"port": s, "token": "secret", "download_dir": str(tmp_path), "connections": 4, "max_concurrent": 2}
    mgr = Manager(cfg)
    srv = make_server(cfg, mgr)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield cfg
    srv.shutdown()


def socket_free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); return s.getsockname()[1]


def call(cfg, path, method="GET", body=None, token="secret", host=None):
    h = {"X-Pawload-Token": token}
    if host: h["Host"] = host
    r = urllib.request.Request(f"http://127.0.0.1:{cfg['port']}{path}", method=method, headers=h,
                               data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(r) as x:
            return x.status, json.load(x)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


def test_api_auth_and_host(api):
    assert call(api, "/api/ping", token="")[0] == 200
    assert call(api, "/api/downloads", token="wrong")[0] == 401
    assert call(api, "/api/downloads", host="evil.com")[0] == 403  # DNS-rebinding guard
    assert call(api, "/api/downloads")[0] == 200


def test_api_rejects_bad_urls(api):
    for u in ("file:///etc/passwd", "ftp://x/y", "javascript:alert(1)"):
        assert call(api, "/api/downloads", "POST", {"url": u})[0] == 400


def test_api_end_to_end(api, origin, tmp_path):
    code, job = call(api, "/api/downloads", "POST", {"url": origin(FileHandler), "kind": "file"})
    assert code == 200
    for _ in range(100):
        d = call(api, "/api/downloads")[1]["downloads"][0]
        if d["status"] in ("done", "error"): break
        time.sleep(0.1)
    assert d["status"] == "done", d
    assert call(api, f"/api/downloads/{job['id']}", "DELETE")[0] == 200
