const send = (m) => new Promise((r) => chrome.runtime.sendMessage(m, r));
const $ = (id) => document.getElementById(id);
const mb = (n) => (n / 1048576).toFixed(1);

async function refresh() {
  const r = await send({ type: "list" });
  $("err").textContent = r.ok ? "" : r.error;
  if (!r.ok) return;
  const list = $("list"); list.textContent = "";
  for (const j of r.data.downloads.slice().reverse().slice(0, 8)) {
    const d = document.createElement("div"); d.className = "job";
    const t = document.createElement("div"); t.className = "t"; t.textContent = j.title;
    const pct = j.total ? Math.round((100 * j.downloaded) / j.total) : 0;
    const bar = document.createElement("div"); bar.className = "bar"; const i = document.createElement("i"); i.style.width = pct + "%"; bar.append(i);
    const s = document.createElement("div"); s.className = "s";
    s.textContent = j.status + (j.status === "downloading" ? ` · ${pct}% · ${mb(j.speed)} MB/s` : "") + (j.error ? " · " + j.error : "");
    d.append(t, bar, s);
    if (["queued", "downloading", "processing"].includes(j.status)) {
      const c = document.createElement("button"); c.textContent = "Cancel"; c.onclick = () => send({ type: "cancel", id: j.id }).then(refresh); d.append(c);
    }
    list.append(d);
  }
}
const add = async (url, kind) => { const r = await send({ type: "download", job: { url, kind } }); $("err").textContent = r.ok ? "" : r.error; refresh(); };
$("go").onclick = () => $("url").value && add($("url").value, "file");
$("here").onclick = async () => { const [t] = await chrome.tabs.query({ active: true, currentWindow: true }); add(t.url, "video"); };
refresh(); setInterval(refresh, 1000);
