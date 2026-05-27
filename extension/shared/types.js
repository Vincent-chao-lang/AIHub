// 统一消息格式（所有平台通用）
const MessageFormat = {
  platform: "",       // "chatgpt" | "claude" | "gemini" | "kimi" | "deepseek"
  conversation_id: "", // 对话 ID
  role: "",            // "user" | "assistant"
  content: "",         // 消息文本
  timestamp: "",       // ISO 8601
};

// 默认 API 地址（用户可在扩展选项中修改）
const DEFAULT_API_BASE = "http://127.0.0.1:8712";

// 已发送消息的缓存（避免重复发送）
let sentMessages = new Set();

// 从 storage 读取 API 地址
function getApiBase() {
  return new Promise((resolve) => {
    if (typeof chrome !== "undefined" && chrome.storage) {
      chrome.storage.local.get(["apiBaseUrl"], (result) => {
        resolve(result.apiBaseUrl || DEFAULT_API_BASE);
      });
    } else {
      resolve(DEFAULT_API_BASE);
    }
  });
}

// 生成消息 ID
function generateMessageId(platform, conversationId, role, content) {
  const text = `${platform}:${conversationId}:${role}:${content}`;
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash;
  }
  return `${platform}_${conversationId}_${Math.abs(hash)}`;
}

// 发送消息到 API（读取 storage 中的自定义地址）
async function sendToAPI(payload) {
  const msgId = generateMessageId(
    payload.platform,
    payload.conversation_id,
    payload.role,
    payload.content
  );
  if (sentMessages.has(msgId)) return;
  sentMessages.add(msgId);

  try {
    const apiBase = await getApiBase();
    const response = await fetch(`${apiBase}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      console.log("[AI Memory Hub] 消息已保存:", payload.platform, payload.role);
    }
  } catch (e) {
    console.debug("[AI Memory Hub] API 不可用:", e.message);
  }
}
