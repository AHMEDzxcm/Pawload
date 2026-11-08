"""Background app: runs the service and shows a system-tray icon."""
import os
import sys
import threading

from . import __version__, autostart
from .manager import Manager
from .server import make_server


def _icon_image():
    from PIL import Image, ImageDraw
    im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((2, 2, 62, 62), fill=(37, 99, 235, 255))
    d.rectangle((27, 12, 37, 34), fill="white")
    d.polygon([(16, 32), (48, 32), (32, 50)], fill="white")
    d.rectangle((16, 52, 48, 56), fill="white")
    return im


def run(cfg) -> None:
    mgr = Manager(cfg)
    try:
        srv = make_server(cfg, mgr)
    except OSError:
        return  # already running
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    import pystray

    def open_folder(icon, item):
        if sys.platform == "win32":
            os.startfile(str(mgr.dest))

    def toggle_start(icon, item):
        autostart.set_enabled(not autostart.is_enabled())

    def quit_(icon, item):
        srv.shutdown()
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem(f"Palwoad {__version__}: running", None, enabled=False),
        pystray.MenuItem("Open downloads folder", open_folder, default=True),
        pystray.MenuItem("Start with Windows", toggle_start, checked=lambda item: autostart.is_enabled()),
        pystray.MenuItem("Quit", quit_),
    )
    pystray.Icon("palwoad", _icon_image(), "Palwoad", menu).run()
