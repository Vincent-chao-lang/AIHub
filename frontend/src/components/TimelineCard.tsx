import { useNavigate } from "react-router-dom";
import type { ConversationSummary } from "../types";
import { PLATFORM_LABELS, PLATFORM_COLORS } from "../types";

interface Props {
  conversation: ConversationSummary;
}

export default function TimelineCard({ conversation: conv }: Props) {
  const navigate = useNavigate();

  const platform = PLATFORM_LABELS[conv.platform] || conv.platform;
  const color = PLATFORM_COLORS[conv.platform] || "#666";
  const time = new Date(conv.latest_timestamp).toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  const title = conv.title || conv.preview || "未命名对话";

  return (
    <div
      className="timeline-card"
      onClick={() => navigate(`/conversation/${conv.conversation_id}`)}
    >
      <div className="card-header">
        <span className="platform-badge" style={{ backgroundColor: color }}>
          {platform}
        </span>
        <span className="card-time">{time}</span>
      </div>
      <div className="card-title">{title}</div>
      {conv.preview && (
        <div className="card-preview">{conv.preview}</div>
      )}
      <div className="card-footer">
        {conv.tags && (
          <div className="card-tags">
            {conv.tags.split(",").slice(0, 3).map((tag) => (
              <span key={tag} className="tag">
                {tag.trim()}
              </span>
            ))}
          </div>
        )}
        <span className="card-msg-count">{conv.message_count} 条消息</span>
      </div>
    </div>
  );
}
