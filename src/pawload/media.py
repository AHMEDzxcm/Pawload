"""Video/audio extraction for YouTube and the ~1800 other sites yt-dlp supports."""
import shutil
import threading
from pathlib import Path
from typing import Callable, Optional

from .segmented import Cancelled

AUDIO_CODECS = ("mp3", "m4a", "opus", "flac", "wav")


def _ydl(opts):
    import yt_dlp
    base = {"quiet": True, "no_warnings": True, "noplaylist": True}
    return yt_dlp.YoutubeDL({**base, **opts})


def has_ffmpeg() -> bool:
    return shutil.which("ffmpeg") is not None


def probe(url: str) -> dict:
    """Describe what can be downloaded from a page URL."""
    with _ydl({"skip_download": True}) as ydl:
        info = ydl.extract_info(url, download=False)
    if info.get("_type") == "playlist" and info.get("entries"):
        info = next(e for e in info["entries"] if e)
    fmts = info.get("formats") or []
    available = {f["height"] for f in fmts if f.get("height") and f.get("vcodec") not in (None, "none")}
    # Offer every real height we actually saw, highest first.
    video = [{"height": h, "label": f"{h}p"} for h in sorted(available, reverse=True)]
    return {
        "title": info.get("title") or url,
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "video": video,
        "audio": [{"codec": c, "label": c.upper()} for c in AUDIO_CODECS] if has_ffmpeg() else [],
        "ffmpeg": has_ffmpeg(),
    }


def download(url: str, dest_dir: Path, kind: str = "video", height: Optional[int] = None,
             audio_codec: str = "mp3", on_progress: Callable[[int, Optional[int], Optional[float]], None] = None,
             on_status: Callable[[str], None] = None, cancel: Optional[threading.Event] = None) -> Path:
    cancel = cancel or threading.Event()
    on_progress = on_progress or (lambda d, t, s: None)
    ffmpeg = has_ffmpeg()
    opts = {"outtmpl": str(dest_dir / "%(title).150B [%(id)s].%(ext)s"), "restrictfilenames": False,
            "windowsfilenames": True, "continuedl": True, "concurrent_fragment_downloads": 4}
    if kind == "audio":
        if not ffmpeg:
            raise RuntimeError("ffmpeg is required for audio extraction")
        if audio_codec not in AUDIO_CODECS:
            raise ValueError(f"unsupported audio codec {audio_codec!r}")
        opts["format"] = "bestaudio/best"
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio", "preferredcodec": audio_codec, "preferredquality": "0"}]
    else:
        cap = f"[height<={int(height)}]" if height else ""
        opts["format"] = f"bv*{cap}+ba/b{cap}" if ffmpeg else f"b{cap}/b"
        if ffmpeg:
            opts["merge_output_format"] = "mp4"

    result = {}

    def hook(d):
        if cancel.is_set():
            raise Cancelled()
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            on_progress(d.get("downloaded_bytes", 0), total, d.get("speed"))
        elif d["status"] == "finished" and on_status:
            on_status("processing")

    def post_hook(d):
        if d["status"] == "finished":
            result["path"] = d["info_dict"].get("filepath") or d["info_dict"].get("_filename")

    opts["progress_hooks"] = [hook]
    opts["postprocessor_hooks"] = [post_hook]
    import yt_dlp
    try:
        with _ydl(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            path = result.get("path") or ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as e:
        if cancel.is_set():
            raise Cancelled() from e
        raise
    return Path(path)
