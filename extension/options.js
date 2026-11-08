const $ = (id) => document.getElementById(id);
chrome.storage.local.get(["port", "token", "intercept"]).then((s) => {
  $("port").value = s.port || 9614; $("token").value = s.token || ""; $("intercept").checked = !!s.intercept;
});
$("save").onclick = async () => {
  await chrome.storage.local.set({ port: +$("port").value, token: $("token").value.trim(), intercept: $("intercept").checked });
  $("ok").textContent = "Saved ✓";
};
