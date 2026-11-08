// Shows a small "Download" pill over videos; click opens a format picker.
(() => {
  if (window.top !== window) return;
  const send = (m) => new Promise((r) => chrome.runtime.sendMessage(m, r));
  const host = document.createElement("div");
  host.style.cssText = "all:initial;position:fixed;z-index:2147483647;top:0;left:0;";
  const root = host.attachShadow({ mode: "closed" });
  root.innerHTML = `
  <style>
    *{box-sizing:border-box;font:13px system-ui,sans-serif}
    .pill{position:fixed;display:none;background:#6c47ff;color:#fff;border:0;border-radius:18px;padding:7px 14px;
          cursor:pointer;box-shadow:0 2px 8px #0006;font-weight:600}
    .pill:hover{background:#5632e0}
    .panel{position:fixed;display:none;width:300px;background:#1c1c24;color:#eee;border-radius:10px;padding:12px;
           box-shadow:0 6px 24px #0008}
    h4{margin:0 0 8px;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .row{display:flex;gap:6px;margin:4px 0}
    button.opt{flex:1;background:#2c2c3a;color:#eee;border:0;border-radius:6px;padding:7px;cursor:pointer}
    button.opt:hover{background:#6c47ff}
    .sec{margin-top:8px;font-size:11px;color:#9a9ab0;text-transform:uppercase}
    .msg{color:#ffb4b4;margin-top:6px}.ok{color:#9fe3a8}
    .x{position:absolute;top:6px;right:10px;cursor:pointer;color:#999}
  </style>
  <button class="pill">⬇ Download</button>
  <div class="panel"><span class="x">✕</span><h4></h4><div class="body">Loading…</div></div>`;
  const pill = root.querySelector(".pill"), panel = root.querySelector(".panel");
  const body = root.querySelector(".body"), title = root.querySelector("h4");
  document.documentElement.appendChild(host);

  let target = null, hideTimer;
  const bigEnough = (v) => { const r = v.getBoundingClientRect(); return r.width > 240 && r.height > 130; };

  function place() {
    if (!target) return;
    const r = target.getBoundingClientRect();
    if (r.bottom < 0 || r.top > innerHeight) { pill.style.display = "none"; return; }
    pill.style.display = "block";
    pill.style.left = Math.max(8, Math.min(innerWidth - 130, r.right - 130)) + "px";
    pill.style.top = Math.max(8, r.top + 10) + "px";
  }
  document.addEventListener("mouseover", (e) => {
    const v = e.target instanceof Element && (e.target.closest("video") ||
      [...document.querySelectorAll("video")].find((x) => bigEnough(x) && x.contains(e.target)));
    if (v && bigEnough(v)) { clearTimeout(hideTimer); target = v; place(); }
    else if (e.target !== host) hideTimer = setTimeout(() => { if (panel.style.display !== "block") pill.style.display = "none"; }, 1500);
  }, true);
  addEventListener("scroll", place, true);
  addEventListener("resize", place);

  const fmtDur = (s) => (s ? `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}` : "");
  const start = (job, label) => send({ type: "download", job: { url: location.href, ...job } }).then((r) => {
    body.innerHTML = r.ok ? `<div class="ok">Started: ${label}</div>` : `<div class="msg"></div>`;
    if (!r.ok) body.firstChild.textContent = r.error;
  });

  pill.onclick = async () => {
    panel.style.display = "block";
    const pr = pill.getBoundingClientRect();
    panel.style.left = Math.max(8, Math.min(innerWidth - 312, pr.right - 300)) + "px";
    panel.style.top = pr.bottom + 8 + "px";
    title.textContent = document.title; body.textContent = "Checking formats…";
    const res = await send({ type: "probe", url: location.href });
    if (!res || !res.ok) { body.innerHTML = '<div class="msg"></div>'; body.firstChild.textContent = res ? res.error : "No response"; return; }
    const d = res.data;
    title.textContent = `${d.title} ${fmtDur(d.duration) && "· " + fmtDur(d.duration)}`;
    body.innerHTML = '<div class="sec">Video</div><div class="row v"></div><div class="sec">Audio only</div><div class="row a"></div>';
    const add = (sel, text, job) => {
      const b = document.createElement("button"); b.className = "opt"; b.textContent = text;
      b.onclick = () => start(job, text); body.querySelector(sel).appendChild(b);
    };
    add(".v", "Best", { kind: "video", title: d.title });
    d.video.slice(0, 5).forEach((v) => add(".v", v.label, { kind: "video", height: v.height, title: d.title }));
    if (d.audio.length) ["mp3", "m4a", "opus"].forEach((c) => add(".a", c.toUpperCase(), { kind: "audio", audio_codec: c, title: d.title }));
    else body.querySelector(".a").textContent = "Install ffmpeg for audio extraction";
  };
  root.querySelector(".x").onclick = () => { panel.style.display = "none"; pill.style.display = "none"; };
})();
