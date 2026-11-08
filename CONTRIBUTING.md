# Contributing

PRs welcome. Setup: `pip install -e .[dev]`, then `pytest`.

- Keep the core dependency-light (stdlib + yt-dlp).
- Anything touching `server.py` must keep the security model in the README (token, Host check, no CORS) and have a test.
- Extension code must stay free of remote scripts, analytics, and eval.
