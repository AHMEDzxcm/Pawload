import io
import json

from palwoad import native


def test_framing_roundtrip():
    buf = io.BytesIO()
    native.write_message(buf, {"type": "hello", "n": 1})
    buf.seek(0)
    assert native.read_message(buf) == {"type": "hello", "n": 1}
    assert native.read_message(buf) is None


def test_hello_returns_pairing(tmp_path, monkeypatch):
    monkeypatch.setenv("PALWOAD_HOME", str(tmp_path))
    monkeypatch.setattr(native, "service_alive", lambda cfg: True)
    r = native.handle({"type": "hello"})
    assert r["ok"] and r["port"] == 9614 and len(r["token"]) > 20


def test_unknown_request_gets_no_token(tmp_path, monkeypatch):
    monkeypatch.setenv("PALWOAD_HOME", str(tmp_path))
    r = native.handle({"type": "give me the token"})
    assert r == {"ok": False, "error": "unknown request"}


def test_manifest_only_allows_our_extension():
    m = native.manifest("C:/x/palwoad-host.exe")
    assert m["allowed_origins"] == [f"chrome-extension://{native.EXT_ID}/"]
    assert m["type"] == "stdio" and m["name"] == "com.palwoad.host"


def test_extension_id_matches_manifest_key():
    import base64, hashlib, pathlib
    mf = json.loads((pathlib.Path(__file__).parents[1] / "extension" / "manifest.json").read_text())
    h = hashlib.sha256(base64.b64decode(mf["key"])).hexdigest()[:32]
    assert "".join(chr(ord("a") + int(c, 16)) for c in h) == native.EXT_ID
