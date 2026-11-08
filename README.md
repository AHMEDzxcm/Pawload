# 🐾 Pawload

A free, open-source download manager. Fast multi-connection downloads for any file, one-click video/audio
grabbing from YouTube and ~1800 other sites (via [yt-dlp](https://github.com/yt-dlp/yt-dlp)), and a browser
extension that puts a **Download** button right on the video.

MIT licensed · no telemetry · no accounts · nothing leaves your machine except the downloads you ask for.

## How it works

```
Browser extension ──(token-authenticated, 127.0.0.1 only)──▶ pawload service ──▶ yt-dlp / segmented downloader ──▶ your disk
```

- **`src/pawload`** – the Python service and CLI. Direct links use a resumable segmented downloader
  (up to 8 parallel connections); video pages go through yt-dlp; ffmpeg handles merging and audio extraction.
- **`extension/`** – Manifest V3 extension (Chrome, Edge, Brave, Chromium). Hover a video → **⬇ Download** pill →
  pick Best / 1080p / 720p… or MP3 / M4A / Opus. Also: toolbar popup with live progress, right-click menu,
  and optional capture of normal browser downloads.

## Install

Requires Python 3.9+. [ffmpeg](https://ffmpeg.org/) is recommended (needed for 1080p+ merging and audio extraction).

```bash
git clone https://github.com/ahmedzxcm/pawload && cd pawload
pip install .
pawload serve          # keep this running (or add it to your startup items)
pawload token          # shows the port + pairing token
```

Load the extension: open `chrome://extensions` → enable *Developer mode* → *Load unpacked* → select `extension/`.
Open its **Options**, paste the token, save. Done.

### CLI

```bash
pawload get https://example.com/big.iso            # segmented file download
pawload get https://www.youtube.com/watch?v=...    # best video+audio
pawload get URL --height 720
pawload get URL --audio mp3
pawload set download_dir ~/Videos
```

Files land in `~/Downloads/Pawload` by default.

## Security model

The extension needs a local service, so that service is locked down:

- listens on **127.0.0.1 only**;
- every call except `/api/ping` needs the random **token** (stored `0600` in your config dir);
- the `Host` header is checked (blocks DNS-rebinding), and **no CORS headers** are sent, so ordinary websites can't use or read it;
- only `http(s)` URLs are accepted; server-supplied filenames are stripped of paths;
- the extension keeps the token in its background worker; web pages never see it.

Report vulnerabilities privately via GitHub Security Advisories.

## Status & roadmap

v0.1 is an early MVP. Works / tested: segmented + resumable downloads, queue, local API and its auth, CLI.
Needs more real-world testing: the extension UI and the yt-dlp path across sites. Ideas: Firefox build,
packaged installers with autostart, pause/resume in UI, scheduler, speed limit, playlists, cookies from browser.

## Legal

Pawload is a tool; you are responsible for what you download. Respect copyright and site terms of service.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). `pip install -e .[dev] && pytest`.
