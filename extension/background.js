// All traffic to the local Palwoad service goes through here, so web pages never see the token.
async function cfg() {
  const { port = 9614, token = "", intercept = false } = await chrome.storage.local.get(["port", "token", "intercept"]);
  return { port, token, intercept };
}

async function api(path, method = "GET", body) {
  const { port, token } = await cfg();
  if (!token) throw new Error("Not paired yet: run `palwoad token` and paste the token in Palwoad options.");
  let res;
  try {
    res = await fetch(`http://127.0.0.1:${port}${path}`, {
      method,
      headers: { "X-Palwoad-Token": token, "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error("Can't reach Palwoad. Is `palwoad serve` running?");
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

chrome.runtime.onMessage.addListener((msg, sender, reply) => {
  // Only our own extension pages/content scripts may use the bridge.
  if (sender.id !== chrome.runtime.id) return;
  const run = {
    probe: () => api("/api/probe", "POST", { url: msg.url }),
    download: () => api("/api/downloads", "POST", msg.job),
    list: () => api("/api/downloads"),
    cancel: () => api(`/api/downloads/${encodeURIComponent(msg.id)}/cancel`, "POST"),
    remove: () => api(`/api/downloads/${encodeURIComponent(msg.id)}`, "DELETE"),
  }[msg.type];
  if (!run) return;
  run().then((data) => reply({ ok: true, data }), (e) => reply({ ok: false, error: e.message }));
  return true; // async reply
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({ id: "pl-link", title: "Download link with Palwoad", contexts: ["link", "video", "audio"] });
  chrome.contextMenus.create({ id: "pl-page", title: "Download this page's video with Palwoad", contexts: ["page"] });
});

chrome.contextMenus.onClicked.addListener(async (info) => {
  const url = info.linkUrl || info.srcUrl;
  try {
    if (info.menuItemId === "pl-page") await api("/api/downloads", "POST", { url: info.pageUrl, kind: "video" });
    else if (url) await api("/api/downloads", "POST", { url, kind: "file" });
  } catch (e) {
    console.warn("Palwoad:", e.message);
  }
});

// Optional IDM-style capture of normal browser downloads (off by default; see options).
chrome.downloads.onCreated.addListener(async (item) => {
  const { intercept } = await cfg();
  const url = item.finalUrl || item.url;
  if (!intercept || !/^https?:/.test(url)) return;
  try {
    await api("/api/downloads", "POST", { url, kind: "file", filename: item.filename?.split(/[\\/]/).pop() || undefined });
    chrome.downloads.cancel(item.id, () => chrome.downloads.erase({ id: item.id }));
  } catch {
    /* service not running: let the browser download normally */
  }
});
