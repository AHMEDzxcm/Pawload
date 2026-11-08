"""Local JSON API used by the browser extension and CLI.

Security model: binds to loopback only, requires a secret token on every call
except /api/ping, rejects unexpected Host headers (DNS rebinding), and sends no
CORS headers, so ordinary web pages can neither call nor read it.
"""
import hmac
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, media
from .manager import Manager

MAX_BODY = 1_000_000


def make_server(cfg: dict, manager: Manager) -> ThreadingHTTPServer:
    port = cfg["port"]
    token = cfg["token"]

    class Handler(BaseHTTPRequestHandler):
        server_version = "Palwoad/" + __version__

        def log_message(self, *a):  # quiet
            pass

        def _send(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _guard(self, need_auth=True) -> bool:
            host = (self.headers.get("Host") or "").lower()
            if host not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                self._send(403, {"error": "bad host"})
                return False
            if need_auth:
                given = self.headers.get("X-Palwoad-Token", "")
                if not hmac.compare_digest(given.encode(), token.encode()):
                    self._send(401, {"error": "invalid token"})
                    return False
            return True

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                raise ValueError("body too large")
            return json.loads(self.rfile.read(n) or b"{}")

        def _handle(self, method):
            path = self.path.split("?", 1)[0]
            if not self._guard(need_auth=path != "/api/ping"):
                return
            try:
                if method == "GET" and path == "/api/ping":
                    return self._send(200, {"app": "palwoad", "version": __version__})
                if method == "GET" and path == "/api/downloads":
                    return self._send(200, {"downloads": manager.list(), "ffmpeg": media.has_ffmpeg()})
                if method == "POST" and path == "/api/probe":
                    return self._send(200, media.probe(self._body()["url"]))
                if method == "POST" and path == "/api/downloads":
                    b = self._body()
                    kind = b.get("kind", "file")
                    opts = {k: b[k] for k in ("height", "audio_codec", "filename", "title") if k in b}
                    if isinstance(b.get("headers"), dict):  # e.g. Referer/Cookie captured by the extension
                        opts["headers"] = {str(k): str(v) for k, v in b["headers"].items()
                                           if re.fullmatch(r"[A-Za-z-]+", str(k)) and "\n" not in str(v)}
                    return self._send(200, manager.add(b["url"], kind, **opts).to_dict())
                m = re.fullmatch(r"/api/downloads/(\w+)(/cancel)?", path)
                if m and method == "POST" and m.group(2):
                    return self._send(200 if manager.cancel(m.group(1)) else 404, {})
                if m and method == "DELETE" and not m.group(2):
                    return self._send(200 if manager.remove(m.group(1)) else 404, {})
                self._send(404, {"error": "not found"})
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                self._send(400, {"error": str(e) or "bad request"})
            except Exception as e:  # noqa: BLE001
                self._send(500, {"error": str(e)[:300]})

        def do_GET(self): self._handle("GET")
        def do_POST(self): self._handle("POST")
        def do_DELETE(self): self._handle("DELETE")

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.daemon_threads = True
    return srv
