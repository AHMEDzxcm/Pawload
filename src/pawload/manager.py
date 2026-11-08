"""Job queue: runs downloads on a small thread pool and tracks their state."""
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from . import media
from .segmented import Cancelled, Segmented

ACTIVE = ("queued", "downloading", "processing")


class Job:
    def __init__(self, url, kind, **opts):
        self.id = uuid.uuid4().hex[:12]
        self.url, self.kind, self.opts = url, kind, opts
        self.title = opts.get("title") or url
        self.status = "queued"
        self.downloaded = 0
        self.total: Optional[int] = None
        self.speed = 0.0
        self.error: Optional[str] = None
        self.path: Optional[str] = None
        self.cancel = threading.Event()
        self._t, self._b = time.monotonic(), 0

    def progress(self, done, total, speed=None):
        self.status = "downloading"
        self.downloaded, self.total = done, total
        if speed is None:  # compute a smoothed speed ourselves
            now = time.monotonic()
            if now - self._t >= 0.5:
                inst = (done - self._b) / (now - self._t)
                self.speed = inst if not self.speed else 0.7 * self.speed + 0.3 * inst
                self._t, self._b = now, done
        else:
            self.speed = speed

    def to_dict(self):
        eta = None
        if self.total and self.speed and self.status == "downloading":
            eta = int((self.total - self.downloaded) / self.speed)
        return {"id": self.id, "url": self.url, "kind": self.kind, "title": self.title,
                "status": self.status, "downloaded": self.downloaded, "total": self.total,
                "speed": self.speed, "eta": eta, "error": self.error, "path": self.path}


def validate_url(url: str) -> str:
    u = urlparse(url)
    if u.scheme not in ("http", "https") or not u.netloc:
        raise ValueError("only http(s) URLs are supported")
    return url


class Manager:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.jobs: Dict[str, Job] = {}
        self.order: List[str] = []
        self.pool = ThreadPoolExecutor(max_workers=cfg["max_concurrent"])
        self.lock = threading.Lock()

    @property
    def dest(self) -> Path:
        return Path(self.cfg["download_dir"]).expanduser()

    def add(self, url: str, kind: str = "file", **opts) -> Job:
        validate_url(url)
        if kind not in ("file", "video", "audio"):
            raise ValueError("kind must be file, video or audio")
        job = Job(url, kind, **opts)
        with self.lock:
            self.jobs[job.id] = job
            self.order.append(job.id)
        self.pool.submit(self._run, job)
        return job

    def _run(self, job: Job):
        if job.cancel.is_set():
            job.status = "cancelled"
            return
        job.status = "downloading"
        try:
            o = job.opts
            if job.kind == "file":
                p = Segmented(job.url, self.dest, headers=o.get("headers"),
                              connections=self.cfg["connections"], on_progress=job.progress,
                              cancel=job.cancel, filename=o.get("filename")).run()
            else:
                p = media.download(job.url, self.dest, kind=job.kind, height=o.get("height"),
                                   audio_codec=o.get("audio_codec", "mp3"), on_progress=job.progress,
                                   on_status=lambda s: setattr(job, "status", s), cancel=job.cancel)
            job.path, job.status = str(p), "done"
            job.title = Path(p).name
        except Cancelled:
            job.status = "cancelled"
        except Exception as e:  # noqa: BLE001
            job.status, job.error = "error", str(e)[:500]

    def list(self) -> List[dict]:
        return [self.jobs[i].to_dict() for i in self.order]

    def cancel(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job:
            return False
        job.cancel.set()
        if job.status == "queued":
            job.status = "cancelled"
        return True

    def remove(self, job_id: str) -> bool:
        job = self.jobs.get(job_id)
        if not job or job.status in ACTIVE:
            return False
        with self.lock:
            self.jobs.pop(job_id, None)
            self.order.remove(job_id)
        return True
