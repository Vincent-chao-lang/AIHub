// 统一消息格式（所有平台通用）
const MessageFormat = {
  platform: "",       // "chatgpt" | "claude" | "gemini" | "kimi" | "deepseek"
  conversation_id: "", // 对话 ID
  role: "",            // "user" | "assistant"
  content: "",         // 消息文本
  timestamp: "",       // ISO 8601
};

// API 地址
const API_BASE = "http://127.0.0.1:8712";

// 已发送消息的缓存（避免重复发送）
let sentMessages = new Set();

// 生成消息 ID
function generateMessageId(platform, conversationId, role, content) {
  const text = `${platform}:${conversationId}:${role}:${content}`;
  let hash = 0;
  for (let i = 0; i < text.length; i++) {
    const char = text.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return `${platform}_${conversationId}_${Math.abs(hash)}`;
}

// 发送消息到本地 API
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
    const response = await fetch(`${API_BASE}/messages`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.ok) {
      console.log("[AI Memory Hub] 消息已保存:", payload.platform, payload.role);
    }
  } catch (e) {
    // API 未启动时静默失败
    console.debug("[AI Memory Hub] API 不可用:", e.message);
  }
}
