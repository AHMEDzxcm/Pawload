import argparse
import json
import sys
import time
import urllib.request

from . import __version__, config
from .manager import Manager
from .server import make_server


def _api(cfg, method, path, body=None):
    req = urllib.request.Request(f"http://127.0.0.1:{cfg['port']}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Palwoad-Token": cfg["token"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main(argv=None):
    p = argparse.ArgumentParser(prog="palwoad", description="Palwoad download manager")
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd")
    sub.add_parser("serve", help="run the local service the browser extension talks to")
    sub.add_parser("token", help="print the pairing token and port for the extension")
    g = sub.add_parser("get", help="download a URL (starts a one-off service if none is running)")
    g.add_argument("url")
    g.add_argument("--audio", metavar="CODEC", help="extract audio (mp3, m4a, opus, flac, wav)")
    g.add_argument("--height", type=int, help="max video height, e.g. 1080")
    g.add_argument("--file", action="store_true", help="treat as a direct file link, not a video page")
    s = sub.add_parser("set", help="change a setting, e.g. palwoad set download_dir ~/Videos")
    s.add_argument("key", choices=["download_dir", "port", "connections", "max_concurrent"])
    s.add_argument("value")
    a = p.parse_args(argv)
    if a.cmd is None:  # double-clicked the .exe: just run the service
        a.cmd = "serve"

    cfg = config.load()
    if a.cmd == "token":
        print(f"port:  {cfg['port']}\ntoken: {cfg['token']}")
    elif a.cmd == "set":
        cfg[a.key] = a.value if a.key == "download_dir" else int(a.value)
        config.save(cfg)
        print(f"{a.key} = {cfg[a.key]}")
    elif a.cmd == "serve":
        mgr = Manager(cfg)
        srv = make_server(cfg, mgr)
        print(f"Palwoad {__version__} listening on 127.0.0.1:{cfg['port']}\nSaving to {mgr.dest}\n"
              f"Extension pairing  ->  port: {cfg['port']}   token: {cfg['token']}")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            print("\nbye")
    elif a.cmd == "get":
        mgr = Manager(cfg)
        kind = "file" if a.file else ("audio" if a.audio else "video")
        if kind == "video" and not a.file:
            from urllib.parse import urlparse
            if urlparse(a.url).path.rsplit(".", 1)[-1].lower() in ("zip", "iso", "exe", "pdf", "7z", "gz", "tar", "dmg", "deb"):
                kind = "file"
        job = mgr.add(a.url, kind, height=a.height, audio_codec=a.audio or "mp3")
        while job.status in ("queued", "downloading", "processing"):
            pct = f"{job.downloaded * 100 // job.total}%" if job.total else f"{job.downloaded >> 20} MB"
            print(f"\r{job.status:<11}{pct:<8}{job.speed / 1e6:6.2f} MB/s", end="", flush=True)
            time.sleep(0.5)
        print()
        if job.status != "done":
            sys.exit(f"{job.status}: {job.error or ''}")
        print(job.path)


if __name__ == "__main__":
    main()
