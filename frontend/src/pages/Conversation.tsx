import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Message, RelatedConversation } from "../types";
import { PLATFORM_LABELS, PLATFORM_COLORS } from "../types";

export default function Conversation() {
  const { conversationId } = useParams<{ conversationId: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [related, setRelated] = useState<RelatedConversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!conversationId) return;
    api
      .getConversation(conversationId)
      .then(setMessages)
      .catch(() => {})
      .finally(() => setLoading(false));

    api
      .getRelatedConversations(conversationId)
      .then(setRelated)
      .catch(() => {});
  }, [conversationId]);

  if (loading) {
    return <div className="empty-state"><p>加载中...</p></div>;
  }

  if (messages.length === 0) {
    return (
      <div className="empty-state">
        <h2>对话不存在</h2>
        <button className="retry-btn" onClick={() => navigate("/")}>
          返回首页
        </button>
      </div>
    );
  }

  const firstMsg = messages[0];
  const platform = PLATFORM_LABELS[firstMsg.platform] || firstMsg.platform;
  const color = PLATFORM_COLORS[firstMsg.platform] || "#666";
  const date = new Date(firstMsg.timestamp).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });

  // 提取标签（从最后一条 assistant 消息中）
  const lastAssistant = [...messages].reverse().find((m) => m.role === "assistant");
  const tags = lastAssistant?.tags;
  const summary = lastAssistant?.summary;
  const title = lastAssistant?.title || firstMsg.content.slice(0, 50);

  return (
    <div className="conversation-page">
      <button className="back-btn" onClick={() => navigate("/")}>
        &#x2190; 返回时间线
      </button>

      <div className="conversation-header">
        <span className="platform-badge large" style={{ backgroundColor: color }}>
          {platform}
        </span>
        <h2>{title}</h2>
        <div className="conv-meta">
          <span>{date}</span>
          {tags && (
            <div className="conv-tags">
              {tags.split(",").map((t) => (
                <span key={t} className="tag">{t.trim()}</span>
              ))}
            </div>
          )}
        </div>
        {summary && <div className="conv-summary">{summary}</div>}
      </div>

      <div className="message-list">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`message-bubble ${msg.role === "user" ? "user" : "assistant"}`}
          >
            <div className="message-role">
              {msg.role === "user" ? "你" : platform}
            </div>
            <div className="message-content">{msg.content}</div>
            <div className="message-time">
              {new Date(msg.timestamp).toLocaleTimeString("zh-CN", {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </div>
          </div>
        ))}
      </div>

      {/* 相关对话推荐 */}
      {related.length > 0 && (
        <div className="related-section">
          <h3>相关对话</h3>
          <div className="related-list">
            {related.map((r) => (
              <div
                key={r.conversation_id}
                className="related-card"
                onClick={() => navigate(`/conversation/${r.conversation_id}`)}
              >
                <div className="related-header">
                  <span
                    className="platform-badge"
                    style={{ backgroundColor: PLATFORM_COLORS[r.platform] || "#666" }}
                  >
                    {PLATFORM_LABELS[r.platform] || r.platform}
                  </span>
                  <span className="related-score">
                    相似度 {(r.score * 100).toFixed(0)}%
                  </span>
                </div>
                <div className="related-title">{r.title || "未命名对话"}</div>
                <div className="related-meta">
                  {r.message_count} 条消息 | {new Date(r.latest_timestamp).toLocaleDateString("zh-CN")}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
