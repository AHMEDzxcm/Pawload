// All traffic to the local Palwoad service goes through here, so web pages never see the token.
async function cfg() {
  const { port = 9614, token = "", intercept = false } = await chrome.storage.local.get(["port", "token", "intercept"]);
  return { port, token, intercept };
}

// Automatic pairing: the installed helper (native messaging) hands us the port + token and
// starts the Palwoad service if it isn't running. Nothing for the user to copy or paste.
async function pair() {
  const r = await new Promise((resolve) => {
    chrome.runtime.sendNativeMessage("com.palwoad.host", { type: "hello" }, (resp) => {
      resolve(chrome.runtime.lastError ? null : resp);
    });
  });
  if (!r || !r.ok) return null;
  await chrome.storage.local.set({ port: r.port, token: r.token });
  return { port: r.port, token: r.token };
}

async function request(c, path, method, body) {
  const res = await fetch(`http://127.0.0.1:${c.port}${path}`, {
    method,
    headers: { "X-Palwoad-Token": c.token, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw Object.assign(new Error(data.error || `HTTP ${res.status}`), { status: res.status });
  return data;
}

async function api(path, method = "GET", body) {
  let c = await cfg();
  if (c.token) {
    try {
      return await request(c, path, method, body);
    } catch (e) {
      if (e.status && e.status !== 401) throw e; // real server error: report it
      // can't reach the service, or the token changed: re-pair below
    }
  }
  c = await pair();
  if (!c) {
    if ((await cfg()).token) throw new Error("Can't reach Palwoad. Start it from the Start menu.");
    throw new Error("Palwoad isn't installed on this computer. Run the Palwoad Setup first.");
  }
  return request(c, path, method, body);
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
