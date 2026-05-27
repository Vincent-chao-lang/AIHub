// Background Service Worker
// 负责：消息转发、侧边栏管理、API 代理、健康检查

const DEFAULT_API_URL = "http://127.0.0.1:8712";

// 从 storage 读取 API 地址（支持用户自定义服务器）
async function getApiBase() {
  return new Promise((resolve) => {
    chrome.storage.local.get(["apiBaseUrl"], (result) => {
      resolve(result.apiBaseUrl || DEFAULT_API_URL);
    });
  });
}

// ── 侧边栏：点击扩展图标打开 ──
chrome.action.onClicked.addListener((tab) => {
  chrome.sidePanel.open({ windowId: tab.windowId });
});

// ── 消息分发 ──
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SAVE_MESSAGE") {
    getApiBase().then(apiBase => {
      fetch(`${apiBase}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(message.payload),
      })
        .then((res) => res.json())
        .then((data) => {
          console.log("[AI Memory Hub] 消息已转发:", data.id?.slice(0, 8));
        })
        .catch((e) => {
          console.debug("[AI Memory Hub] API 不可用:", e.message);
        });
    });
  }

  // 侧边栏代理：GET_CONTEXT
  if (message.type === "GET_CONTEXT") {
    getApiBase().then(apiBase => {
      fetch(`${apiBase}/context`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: message.query,
          max_tokens: message.maxTokens || 2000,
        }),
      })
        .then((res) => res.json())
        .then((data) => {
          sendResponse(data);
        })
        .catch((e) => {
          sendResponse({ error: e.message });
        });
    });
    return true;  // 异步响应
  }

  // 返回当前 API 地址（供 sidepanel/content scripts 查询）
  if (message.type === "GET_API_URL") {
    getApiBase().then(apiBase => {
      sendResponse({ apiBase });
    });
    return true;
  }
});

// ── 安装/更新时初始化 ──
chrome.runtime.onInstalled.addListener(() => {
  console.log("[AI Memory Hub] Personal AI OS v0.2.0 已安装");
  console.log("  点击扩展图标 → 打开侧边栏 / 设置");
});

// ── API 健康检查 ──
setInterval(async () => {
  try {
    const apiBase = await getApiBase();
    const res = await fetch(`${apiBase}/stats`);
    if (res.ok) {
      const stats = await res.json();
      console.debug("[AI Memory Hub] API 正常:", stats.total_messages, "条消息");
    }
  } catch (e) {
    // API 未运行，静默
  }
}, 30000);
