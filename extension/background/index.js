// Background Service Worker
// 负责：消息转发、状态管理、定期健康检查

const API_BASE = "http://127.0.0.1:8712";

// 监听来自 content script 的消息
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "SAVE_MESSAGE") {
    fetch(`${API_BASE}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(message.payload),
    })
      .then((res) => {
        if (res.ok) {
          console.log("[AI Memory Hub] 消息已转发");
        }
      })
      .catch((e) => {
        console.debug("[AI Memory Hub] API 不可用:", e.message);
      });
  }
});

// 安装时初始化
chrome.runtime.onInstalled.addListener(() => {
  console.log("[AI Memory Hub] 插件已安装 v0.1.0");
});

// 检查 API 健康状态
setInterval(async () => {
  try {
    const res = await fetch(`${API_BASE}/stats`);
    if (res.ok) {
      const stats = await res.json();
      // 更新插件图标状态（后续可加 badge）
      console.debug("[AI Memory Hub] API 正常:", stats.total_messages, "条消息");
    }
  } catch (e) {
    // API 未运行
  }
}, 30000);
