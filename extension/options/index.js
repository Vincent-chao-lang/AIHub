// AI Memory Hub 设置页

const DEFAULT_API_URL = "http://127.0.0.1:8712";
const STORAGE_KEY = "apiBaseUrl";

const urlInput = document.getElementById("apiUrl");
const saveBtn = document.getElementById("saveBtn");
const toast = document.getElementById("toast");
const statusLine = document.getElementById("statusLine");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");

// 加载当前配置
chrome.storage.local.get([STORAGE_KEY], (result) => {
  urlInput.value = result[STORAGE_KEY] || DEFAULT_API_URL;
  checkConnection();
});

// 保存
saveBtn.addEventListener("click", () => {
  const url = urlInput.value.trim().replace(/\/+$/, "") || DEFAULT_API_URL;
  chrome.storage.local.set({ [STORAGE_KEY]: url }, () => {
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 1500);
    checkConnection();
  });
});

// 测试连接
async function checkConnection() {
  const base = urlInput.value.trim().replace(/\/+$/, "") || DEFAULT_API_URL;
  statusLine.style.display = "flex";
  statusText.textContent = "检测中...";
  statusDot.className = "status-dot";

  try {
    const res = await fetch(`${base}/stats`);
    if (res.ok) {
      const data = await res.json();
      statusDot.className = "status-dot online";
      statusText.textContent = `已连接 — ${data.total_messages} 条消息，${Object.keys(data.by_platform).length} 个平台`;
    } else {
      throw new Error("HTTP " + res.status);
    }
  } catch (e) {
    statusDot.className = "status-dot offline";
    statusText.textContent = "无法连接 — 请确认后端已启动且地址正确";
  }
}
